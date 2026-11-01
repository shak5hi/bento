from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from bento_core import streams
from bento_core.config import settings
from bento_core.net import probe_target_error, repo_full_name, repo_url_error
from bento_core.scoring import status_for

from ..security import current_user_id
from ..state import state

router = APIRouter(prefix="/api", tags=["projects"])


class ProjectBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    repo_url: str | None = Field(default=None, max_length=500)
    endpoints: list[str] = Field(default_factory=list, max_length=20)


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    repo_url: str | None = Field(default=None, max_length=500)


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


async def _queue_scan(project_id: UUID, reason: str) -> None:
    await streams.publish(state.redis, streams.SCAN_JOBS, {"project_id": str(project_id), "sha": None, "delivery": reason})


def project_json(row, score=None) -> dict:
    total = score["total"] if score else None
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "repoUrl": row["repo_url"],
        "lastScanAt": row["last_scan_at"],
        "lastScanSha": row["last_scan_sha"],
        "createdAt": row["created_at"],
        "health": total,
        "status": status_for(total),
        "parts": (
            {k: score[k] for k in ("uptime", "latency", "errors", "code")} | {"basis": score["basis"]} if score else None
        ),
    }


@router.get("/projects")
async def list_projects(user_id: UUID = Depends(current_user_id)):
    rows = await state.pg.fetch(
        """SELECT p.*, s.total, s.uptime, s.latency, s.errors, s.code, s.basis
             FROM projects p LEFT JOIN project_scores s ON s.project_id = p.id
            WHERE p.owner_id = $1 ORDER BY p.created_at""",
        user_id,
    )
    return {"projects": [project_json(r, r if r["total"] is not None else None) for r in rows]}


@router.post("/projects", status_code=201)
async def create_project(body: ProjectBody, user_id: UUID = Depends(current_user_id)):
    repo = _check_repo(body.repo_url)
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

    return {
        "project": project_json(row, score),
        "endpoints": [ep_json(e) for e in endpoints],
        "findings": [
            {
                "id": str(f["id"]),
                "severity": f["severity"],
                "title": f["title"],
                "detail": f["detail"],
                "effortMinutes": f["effort_minutes"],
                "firstSeen": f["first_seen"],
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
                "source": advice["source"],
                "generatedAt": advice["generated_at"],
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


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: UUID, user_id: UUID = Depends(current_user_id)):
    await owned_project(project_id, user_id)
    await state.pg.execute("DELETE FROM projects WHERE id = $1", project_id)


@router.post("/projects/{project_id}/scan", status_code=202)
async def scan_now(project_id: UUID, user_id: UUID = Depends(current_user_id)):
    row = await owned_project(project_id, user_id)
    if not row["repo_url"]:
        raise HTTPException(422, "Add a repository URL to this project first")
    await _queue_scan(project_id, "manual")
    return {"queued": True}


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
