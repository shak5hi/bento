"""Public, unauthenticated views of a project: the status page and the README badge.

Only projects whose owner turned on "Public status page" are visible, looked up by their slug.
These endpoints never expose code findings, vulnerability details, endpoint paths or Pickle's
advice: a public page listing open security issues would advertise them.
"""

import json
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder

from bento_core.scoring import status_for

from ..security import rate_limit
from ..state import state

router = APIRouter(prefix="/api", tags=["public"])

STATUS_CACHE_S = 30


def _host(url: str) -> str:
    """Hostname only: paths and query strings can carry tokens."""
    return urlsplit(url).hostname or "endpoint"


async def _public_project(slug: str):
    if len(slug) > 64:
        return None
    return await state.pg.fetchrow(
        """SELECT p.id, p.name, s.total, s.basis, s.computed_at
             FROM projects p LEFT JOIN project_scores s ON s.project_id = p.id
            WHERE p.public_slug = $1 AND p.is_public""",
        slug,
    )


def _pct(ok: int, total: int) -> float | None:
    return round(ok * 100 / total, 2) if total else None


async def _status_payload(project) -> dict:
    pid = project["id"]
    uptime = await state.ts.fetchrow(
        """SELECT count(*) FILTER (WHERE time > now() - interval '24 hours')        AS t1,
                  count(*) FILTER (WHERE time > now() - interval '24 hours' AND ok) AS o1,
                  count(*) FILTER (WHERE time > now() - interval '7 days')          AS t7,
                  count(*) FILTER (WHERE time > now() - interval '7 days' AND ok)   AS o7,
                  count(*)                                                          AS t30,
                  count(*) FILTER (WHERE ok)                                        AS o30
             FROM probe_results WHERE project_id = $1 AND time > now() - interval '30 days'""",
        pid,
    )
    latency = await state.ts.fetch(
        """SELECT time_bucket(interval '30 minutes', time) AS t,
                  percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE ok) AS p95
             FROM probe_results WHERE project_id = $1 AND time > now() - interval '24 hours'
            GROUP BY t ORDER BY t""",
        pid,
    )
    open_incidents = await state.pg.fetch(
        """SELECT kind, url, opened_at FROM incidents
            WHERE project_id = $1 AND status = 'open' ORDER BY opened_at DESC LIMIT 20""",
        pid,
    )
    resolved = await state.pg.fetch(
        """SELECT kind, url, opened_at, closed_at FROM incidents
            WHERE project_id = $1 AND status = 'closed' AND closed_at > now() - interval '30 days'
            ORDER BY closed_at DESC LIMIT 10""",
        pid,
    )
    endpoints = await state.pg.fetchval("SELECT count(*) FROM endpoints WHERE project_id = $1", pid)
    return {
        "name": project["name"],
        "health": project["total"],
        "status": status_for(project["total"]),
        "basis": project["basis"],
        "updatedAt": project["computed_at"],
        "monitoredEndpoints": endpoints,
        "uptime": {
            "24h": _pct(uptime["o1"], uptime["t1"]),
            "7d": _pct(uptime["o7"], uptime["t7"]),
            "30d": _pct(uptime["o30"], uptime["t30"]),
        },
        "latency": [{"t": r["t"], "p95": round(r["p95"]) if r["p95"] is not None else None} for r in latency],
        "openIncidents": [
            {"kind": i["kind"], "host": _host(i["url"]), "openedAt": i["opened_at"]} for i in open_incidents
        ],
        "resolvedIncidents": [
            {"kind": i["kind"], "host": _host(i["url"]), "openedAt": i["opened_at"], "closedAt": i["closed_at"]}
            for i in resolved
        ],
    }


@router.get("/public/status/{slug}", dependencies=[Depends(rate_limit("public-status", 60, 60))])
async def public_status(slug: str):
    project = await _public_project(slug)
    if project is None:
        raise HTTPException(404, "This status page doesn't exist or isn't public")
    # Short Redis cache: a popular status page costs one set of queries per 30 s, not one per visitor.
    key = f"public:status:{project['id']}"
    body = await state.redis.get(key)
    if body is None:
        body = json.dumps(jsonable_encoder(await _status_payload(project)))
        await state.redis.set(key, body, ex=STATUS_CACHE_S)
    return Response(
        body,
        media_type="application/json",
        headers={"Cache-Control": f"public, max-age={STATUS_CACHE_S}"},
    )
