"""The weekly digest: what changed across a user's projects in the last 7 days. Rule-based."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bento_core.guides import plain

SEVERITY_ORDER = ("critical", "high", "medium", "low")


def due_week(now_utc: datetime, tz_name: str, hour: int) -> str | None:
    """The ISO week (e.g. '2026-W48') if it's Monday at or after `hour` local time, else None."""
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    local = now_utc.astimezone(tz)
    if local.isoweekday() != 1 or local.hour < hour:
        return None
    year, week, _ = local.isocalendar()
    return f"{year}-W{week:02d}"


async def build(pg, ts, user_id) -> dict | None:
    """Digest content for one user, or None if they have no projects."""
    projects = await pg.fetch(
        """SELECT p.id, p.name, s.total, s.grade FROM projects p LEFT JOIN project_scores s ON s.project_id = p.id
            WHERE p.owner_id = $1 ORDER BY s.total NULLS LAST, p.name""",
        user_id,
    )
    if not projects:
        return None
    week_ago = {
        r["project_id"]: r["total"]
        for r in await ts.fetch(
            """SELECT DISTINCT ON (project_id) project_id, total FROM project_health
                WHERE owner_id = $1 AND time > now() - interval '7 days' ORDER BY project_id, time""",
            user_id,
        )
    }
    rows = [
        {"name": p["name"], "health": p["total"], "grade": p["grade"],
         "change": (p["total"] - week_ago[p["id"]]) if p["total"] is not None and p["id"] in week_ago else None}
        for p in projects
    ]
    scored = [r["health"] for r in rows if r["health"] is not None]
    then = [week_ago[p["id"]] for p in projects if p["id"] in week_ago and p["total"] is not None]
    health = round(sum(scored) / len(scored)) if scored else None
    change = (health - round(sum(then) / len(then))) if health is not None and then else None

    new = await pg.fetch(
        """SELECT f.key, f.meta, f.title, f.severity, p.name FROM findings f JOIN projects p ON p.id = f.project_id
            WHERE p.owner_id = $1 AND f.status = 'open' AND f.first_seen > now() - interval '7 days'""",
        user_id,
    )
    resolved = await pg.fetch(
        """SELECT f.key, f.meta, f.title, f.severity, p.name FROM findings f JOIN projects p ON p.id = f.project_id
            WHERE p.owner_id = $1 AND f.status = 'resolved' AND f.resolved_at > now() - interval '7 days'""",
        user_id,
    )
    # Pickle's top 3: its recommendations across all projects, most severe first
    recs = []
    for a in await pg.fetch(
        "SELECT a.recommendations, p.name FROM advice a JOIN projects p ON p.id = a.project_id WHERE p.owner_id = $1",
        user_id,
    ):
        for r in a["recommendations"] or []:
            recs.append({"title": r.get("title", ""), "why": r.get("why"), "project": a["name"],
                         "severity": r.get("severity", "low")})
    rank = lambda x: SEVERITY_ORDER.index(x["severity"]) if x["severity"] in SEVERITY_ORDER else 9  # noqa: E731
    recs.sort(key=rank)

    def listed(found):
        return sorted(({"title": plain(f["key"], f["title"], None, f["meta"])[0], "project": f["name"], "severity": f["severity"]}
                       for f in found), key=rank)

    return {"health": health, "change": change, "projects": rows, "new": listed(new), "resolved": listed(resolved),
            "top": recs[:3]}
