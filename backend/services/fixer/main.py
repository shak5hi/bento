"""Fixer: fix.jobs -> a branch, one commit and a pull request on GitHub.

* Only projects imported through the GitHub App (projects.installation_id), using its installation token.
* Never writes to the default branch: changes go on a new `bento/fix-...` branch and a human merges the PR.
* One active PR per finding: the API refuses duplicates (unique index on queued/open rows) and the worker
  adopts an already-open PR for the branch instead of opening a second one.
* Secret files are deleted by path, never read.
"""

import asyncio
import time

import httpx

from bento_core import github, streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.log import setup_logging

import fixes
from gh import FixError, Repo

log = setup_logging()


class Fixer:
    def __init__(self, pg, r, http):
        self.pg, self.r, self.http = pg, r, http

    async def handle(self, batch: list[streams.Message]) -> None:
        for _, job in batch:
            await self.run(job["fix_id"])

    async def run(self, fix_id: str) -> None:
        row = await self.pg.fetchrow(
            """SELECT f.id, f.finding_key, f.status, p.id AS project_id, p.owner_id, p.name,
                      p.repo_full_name, p.installation_id
                 FROM fix_prs f JOIN projects p ON p.id = f.project_id WHERE f.id = $1""",
            fix_id,
        )
        if row is None or row["status"] != "queued":
            return  # cancelled, or a redelivery of a job that already finished
        key = row["finding_key"]
        try:
            if not row["installation_id"] or not row["repo_full_name"]:
                raise FixError("Auto-fix needs the project to be imported through the Bento GitHub app.")
            if not fixes.fixable(key):
                raise FixError("Bento can't fix this kind of finding automatically yet.")
            repo = Repo(row["repo_full_name"], row["installation_id"], self.http)
            branch, pr = await self.make_pr(repo, key)
        except (FixError, github.GitHubError, httpx.HTTPError, KeyError, ValueError) as exc:
            if not isinstance(exc, (FixError, github.GitHubError)):
                log.exception("fix %s for %s crashed", key, row["name"])
                exc = FixError("Something went wrong talking to GitHub. Try again in a minute.")
            log.info("fix %s for %s failed: %s", key, row["name"], exc)
            await self.pg.execute(
                "UPDATE fix_prs SET status = 'failed', error = $2, updated_at = now() WHERE id = $1", row["id"], str(exc)
            )
            await self.note(row, "Fix failed", f"{key}: {exc}")
            return
        await self.pg.execute(
            """UPDATE fix_prs SET status = 'open', branch = $2, pr_number = $3, pr_url = $4, error = NULL,
                      updated_at = now() WHERE id = $1""",
            row["id"], branch, pr["number"], pr["html_url"],
        )
        log.info("opened PR #%s on %s for %s", pr["number"], row["repo_full_name"], key)
        await self.note(row, "Fix pull request opened", f"#{pr['number']}: {pr['title']}")

    async def make_pr(self, repo: Repo, key: str) -> tuple[str, dict]:
        info = await repo.info()
        if info.get("archived"):
            raise FixError("The repository is archived, so it can't take pull requests.")
        base = info["default_branch"]
        branch = fixes.branch_for(key)
        if await repo.branch_exists(branch):
            if existing := await repo.pr_for_branch(branch):
                return branch, existing  # a PR is already open: track it, don't open another
            branch = f"{branch}-{int(time.time())}"  # stale branch from a closed PR: leave it alone
        base_sha = await repo.head(base)
        files = await repo.tree(base_sha)
        fix = await self.build(repo, key, base_sha, files, info)
        try:
            await repo.commit_to_new_branch(branch, base_sha, f"{fix.message}\n\nOpened by Bento for finding {key}.", fix.changes)
        except FixError as exc:
            if "403" in str(exc) and any(p.startswith(".github/workflows/") for p in fix.changes):
                raise FixError(
                    "GitHub only lets apps add CI files with the Workflows permission. In your GitHub App's settings, "
                    "set Repository permissions → Workflows to Read and write, save, then accept the new permission "
                    "on the installation and try again."
                ) from None
            raise
        pr = await repo.open_pr(branch, base, f"Bento: {fix.title}", fix.body)
        return branch, pr

    async def build(self, repo: Repo, key: str, ref: str, files: list[str], info: dict) -> fixes.Fix:
        if key == "no-ci":
            return fixes.fix_no_ci(files, await repo.read("package.json", ref) if "package.json" in files else None)
        if key == "no-readme":
            return fixes.fix_no_readme(files, info)
        if key == "secrets-env-file":
            return fixes.fix_env_file(files, await repo.read(".gitignore", ref) if ".gitignore" in files else None)
        _, eco, name = key.split(":", 2)
        if eco == "npm":
            return await self.npm_fix(repo, name, ref, files)
        return await self.pypi_fix(repo, name, ref, files)

    async def npm_fix(self, repo: Repo, name: str, ref: str, files: list[str]) -> fixes.Fix:
        if "package.json" not in files:
            raise FixError("No package.json at the repository root.")
        pkg = await repo.read("package.json", ref) or "{}"
        lock = await repo.read("package-lock.json", ref) if "package-lock.json" in files else None
        current = fixes.npm_locked_version(lock, name)
        if current is None:
            raise FixError(f"Couldn't find the installed version of {name} in package-lock.json.")
        fixed, unfixed = await fixes.fixed_version("npm", name, current, self.http)
        try:
            new_pkg = fixes.bump_package_json(pkg, name, fixed)
        except ValueError:
            raise FixError("package.json isn't valid JSON.") from None
        lock_note = (
            "> [!IMPORTANT]\n> **The lockfile still needs regenerating.** Bento only edits `package.json`. "
            "Check out this branch, run `npm install`, and commit the updated `package-lock.json`, "
            "otherwise `npm ci` keeps installing the old version.\n\n"
        )
        return fixes.Fix(
            title=f"Upgrade {name} to {fixed}",
            message=f"Upgrade {name} from {current} to {fixed}",
            changes={"package.json": new_pkg},
            body=fixes.vuln_fix_body("npm", name, current, fixed, unfixed, lock_note),
        )

    async def pypi_fix(self, repo: Repo, name: str, ref: str, files: list[str]) -> fixes.Fix:
        if "requirements.txt" not in files:
            raise FixError("No requirements.txt at the repository root.")
        text = await repo.read("requirements.txt", ref) or ""
        current = next(
            (v for n, v in (l.split("==", 1) for l in text.splitlines() if "==" in l and not l.lstrip().startswith("#"))
             if fixes._norm(n.split("[")[0].strip()) == fixes._norm(name)),
            None,
        )
        if current is None:
            raise FixError(f"{name} isn't pinned with == in requirements.txt.")
        current = current.split(";")[0].split("#")[0].strip()
        fixed, unfixed = await fixes.fixed_version("PyPI", name, current, self.http)
        new_text, changed = fixes.bump_requirements(text, name, fixed)
        if not changed:
            raise FixError(f"Couldn't update {name} in requirements.txt.")
        locks = [f for f in ("poetry.lock", "Pipfile.lock", "uv.lock") if f in files]
        lock_note = (
            f"> [!IMPORTANT]\n> **{', '.join(locks)} still needs regenerating** to match. Bento only edits "
            "`requirements.txt`.\n\n" if locks else
            "`requirements.txt` pins exact versions, so no other lockfile needs updating.\n\n"
        )
        return fixes.Fix(
            title=f"Upgrade {name} to {fixed}",
            message=f"Upgrade {name} from {current} to {fixed}",
            changes={"requirements.txt": new_text},
            body=fixes.vuln_fix_body("PyPI", name, current, fixed, unfixed, lock_note),
        )

    async def note(self, row, title: str, body: str) -> None:
        await self.pg.execute(
            "INSERT INTO notifications (owner_id, project_id, kind, title, body) VALUES ($1, $2, 'fix', $3, $4)",
            row["owner_id"], row["project_id"], title, body,
        )


async def main() -> None:
    pg = await create_pool(settings.database_url)
    r = streams.connect()
    async with httpx.AsyncClient(timeout=20) as http:
        await streams.consume(r, streams.FIX_JOBS, "fixer", Fixer(pg, r, http).handle, count=1, block_ms=5000)


if __name__ == "__main__":
    asyncio.run(main())
