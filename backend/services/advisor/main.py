"""Advisor ("Pickle"): advice.requests -> a short brief and at most 3 prioritised recommendations.

Pickle is rule-based: it ranks a project's open incidents and code findings by severity and
writes plain-language advice from them. No external AI service is used.

Cached by a hash of the project's open findings + open incidents: if nothing changed, the
existing advice is kept.
"""

import asyncio
import hashlib
import json

from bento_core import streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.log import setup_logging

log = setup_logging()

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
MAX_RECOMMENDATIONS = 3


def incident_advice(i: dict) -> dict:
    if i["kind"] == "errors":
        return {
            "title": f"Fix the errors on {i['url']}",
            "why": f"It is failing on {round((i['peak'] or 0) * 100)}% of recent checks, so users are affected right now.",
            "effort_minutes": 30,
            "severity": "critical",
        }
    return {
        "title": f"Find out why {i['url']} slowed down",
        "why": f"It is responding in about {round(i['peak'] or 0)} ms instead of its usual {round(i['baseline'] or 0)} ms.",
        "effort_minutes": 30,
        "severity": "high",
    }


def finding_advice(f: dict) -> dict:
    return {
        "title": f["title"],
        "why": f["detail"] or "",
        "effort_minutes": f["effort_minutes"] or 30,
        "severity": f["severity"],
    }


def build_advice(name: str, score: int | None, findings: list[dict], incidents: list[dict]) -> tuple[str, list[dict]]:
    # Live incidents first, then code findings; most severe first within each.
    recs = sorted((incident_advice(i) for i in incidents), key=lambda r: SEVERITY_RANK[r["severity"]])
    recs += sorted((finding_advice(f) for f in findings), key=lambda r: SEVERITY_RANK.get(r["severity"], 9))

    if not recs:
        label = "healthy" if score is None or score >= 80 else "stable"
        return f"{name} looks {label}. Nothing needs your attention right now.", []

    total = len(recs)
    first = recs[0]["title"].rstrip(".")
    if incidents:
        brief = f"{name} has a live problem. Start with: {first}."
    else:
        brief = f"{name} has {total} open issue{'s' if total != 1 else ''}. Start with: {first}."
    if total > MAX_RECOMMENDATIONS:
        brief += f" The other {total - MAX_RECOMMENDATIONS} can wait."
    return brief, recs[:MAX_RECOMMENDATIONS]


class Advisor:
    def __init__(self, pg):
        self.pg = pg

    async def handle(self, batch: list[streams.Message]) -> None:
        for project_id in dict.fromkeys(msg["project_id"] for _, msg in batch):  # coalesce duplicates
            await self.advise(project_id)

    async def advise(self, project_id: str) -> None:
        project = await self.pg.fetchrow("SELECT id, name FROM projects WHERE id = $1", project_id)
        if project is None:
            return
        score = await self.pg.fetchval("SELECT total FROM project_scores WHERE project_id = $1", project_id)
        findings = [dict(r) for r in await self.pg.fetch(
            """SELECT key, severity, title, detail, effort_minutes FROM findings
                WHERE project_id = $1 AND status = 'open'""", project_id)]
        incidents = [dict(r) for r in await self.pg.fetch(
            "SELECT url, kind, baseline, peak FROM incidents WHERE project_id = $1 AND status = 'open'", project_id)]

        digest = hashlib.sha256(json.dumps(
            {"f": sorted((f["key"], f["severity"]) for f in findings), "i": sorted((i["url"], i["kind"]) for i in incidents)}
        ).encode()).hexdigest()
        cached = await self.pg.fetchval("SELECT findings_hash FROM advice WHERE project_id = $1", project_id)
        if cached == digest:
            log.info("advice for %s unchanged (cached by findings hash)", project["name"])
            return

        brief, recommendations = build_advice(project["name"], score, findings, incidents)
        await self.pg.execute(
            """INSERT INTO advice (project_id, findings_hash, brief, recommendations, source, generated_at)
               VALUES ($1, $2, $3, $4, 'rules', now())
               ON CONFLICT (project_id) DO UPDATE SET findings_hash = $2, brief = $3, recommendations = $4,
                 source = 'rules', generated_at = now()""",
            project["id"], digest, brief, recommendations,
        )
        log.info("advice refreshed for %s", project["name"])


async def main() -> None:
    pg = await create_pool(settings.database_url)
    r = streams.connect()
    await streams.consume(r, streams.ADVICE_REQUESTS, "advisor", Advisor(pg).handle, count=20)


if __name__ == "__main__":
    asyncio.run(main())
