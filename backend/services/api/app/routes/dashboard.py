"""The home screen: five questions, one response.

1. How healthy is my portfolio?      -> portfolio.health
2. Which projects need attention?    -> projects (sorted worst first)
3. What's the biggest risk?          -> biggestRisk
4. What should I work on today?      -> today (max 3 tasks, never a wall of alerts)
5. How is my engineering improving?  -> portfolio.trend
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from bento_core.scoring import status_for

from ..security import current_user_id
from ..state import state

router = APIRouter(prefix="/api", tags=["dashboard"])

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _label(health: int | None) -> str:
    if health is None:
        return "waiting for data"
    return {"healthy": "healthy", "degraded": "under strain", "critical": "at risk"}[status_for(health)]


def _brief(health, projects, tasks, risk) -> str:
    if not projects:
        return "Add your first project and Pickle will start watching it — uptime, latency, errors and code health."
    parts = [f"Your portfolio looks {_label(health)} today."]
    issues = len(tasks)
    if risk is None:
        parts.append("Nothing needs your attention right now.")
    else:
        if issues > 3:
            parts.append(f"Pickle reviewed {issues} open issues and picked the three that matter most.")
        else:
            parts.append(f"Pickle found {issues} thing{'s' if issues != 1 else ''} worth your time.")
        parts.append(f"The biggest risk is {risk['title'].rstrip('.').lower()} in {risk['projectName']}.")
        parts.append(f"Today's focus should be {risk['projectName']}.")
    return " ".join(parts)


@router.get("/dashboard")
async def dashboard(user_id: UUID = Depends(current_user_id)):
    user = await state.pg.fetchrow("SELECT name, email FROM users WHERE id = $1", user_id)

    projects = await state.pg.fetch(
        """SELECT p.id, p.name, p.repo_url, p.last_scan_at, s.total, s.basis,
                  (SELECT count(*) FROM endpoints e WHERE e.project_id = p.id)                         AS endpoints,
                  (SELECT count(*) FROM incidents i WHERE i.project_id = p.id AND i.status = 'open')    AS open_incidents,
                  (SELECT count(*) FROM findings f WHERE f.project_id = p.id AND f.status = 'open')     AS open_findings
             FROM projects p LEFT JOIN project_scores s ON s.project_id = p.id
            WHERE p.owner_id = $1""",
        user_id,
    )

    findings = await state.pg.fetch(
        """SELECT f.id, f.project_id, p.name AS project_name, f.severity, f.title, f.detail, f.effort_minutes, f.first_seen
             FROM findings f JOIN projects p ON p.id = f.project_id
            WHERE p.owner_id = $1 AND f.status = 'open'""",
        user_id,
    )
    incidents = await state.pg.fetch(
        """SELECT i.id, i.project_id, p.name AS project_name, i.kind, i.url, i.baseline, i.peak, i.opened_at
             FROM incidents i JOIN projects p ON p.id = i.project_id
            WHERE p.owner_id = $1 AND i.status = 'open'""",
        user_id,
    )
    advice = await state.pg.fetch(
        """SELECT a.project_id, a.brief, a.recommendations, a.generated_at
             FROM advice a JOIN projects p ON p.id = a.project_id WHERE p.owner_id = $1""",
        user_id,
    )

    # Live incidents outrank static findings of the same severity.
    tasks = [
        {
            "id": str(i["id"]),
            "kind": "incident",
            "projectId": str(i["project_id"]),
            "projectName": i["project_name"],
            "severity": "critical" if i["kind"] == "errors" else "high",
            "title": "Errors spiking" if i["kind"] == "errors" else "Latency well above baseline",
            "detail": (
                f"{i['url']} — peak {round(i['peak'] or 0)} ms vs {round(i['baseline'] or 0)} ms normal."
                if i["kind"] == "latency"
                else f"{i['url']} is failing ({round((i['peak'] or 0) * 100)}% of recent probes)."
            ),
            "effortMinutes": None,
            "since": i["opened_at"],
        }
        for i in incidents
    ] + [
        {
            "id": str(f["id"]),
            "kind": "finding",
            "projectId": str(f["project_id"]),
            "projectName": f["project_name"],
            "severity": f["severity"],
            "title": f["title"],
            "detail": f["detail"],
            "effortMinutes": f["effort_minutes"],
            "since": f["first_seen"],
        }
        for f in findings
    ]
    tasks.sort(key=lambda t: (SEVERITY_RANK[t["severity"]], t["kind"] != "incident", t["since"]))

    scored = [p["total"] for p in projects if p["total"] is not None]
    health = round(sum(scored) / len(scored)) if scored else None

    trend = await state.ts.fetch(
        """SELECT time_bucket('6 hours', time) AS t, round(avg(total))::int AS health
             FROM project_health WHERE owner_id = $1 AND time > now() - interval '14 days'
            GROUP BY t ORDER BY t""",
        user_id,
    )

    project_list = sorted(
        (
            {
                "id": str(p["id"]),
                "name": p["name"],
                "repoUrl": p["repo_url"],
                "health": p["total"],
                "basis": p["basis"],
                "status": status_for(p["total"]),
                "endpoints": p["endpoints"],
                "openIncidents": p["open_incidents"],
                "openFindings": p["open_findings"],
                "lastScanAt": p["last_scan_at"],
            }
            for p in projects
        ),
        key=lambda p: (p["health"] is None, p["health"] if p["health"] is not None else 0),
    )

    risk = tasks[0] if tasks else None
    notes = await state.pg.fetch(
        """SELECT n.kind, n.title, n.body, n.created_at, p.name AS project_name
             FROM notifications n LEFT JOIN projects p ON p.id = n.project_id
            WHERE n.owner_id = $1 ORDER BY n.created_at DESC LIMIT 12""",
        user_id,
    )

    return {
        "user": {"name": user["name"], "email": user["email"]},
        "brief": _brief(health, project_list, tasks, risk),
        "portfolio": {
            "health": health,
            "label": _label(health),
            "projects": len(project_list),
            "needsAttention": sum(1 for p in project_list if p["status"] in ("degraded", "critical")),
            "openIncidents": len(incidents),
            "openFindings": len(findings),
            "trend": [{"t": r["t"], "health": r["health"]} for r in trend],
        },
        "biggestRisk": risk,
        "today": tasks[:3],
        "projects": project_list,
        "pickle": [
            {
                "projectId": str(a["project_id"]),
                "brief": a["brief"],
                "recommendations": a["recommendations"],
                "generatedAt": a["generated_at"],
            }
            for a in advice
        ],
        "activity": [
            {"kind": n["kind"], "title": n["title"], "body": n["body"], "at": n["created_at"], "projectName": n["project_name"]}
            for n in notes
        ],
    }
