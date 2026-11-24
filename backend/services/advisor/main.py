"""Advisor ("Pickle"): advice.requests -> a short brief and at most 3 prioritised recommendations.

How Pickle works:
  1. Rules decide what matters: live incidents first, then findings, most severe first, top 3.
     Each recommendation gets Bento's hand-written guide (why it matters, steps to fix).
  2. A small open model running locally (Ollama, see writer.py) rewrites that plan in friendly,
     student-level words, using only those facts. No hosted AI service, nothing leaves the machine.
  3. If the model is off, slow or gives unusable text, the rule-based text from step 1 is used.

Cached by a hash of the project's open findings + open incidents (+ the model and prompt version):
if nothing changed, the existing advice is kept. Advice written without the model is upgraded once
the model is ready.
"""

import asyncio
import hashlib
import json

import httpx

import writer
from bento_core import streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.guides import guide_for
from bento_core.log import setup_logging

log = setup_logging()

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
MAX_RECOMMENDATIONS = 3
UPGRADE_EVERY_S = 300


def incident_advice(i: dict) -> dict:
    if i["kind"] == "errors":
        return {
            "title": f"Fix the errors on {i['url']}",
            "why": f"It is failing on {round((i['peak'] or 0) * 100)}% of recent checks, so users are affected right now.",
            "steps": ["Open the site yourself to see the error.", "Check your server or hosting logs for the failing requests.",
                      "Roll back the last deploy if it started right after one."],
            "effort_minutes": 30,
            "severity": "critical",
        }
    return {
        "title": f"Find out why {i['url']} slowed down",
        "why": f"It is responding in about {round(i['peak'] or 0)} ms instead of its usual {round(i['baseline'] or 0)} ms.",
        "steps": ["Check whether a recent change or a traffic spike lines up with the slowdown.",
                  "Look at your hosting dashboard for CPU, memory or database limits.",
                  "Find the slowest page or query and fix that first."],
        "effort_minutes": 30,
        "severity": "high",
    }


def finding_advice(f: dict) -> dict:
    guide = guide_for(f["key"])
    return {
        "key": f["key"],
        "title": f["title"],
        "why": guide["why"] if guide else (f["detail"] or ""),
        "steps": guide["steps"] if guide else [],
        "guide": guide,
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
    def __init__(self, pg, http: httpx.AsyncClient | None = None, ollama_url: str = "", model: str = ""):
        self.pg, self.http, self.ollama_url, self.model = pg, http, ollama_url, model

    async def handle(self, batch: list[streams.Message]) -> None:
        for project_id in dict.fromkeys(msg["project_id"] for _, msg in batch):  # coalesce duplicates
            await self.advise(project_id)

    def _version(self) -> str:
        return f"{writer.PROMPT_VERSION}:{self.model}" if self.ollama_url else "rules"

    async def advise(self, project_id, force: bool = False) -> None:
        project = await self.pg.fetchrow("SELECT id, name FROM projects WHERE id = $1", project_id)
        if project is None:
            return
        score = await self.pg.fetchrow(
            "SELECT total, grade, cards, capped FROM project_scores WHERE project_id = $1", project_id
        )
        findings = [dict(r) for r in await self.pg.fetch(
            """SELECT key, severity, title, detail, effort_minutes FROM findings
                WHERE project_id = $1 AND status = 'open'""", project_id)]
        incidents = [dict(r) for r in await self.pg.fetch(
            "SELECT url, kind, baseline, peak FROM incidents WHERE project_id = $1 AND status = 'open'", project_id)]

        digest = hashlib.sha256(json.dumps(
            {"f": sorted((f["key"], f["severity"]) for f in findings), "i": sorted((i["url"], i["kind"]) for i in incidents),
             "v": self._version()}
        ).encode()).hexdigest()
        cached = await self.pg.fetchval("SELECT findings_hash FROM advice WHERE project_id = $1", project_id)
        if cached == digest and not force:
            log.info("advice for %s unchanged (cached by findings hash)", project["name"])
            return

        brief, recommendations = build_advice(project["name"], score["total"] if score else None, findings, incidents)
        source = "rules"
        if self.ollama_url and recommendations and self.http is not None:
            facts = writer.facts_for(project["name"], dict(score) if score else None, recommendations, incidents)
            written = await writer.write(self.http, self.ollama_url, self.model, facts, recommendations)
            if written:
                brief, recommendations = written
                source = f"ai:{self.model}"
        for r in recommendations:
            r.pop("guide", None)  # the API attaches guides to findings itself
        await self.pg.execute(
            """INSERT INTO advice (project_id, findings_hash, brief, recommendations, source, generated_at)
               VALUES ($1, $2, $3, $4, $5, now())
               ON CONFLICT (project_id) DO UPDATE SET findings_hash = $2, brief = $3, recommendations = $4,
                 source = $5, generated_at = now()""",
            project["id"], digest, brief, recommendations, source,
        )
        log.info("advice refreshed for %s (%s)", project["name"], source)

    async def upgrade_loop(self) -> None:
        """Advice written while the model was downloading or down gets rewritten once it's ready."""
        ready_since = None
        while True:
            await asyncio.sleep(UPGRADE_EVERY_S)
            try:
                if not await writer.ready(self.http, self.ollama_url, self.model):
                    ready_since = None
                    continue
                if ready_since is None:
                    ready_since = await self.pg.fetchval("SELECT now()")
                # only advice written before the model was ready: a project the model keeps failing on
                # isn't retried forever
                stale = await self.pg.fetch(
                    """SELECT project_id FROM advice
                        WHERE source = 'rules' AND recommendations <> '[]'::jsonb AND generated_at < $1""",
                    ready_since,
                )
                for row in stale:
                    await self.advise(row["project_id"], force=True)
            except Exception:  # noqa: BLE001
                log.exception("advice upgrade failed")


async def main() -> None:
    pg = await create_pool(settings.database_url)
    r = streams.connect()
    async with httpx.AsyncClient() as http:
        advisor = Advisor(pg, http, settings.ollama_url, settings.pickle_model)
        if settings.ollama_url:
            log.info("Pickle writes with %s via %s (rule-based text as fallback)", settings.pickle_model, settings.ollama_url)
            asyncio.create_task(advisor.upgrade_loop())
        await streams.consume(r, streams.ADVICE_REQUESTS, "advisor", advisor.handle, count=20)


if __name__ == "__main__":
    asyncio.run(main())
