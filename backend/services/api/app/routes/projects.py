import re
import secrets
from uuid import UUID

import asyncpg

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from bento_core import github, streams
from bento_core.config import settings
from bento_core.guides import guide_for, plain
from bento_core.net import probe_target_error, repo_full_name, repo_url_error
from bento_core.scoring import status_for

from ..security import current_user_id, rate_limit
from ..state import state

router = APIRouter(prefix="/api", tags=["projects"])


class ProjectBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    repo_url: str | None = Field(default=None, max_length=500)
    endpoints: list[str] = Field(default_factory=list, max_length=20)


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    repo_url: str | None = Field(default=None, max_length=500)


class PublicBody(BaseModel):
    enabled: bool


class EndpointBody(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    interval_s: int = Field(default=settings.default_probe_interval, ge=15, le=3600)


async def owned_project(project_id: UUID, user_id: UUID):
    row = await state.pg.fetchrow("SELECT * FROM projects WHERE id = $1 AND owner_id = $2", project_id, user_id)
    if row is None:
        raise HTTPException(404, "Project not found")
    return row


def _check_repo(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip().removesuffix("/")
    if err := repo_url_error(url):
        raise HTTPException(422, err)
    return url


def _check_endpoint(url: str) -> str:
    url = url.strip()
    if err := probe_target_error(url):
        raise HTTPException(422, f"{url}: {err}")
    return url


async def _queue_scan(project_id: UUID, reason: str, force: bool = False) -> None:
    job = {"project_id": str(project_id), "sha": None, "delivery": reason} | ({"force": True} if force else {})
    await streams.publish(state.redis, streams.SCAN_JOBS, job)


def project_json(row, score=None, week_change: int | None = None) -> dict:
    total = score["total"] if score else None
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "repoUrl": row["repo_url"],
        "lastScanAt": row["last_scan_at"],
        "lastScanSha": row["last_scan_sha"],
        "lastScanError": row["last_scan_error"],
        "createdAt": row["created_at"],
        "isPublic": row["is_public"],
        "publicSlug": row["public_slug"] if row["is_public"] else None,
        "health": total,
        "grade": score["grade"] if score else None,
        "status": status_for(total),
        "basis": score["basis"] if score else None,
        # report cards (bento_core.scoring): security, website, basics, upkeep, each explained
        "cards": score["cards"] if score else None,
        "nextAction": score["next_action"] if score else None,
        "capped": score["capped"] if score else None,
        "weekChange": week_change,
    }


@router.get("/projects")
async def list_projects(user_id: UUID = Depends(current_user_id)):
    rows = await state.pg.fetch(
        """SELECT p.*, s.total, s.grade, s.cards, s.next_action, s.capped, s.basis
             FROM projects p LEFT JOIN project_scores s ON s.project_id = p.id
            WHERE p.owner_id = $1 ORDER BY p.created_at""",
        user_id,
    )
    weeks = await week_changes([r["id"] for r in rows], {r["id"]: r["total"] for r in rows})
    return {"projects": [project_json(r, r if r["total"] is not None else None, weeks.get(r["id"])) for r in rows]}


async def week_changes(project_ids: list, totals: dict) -> dict:
    """Score now minus the score about a week ago (the oldest reading in the last 7 days)."""
    if not project_ids:
        return {}
    rows = await state.ts.fetch(
        """SELECT DISTINCT ON (project_id) project_id, total FROM project_health
            WHERE project_id = ANY($1::uuid[]) AND time > now() - interval '7 days'
            ORDER BY project_id, time""",
        project_ids,
    )
    return {r["project_id"]: totals[r["project_id"]] - r["total"] for r in rows if totals.get(r["project_id"]) is not None}


async def _check_not_added(user_id: UUID, repo: str | None, except_id: UUID | None = None) -> None:
    """One project per repository: re-adding it would just split its history in two."""
    if not repo:
        return
    existing = await state.pg.fetchval(
        "SELECT name FROM projects WHERE owner_id = $1 AND repo_full_name = $2 AND id IS DISTINCT FROM $3",
        user_id, repo_full_name(repo), except_id,
    )
    if existing:
        raise HTTPException(409, f"This repository is already in Bento as \"{existing}\"")


@router.post("/projects", status_code=201)
async def create_project(body: ProjectBody, user_id: UUID = Depends(current_user_id)):
    repo = _check_repo(body.repo_url)
    await _check_not_added(user_id, repo)
    urls = list(dict.fromkeys(_check_endpoint(u) for u in body.endpoints if u.strip()))
    async with state.pg.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            "INSERT INTO projects (owner_id, name, repo_url, repo_full_name) VALUES ($1, $2, $3, $4) RETURNING *",
            user_id,
            body.name.strip(),
            repo,
            repo_full_name(repo) if repo else None,
        )
        for url in urls:
            await conn.execute(
                "INSERT INTO endpoints (project_id, url, interval_s) VALUES ($1, $2, $3)",
                row["id"],
                url,
                settings.default_probe_interval,
            )
    if repo:
        await _queue_scan(row["id"], "project-created")
    await streams.publish(state.redis, streams.ADVICE_REQUESTS, {"project_id": str(row["id"])})
    return {"project": project_json(row)}


