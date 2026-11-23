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


# ---------- README badge ----------

BADGE_COLORS = {"healthy": "#4a7a5c", "degraded": "#a8701c", "critical": "#b8422f", "unknown": "#8a8680"}
BADGE_LABEL = "bento health"
BADGE_LABEL_BG = "#3a3733"


def _text_width(text: str) -> float:
    """Rough Verdana 11px advance widths; textLength in the SVG absorbs the error."""
    width = 0.0
    for ch in text:
        if ch in "ijlI.,:;'|!":
            width += 3.6
        elif ch in "frt()-[] ":
            width += 4.6
        elif ch in "mwMW%":
            width += 10.2
        elif ch.isupper():
            width += 7.6
        elif ch.isdigit():
            width += 7.0
        else:
            width += 6.6
    return width


def render_badge(value: str, status: str) -> str:
    """A shields.io-style flat badge: `bento health | 94`."""
    color = BADGE_COLORS.get(status, BADGE_COLORS["unknown"])
    lt, vt = _text_width(BADGE_LABEL), _text_width(value)
    lw, vw = round(lt + 12), round(vt + 12)
    w = lw + vw
    # Text is drawn at 10x and scaled down, like shields.io, for crisp sub-pixel positioning.
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{BADGE_LABEL}: {value}">
<title>{BADGE_LABEL}: {value}</title>
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="{BADGE_LABEL_BG}"/><rect x="{lw}" width="{vw}" height="20" fill="{color}"/><rect width="{w}" height="20" fill="url(#s)"/></g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
<text aria-hidden="true" x="{lw * 5}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{round(lt * 10)}">{BADGE_LABEL}</text>
<text x="{lw * 5}" y="140" transform="scale(.1)" textLength="{round(lt * 10)}">{BADGE_LABEL}</text>
<text aria-hidden="true" x="{lw * 10 + vw * 5}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{round(vt * 10)}">{value}</text>
<text x="{lw * 10 + vw * 5}" y="140" transform="scale(.1)" textLength="{round(vt * 10)}">{value}</text>
</g>
</svg>"""


@router.get("/badge/{slug}.svg", dependencies=[Depends(rate_limit("badge", 240, 60))])
async def badge(slug: str):
    # Never 404: a README embed should show a grey "unknown" badge, not a broken image.
    project = await _public_project(slug)
    total = project["total"] if project else None
    status = status_for(total)
    value = str(total) if total is not None else "unknown"
    cache = "public, max-age=300, s-maxage=300, stale-while-revalidate=600" if project else "public, max-age=60"
    return Response(
        render_badge(value, status),
        media_type="image/svg+xml",
        headers={"Cache-Control": cache, "X-Content-Type-Options": "nosniff"},
    )
