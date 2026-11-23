"""Repo scanner: scan.jobs -> findings.

* Dedupe by commit SHA: GitHub may deliver the same push several times; each commit is scanned once.
* Checks: hygiene (tests, CI, README, lockfile, .env files), secrets in code, known-vulnerable and
  outdated dependencies, Dockerfile practices. Secret values are never stored, logged or shown.
* Sandboxed: shallow fetch of exactly one commit into a throwaway directory, as an unprivileged
  user, with timeouts and a size cap. Repository code is read, never executed.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

import httpx

from bento_core import github, streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.log import setup_logging
from bento_core.net import repo_url_error
from bento_core.scanning import list_files, run_checks


log = setup_logging()

GIT_TIMEOUT_S = 120
MAX_REPO_MB = 500
GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",  # never prompt for credentials (private repos fail fast)
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_LFS_SKIP_SMUDGE": "1",
}
GIT_SAFE = ["-c", "protocol.file.allow=never", "-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false"]


class ScanError(Exception):
    pass


async def git(*args: str, cwd: str | None = None, auth: str | None = None) -> str:
    env = GIT_ENV
    if auth:
        # Pass the token through git's environment config, never argv: command lines are visible
        # in process listings (ps, docker top), environment variables are not.
        env = {**GIT_ENV, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraHeader", "GIT_CONFIG_VALUE_0": auth}
    proc = await asyncio.create_subprocess_exec(
        "git", *GIT_SAFE, *args, cwd=cwd, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), GIT_TIMEOUT_S)
    except asyncio.TimeoutError:
        proc.kill()
        raise ScanError(f"git {args[0]} timed out") from None
    if proc.returncode != 0:
        raise ScanError(f"git {args[0]} failed: {err.decode(errors='ignore').strip()[:300]}")
    return out.decode().strip()


async def resolve_head(url: str, auth: str | None = None) -> str:
    out = await git("ls-remote", url, "HEAD", auth=auth)
    if not out:
        raise ScanError("repository has no HEAD (empty or private)")
    return out.split()[0]


def dir_size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink()) / 1_048_576


class Scanner:
    def __init__(self, pg, r, http):
        self.pg, self.r, self.http = pg, r, http

    async def handle(self, batch: list[streams.Message]) -> None:
        for _, job in batch:
            await self.run(job)

    async def run(self, job: dict) -> None:
        project = await self.pg.fetchrow(
            "SELECT id, owner_id, name, repo_url, installation_id FROM projects WHERE id = $1", job["project_id"]
        )
        if project is None or not project["repo_url"] or repo_url_error(project["repo_url"]):
            return
        name, url = project["name"], project["repo_url"]
        auth = None
        try:
            if project["installation_id"]:  # imported through the GitHub App: private repos work too
                token = await github.installation_token(project["installation_id"], self.http)
                auth = github.git_auth_header(token)
            sha = job.get("sha") or await resolve_head(url, auth)
        except github.GitHubError as exc:
            await self.fail(project, str(exc))
            return
        except ScanError as exc:
            await self.fail(project, f"Could not reach {url}: {exc}")
            return

        # Claim the (project, commit) pair. Re-scan only if the earlier attempt failed or got stuck
        # (scanner crashed mid-scan); otherwise this delivery is a duplicate.
        claim = await self.pg.fetchrow(
            """WITH prev AS (SELECT status, started_at FROM scans WHERE project_id = $1 AND sha = $2)
               INSERT INTO scans (project_id, sha, status) VALUES ($1, $2, 'running')
               ON CONFLICT (project_id, sha) DO UPDATE SET
                 delivery_count = scans.delivery_count + 1,
                 status = CASE WHEN scans.status = 'failed'
                                 OR (scans.status = 'running' AND scans.started_at < now() - interval '10 minutes')
                               THEN 'running' ELSE scans.status END,
                 started_at = CASE WHEN scans.status = 'failed'
                                     OR (scans.status = 'running' AND scans.started_at < now() - interval '10 minutes')
                                   THEN now() ELSE scans.started_at END
               RETURNING delivery_count, (xmax = 0) AS inserted,
                         (SELECT status FROM prev) AS prev_status, (SELECT started_at FROM prev) AS prev_started""",
            project["id"], sha,
        )
        stale = claim["prev_status"] == "running" and claim["prev_started"] is not None and (
            await self.pg.fetchval("SELECT $1 < now() - interval '10 minutes'", claim["prev_started"])
        )
        # "Scan now" always rescans: the checks may have changed even if the commit hasn't.
        forced = bool(job.get("force")) and not claim["inserted"]
        if forced:
            await self.pg.execute(
                "UPDATE scans SET status = 'running', started_at = now(), error = NULL WHERE project_id = $1 AND sha = $2",
                project["id"], sha,
            )
        if not (claim["inserted"] or claim["prev_status"] == "failed" or stale or forced):
            log.info("skip %s@%s: already scanned (delivery %d)", name, sha[:7], claim["delivery_count"])
            return

        log.info("scanning %s@%s in sandbox (delivery %s)", name, sha[:7], job.get("delivery"))
        workdir = tempfile.mkdtemp(prefix="scan-")
        try:
            await git("init", "--quiet", workdir)
            await git("fetch", "--quiet", "--depth", "1", url, sha, cwd=workdir, auth=auth)
            await git("checkout", "--quiet", "FETCH_HEAD", cwd=workdir)
            root = Path(workdir)
            if dir_size_mb(root) > MAX_REPO_MB:
                raise ScanError(f"repository is larger than {MAX_REPO_MB} MB")
            # the same checks the `bento scan` CLI runs (bento_core.scanning)
            found = await run_checks(root, list_files(root), self.http, cache=self.r)
        except ScanError as exc:
            await self.pg.execute(
                "UPDATE scans SET status = 'failed', error = $3, finished_at = now() WHERE project_id = $1 AND sha = $2",
                project["id"], sha, str(exc),
            )
            await self.fail(project, str(exc))
            return
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        new, resolved = await self.save(project["id"], sha, found)
        log.info("done %s@%s: %d findings (%d new, %d resolved)", name, sha[:7], len(found), new, resolved)
        await self.note(project, "scan", "Scan finished",
                        f"{sha[:7]}: {len(found)} open finding{'s' if len(found) != 1 else ''}, {new} new, {resolved} resolved")
        await streams.publish(self.r, streams.ADVICE_REQUESTS, {"project_id": str(project["id"])})

    async def save(self, project_id, sha: str, found: list[dict]) -> tuple[int, int]:
        keys = [f["key"] for f in found]
        async with self.pg.acquire() as conn, conn.transaction():
            before = {r["key"] for r in await conn.fetch(
                "SELECT key FROM findings WHERE project_id = $1 AND status = 'open'", project_id)}
            for f in found:
                await conn.execute(
                    """INSERT INTO findings (project_id, key, severity, title, detail, effort_minutes)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       ON CONFLICT (project_id, key) DO UPDATE SET severity = $3, title = $4, detail = $5,
                         effort_minutes = $6, last_seen = now(), status = 'open', resolved_at = NULL""",
                    project_id, f["key"], f["severity"], f["title"], f["detail"], f["effort_minutes"],
                )
            await conn.execute(
                """UPDATE findings SET status = 'resolved', resolved_at = now()
                    WHERE project_id = $1 AND status = 'open' AND NOT (key = ANY($2::text[]))""",
                project_id, keys,
            )
            await conn.execute(
                "UPDATE scans SET status = 'done', finished_at = now() WHERE project_id = $1 AND sha = $2", project_id, sha)
            await conn.execute(
                "UPDATE projects SET last_scan_at = now(), last_scan_sha = $2, last_scan_error = NULL WHERE id = $1", project_id, sha)
        return len(set(keys) - before), len(before - set(keys))

    async def fail(self, project, reason: str) -> None:
        await self.pg.execute("UPDATE projects SET last_scan_error = $2 WHERE id = $1", project["id"], reason)
        await self.note(project, "scan", "Scan failed", reason)

    async def note(self, project, kind: str, title: str, body: str) -> None:
        await self.pg.execute(
            "INSERT INTO notifications (owner_id, project_id, kind, title, body) VALUES ($1, $2, $3, $4, $5)",
            project["owner_id"], project["id"], kind, title, body,
        )


async def main() -> None:
    pg = await create_pool(settings.database_url)
    r = streams.connect()
    async with httpx.AsyncClient(timeout=20) as http:
        # scans are slow: one at a time per scanner replica
        await streams.consume(r, streams.SCAN_JOBS, "scanner", Scanner(pg, r, http).handle, count=1, block_ms=5000)


if __name__ == "__main__":
    asyncio.run(main())