@router.get("/projects/{project_id}")
async def get_project(project_id: UUID, user_id: UUID = Depends(current_user_id)):
    row = await owned_project(project_id, user_id)
    score = await state.pg.fetchrow("SELECT * FROM project_scores WHERE project_id = $1", project_id)
    endpoints = await state.pg.fetch("SELECT * FROM endpoints WHERE project_id = $1 ORDER BY created_at", project_id)
    findings = await state.pg.fetch(
        """SELECT * FROM findings WHERE project_id = $1 AND status = 'open'
           ORDER BY array_position(ARRAY['critical','high','medium','low'], severity), first_seen""",
        project_id,
    )
    incidents = await state.pg.fetch(
        "SELECT * FROM incidents WHERE project_id = $1 ORDER BY opened_at DESC LIMIT 20", project_id
    )
    advice = await state.pg.fetchrow("SELECT * FROM advice WHERE project_id = $1", project_id)
    # latest fix attempt per finding (queued/open ones win: there's at most one of those per finding)
    fix_rows = await state.pg.fetch(
        """SELECT DISTINCT ON (finding_key) finding_key, status, pr_url, pr_number, error
             FROM fix_prs WHERE project_id = $1
            ORDER BY finding_key, (status IN ('queued', 'open')) DESC, created_at DESC""",
        project_id,
    )
    fix_by_key = {r["finding_key"]: r for r in fix_rows}
    can_fix = row["installation_id"] is not None
    last = await state.ts.fetch(
        """SELECT DISTINCT ON (endpoint_id) endpoint_id, time, status, latency_ms, ok
             FROM probe_results WHERE project_id = $1 AND time > now() - interval '1 hour'
            ORDER BY endpoint_id, time DESC""",
        project_id,
    )
    last_by_ep = {r["endpoint_id"]: r for r in last}
    open_kinds = {(i["endpoint_id"], i["kind"]) for i in incidents if i["status"] == "open"}

    def ep_json(e):
        lp = last_by_ep.get(e["id"])
        state_ = "incident" if any((e["id"], k) in open_kinds for k in ("latency", "errors")) else (
            "pending" if lp is None else ("normal" if lp["ok"] else "failing")
        )
        return {
            "id": str(e["id"]),
            "url": e["url"],
            "intervalS": e["interval_s"],
            "state": state_,
            "lastStatus": lp["status"] if lp else None,
            "lastLatencyMs": round(lp["latency_ms"]) if lp and lp["latency_ms"] is not None else None,
            "lastProbedAt": lp["time"] if lp else None,
        }

    history = await state.pg.fetch(
        "SELECT at, total, previous, grade, reason FROM score_events WHERE project_id = $1 ORDER BY at DESC LIMIT 20",
        project_id,
    )
    weeks = await week_changes([project_id], {project_id: score["total"] if score else None})
    return {
        "project": project_json(row, score, weeks.get(project_id)),
        "history": [
            {"at": h["at"], "total": h["total"], "previous": h["previous"], "grade": h["grade"], "reason": h["reason"]}
            for h in history
        ],
        "endpoints": [ep_json(e) for e in endpoints],
        "findings": [
            {
                "id": str(f["id"]),
                "key": f["key"],
                "severity": f["severity"],
                **dict(zip(("title", "detail"), plain(f["key"], f["title"], f["detail"], f["meta"]))),
                "technical": {"title": f["title"], "detail": f["detail"]},
                "effortMinutes": f["effort_minutes"],
                "firstSeen": f["first_seen"],
                "fixable": can_fix and github.fixable_finding(f["key"]),
                "guide": guide_for(f["key"]),  # what's wrong / why it matters / how to fix, in plain words
                "fix": (
                    {
                        "status": fx["status"],
                        "prUrl": fx["pr_url"],
                        "prNumber": fx["pr_number"],
                        "error": fx["error"],
                    }
                    if (fx := fix_by_key.get(f["key"]))
                    else None
                ),
            }
            for f in findings
        ],
        "incidents": [
            {
                "id": str(i["id"]),
                "url": i["url"],
                "kind": i["kind"],
                "status": i["status"],
                "baseline": i["baseline"],
                "peak": i["peak"],
                "openedAt": i["opened_at"],
                "closedAt": i["closed_at"],
            }
            for i in incidents
        ],
        "advice": (
            {
                "brief": advice["brief"],
                "recommendations": advice["recommendations"],
                "generatedAt": advice["generated_at"],
                "source": advice["source"],  # "rules" or "ai:<model>"
            }
            if advice
            else None
        ),
    }


@router.get("/projects/{project_id}/latency")
async def latency_series(
    project_id: UUID, minutes: int = Query(60, ge=5, le=1440), user_id: UUID = Depends(current_user_id)
):
    await owned_project(project_id, user_id)
    bucket = max(1, minutes // 60)
    rows = await state.ts.fetch(
        """SELECT time_bucket(make_interval(mins => $3), time) AS t,
                  percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE ok) AS p95,
                  count(*) FILTER (WHERE NOT ok) AS failures, count(*) AS total
             FROM probe_results
            WHERE project_id = $1 AND time > now() - make_interval(mins => $2)
            GROUP BY t ORDER BY t""",
        project_id,
        minutes,
        bucket,
    )
    return {
        "points": [
            {"t": r["t"], "p95": round(r["p95"]) if r["p95"] is not None else None, "failures": r["failures"], "total": r["total"]}
            for r in rows
        ]
    }


@router.patch("/projects/{project_id}")
async def update_project(project_id: UUID, body: ProjectPatch, user_id: UUID = Depends(current_user_id)):
    current = await owned_project(project_id, user_id)
    fields = body.model_dump(exclude_unset=True)
    name = (fields.get("name") or current["name"]).strip()
    repo = _check_repo(fields["repo_url"]) if "repo_url" in fields else current["repo_url"]
    if repo != current["repo_url"]:
        await _check_not_added(user_id, repo, except_id=project_id)
    row = await state.pg.fetchrow(
        "UPDATE projects SET name = $3, repo_url = $4, repo_full_name = $5 WHERE id = $1 AND owner_id = $2 RETURNING *",
        project_id,
        user_id,
        name,
        repo,
        repo_full_name(repo) if repo else None,
    )
    if repo and repo != current["repo_url"]:
        await _queue_scan(project_id, "repo-changed")
    return {"project": project_json(row)}


def _new_slug(name: str) -> str:
    """Readable and unguessable: `my-app-3f9k2a`. Random suffix so private names can't be probed."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40].strip("-") or "project"
    return f"{base}-{secrets.token_hex(3)}"


@router.put("/projects/{project_id}/public")
async def set_public(project_id: UUID, body: PublicBody, user_id: UUID = Depends(current_user_id)):
    """Turn the public status page and badge on or off. The slug is created once and kept."""
    current = await owned_project(project_id, user_id)
    if not body.enabled or current["public_slug"]:
        row = await state.pg.fetchrow(
            "UPDATE projects SET is_public = $2 WHERE id = $1 RETURNING *", project_id, body.enabled
        )
        return {"project": project_json(row)}
    for _ in range(5):
        try:
            row = await state.pg.fetchrow(
                "UPDATE projects SET is_public = true, public_slug = $2 WHERE id = $1 RETURNING *",
                project_id,
                _new_slug(current["name"]),
            )
            return {"project": project_json(row)}
        except asyncpg.UniqueViolationError:
            continue
    raise HTTPException(500, "Could not create a public link, please try again")


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: UUID, user_id: UUID = Depends(current_user_id)):
    await owned_project(project_id, user_id)
    await state.pg.execute("DELETE FROM projects WHERE id = $1", project_id)


@router.post("/projects/{project_id}/scan", status_code=202)
async def scan_now(project_id: UUID, user_id: UUID = Depends(current_user_id)):
    row = await owned_project(project_id, user_id)
    if not row["repo_url"]:
        raise HTTPException(422, "Add a repository URL to this project first")
    await _queue_scan(project_id, "manual", force=True)
    return {"queued": True}


@router.post(
    "/projects/{project_id}/findings/{finding_id}/fix",
    status_code=202,
    dependencies=[Depends(rate_limit("fix", 20, 60))],
)
async def fix_finding(project_id: UUID, finding_id: UUID, user_id: UUID = Depends(current_user_id)):
    """Queue an auto-fix pull request. The fixer worker does the GitHub work, not this request."""
    project = await owned_project(project_id, user_id)
    finding = await state.pg.fetchrow(
        "SELECT key FROM findings WHERE id = $1 AND project_id = $2 AND status = 'open'", finding_id, project_id
    )
    if finding is None:
        raise HTTPException(404, "Finding not found or already resolved")
    if project["installation_id"] is None:
        raise HTTPException(422, "Auto-fix works for repositories imported through the Bento GitHub app")
    if not github.fixable_finding(finding["key"]):
        raise HTTPException(422, "Bento can't fix this kind of finding automatically yet")
    fix = await state.pg.fetchrow(
        """INSERT INTO fix_prs (project_id, finding_key) VALUES ($1, $2)
           ON CONFLICT (project_id, finding_key) WHERE status IN ('queued', 'open') DO NOTHING
           RETURNING id""",
        project_id,
        finding["key"],
    )
    if fix is None:
        raise HTTPException(409, "A fix pull request for this finding is already open or on its way")
    await streams.publish(state.redis, streams.FIX_JOBS, {"fix_id": str(fix["id"])})
    return {"queued": True, "fixId": str(fix["id"])}


@router.post("/projects/{project_id}/endpoints", status_code=201)
async def add_endpoint(project_id: UUID, body: EndpointBody, user_id: UUID = Depends(current_user_id)):
    await owned_project(project_id, user_id)
    url = _check_endpoint(body.url)
    row = await state.pg.fetchrow(
        """INSERT INTO endpoints (project_id, url, interval_s) VALUES ($1, $2, $3)
           ON CONFLICT (project_id, url) DO NOTHING RETURNING *""",
        project_id,
        url,
        body.interval_s,
    )
    if row is None:
        raise HTTPException(409, "This endpoint is already monitored")
    return {"endpoint": {"id": str(row["id"]), "url": row["url"], "intervalS": row["interval_s"]}}


@router.delete("/endpoints/{endpoint_id}", status_code=204)
async def delete_endpoint(endpoint_id: UUID, user_id: UUID = Depends(current_user_id)):
    result = await state.pg.execute(
        """DELETE FROM endpoints e USING projects p
            WHERE e.id = $1 AND e.project_id = p.id AND p.owner_id = $2""",
        endpoint_id,
        user_id,
    )
    if result.endswith(" 0"):
        raise HTTPException(404, "Endpoint not found")
