"""AI advisor ("Pickle"): advice.requests -> short, prioritised recommendations per project.

* Cached by a hash of the project's open findings + open incidents: unchanged inputs, no LLM call.
* Circuit breaker: 5 consecutive LLM failures open the circuit for 60 s (rule-based advice is
  served meanwhile, scores keep updating); then one half-open trial call decides.
* Without ANTHROPIC_API_KEY the advisor runs on rules only.
"""

import asyncio
import hashlib
import json
import time

import anthropic
from pydantic import BaseModel, Field

from bento_core import streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.log import setup_logging
from bento_core.scoring import status_for

log = setup_logging()

MODEL = "claude-opus-5-5"
FAILURES_TO_OPEN = 5
OPEN_FOR_S = 60
RETRY_AFTER_S = 10
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

SYSTEM = """You are Pickle, the engineering assistant inside Bento. Bento watches a developer's projects
and tells them what deserves attention. You receive one project's health score, open findings from
static repository scans, and open runtime incidents.

Write like a calm, experienced teammate who already read the logs:
- Explain, prioritise, suggest. Never overwhelm.
- Plain language; no jargon the developer would have to look up.
- At most 3 recommendations, most important first. Each must be a concrete next action.
- Base everything on the data given. Do not invent issues, numbers, or tools that are not in the input.
- If nothing is wrong, say so briefly and recommend nothing."""


class Recommendation(BaseModel):
    title: str = Field(description="Short imperative action, e.g. 'Upgrade lodash to a patched version'")
    why: str = Field(description="One sentence on the consequence of leaving it")
    effort_minutes: int = Field(description="Realistic estimate in minutes")
    severity: str = Field(description="critical, high, medium or low")


class Advice(BaseModel):
    brief: str = Field(description="Two sentences at most: the state of this project and what to do first")
    recommendations: list[Recommendation]


class CircuitBreaker:
    def __init__(self, r):
        self.r = r
        self.state = "closed"
        self.failures = 0
        self.open_until = 0.0

    def allow(self) -> bool:
        if self.state == "open" and time.monotonic() >= self.open_until:
            self.state = "half-open"
            log.info("advisor circuit half-open: one trial call allowed")
        return self.state != "open"

    async def success(self) -> None:
        if self.state != "closed":
            log.info("advisor trial call succeeded: circuit closed")
        self.state, self.failures = "closed", 0
        await self.r.set("advisor:circuit", self.state)

    async def failure(self) -> None:
        self.failures += 1
        if self.state == "half-open" or self.failures >= FAILURES_TO_OPEN:
            self.state, self.open_until = "open", time.monotonic() + OPEN_FOR_S
            log.warning("advisor circuit OPEN after %d failures: skipping LLM calls for %ds", self.failures, OPEN_FOR_S)
        await self.r.set("advisor:circuit", self.state)


def rules_advice(name: str, score: int | None, findings: list, incidents: list) -> Advice:
    recs = [
        Recommendation(
            title=f"Fix {i['kind']} on {i['url']}",
            why="It is live right now and users are affected.",
            effort_minutes=30,
            severity="critical" if i["kind"] == "errors" else "high",
        )
        for i in incidents
    ] + [
        Recommendation(title=f["title"], why=f["detail"] or "", effort_minutes=f["effort_minutes"] or 30, severity=f["severity"])
        for f in findings
    ]
    recs.sort(key=lambda r: SEVERITY_RANK.get(r.severity, 9))
    if not recs:
        brief = f"{name} looks {'healthy' if (score or 100) >= 80 else 'stable'}. Nothing needs your attention."
    else:
        brief = f"{name} has {len(recs)} open issue{'s' if len(recs) != 1 else ''}. Start with: {recs[0].title.rstrip('.')}."
    return Advice(brief=brief, recommendations=recs[:3])


class Advisor:
    def __init__(self, pg, r):
        self.pg, self.r = pg, r
        self.breaker = CircuitBreaker(r)
        self.client = anthropic.AsyncAnthropic(max_retries=1, timeout=90) if settings.anthropic_api_key else None
        if not self.client:
            log.info("ANTHROPIC_API_KEY not set: advisor runs on rule-based advice only")

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
        cached = await self.pg.fetchrow("SELECT findings_hash, source FROM advice WHERE project_id = $1", project_id)
        if cached and cached["findings_hash"] == digest and (cached["source"] == "ai" or self.client is None):
            log.info("advice for %s unchanged (cached by findings hash)", project["name"])
            return

        advice, source = None, "rules"
        if self.client and self.breaker.allow():
            try:
                advice = await self.ask_claude(project["name"], score, findings, incidents)
                source = "ai"
                await self.breaker.success()
            except (anthropic.APIStatusError, anthropic.APIConnectionError, ValueError) as exc:
                log.warning("LLM call failed (%s); serving rule-based advice", exc.__class__.__name__)
                await self.breaker.failure()
                if self.breaker.state != "open":
                    asyncio.create_task(self.retry_later(project_id))
        if advice is None:
            advice = rules_advice(project["name"], score, findings, incidents)

        await self.pg.execute(
            """INSERT INTO advice (project_id, findings_hash, brief, recommendations, source, generated_at)
               VALUES ($1, $2, $3, $4, $5, now())
               ON CONFLICT (project_id) DO UPDATE SET findings_hash = $2, brief = $3, recommendations = $4,
                 source = $5, generated_at = now()""",
            project["id"],
            digest if source == "ai" or self.client is None else None,  # rules fallback is retried later
            advice.brief,
            [rec.model_dump() for rec in advice.recommendations],
            source,
        )
        log.info("advice refreshed for %s (%s)", project["name"], source)

    async def retry_later(self, project_id: str) -> None:
        await asyncio.sleep(RETRY_AFTER_S)
        await streams.publish(self.r, streams.ADVICE_REQUESTS, {"project_id": project_id})

    async def ask_claude(self, name: str, score: int | None, findings: list, incidents: list) -> Advice:
        payload = {
            "project": name,
            "health_score": score,
            "health_status": status_for(score),
            "open_findings": [{k: f[k] for k in ("severity", "title", "detail", "effort_minutes")} for f in findings],
            "open_incidents": [
                {"url": i["url"], "kind": i["kind"], "baseline": round(i["baseline"] or 0, 2), "peak": round(i["peak"] or 0, 2)}
                for i in incidents
            ],
        }
        response = await self.client.messages.parse(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": f"Project data:\n{json.dumps(payload, indent=2)}"}],
            output_format=Advice,
            output_config={"effort": "low"},
            # If a safety classifier declines, the API retries on Anthropic's recommended fallback model.
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"},
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise ValueError(f"no usable advice (stop_reason={response.stop_reason})")
        advice = response.parsed_output
        advice.recommendations = advice.recommendations[:3]
        return advice


async def main() -> None:
    pg = await create_pool(settings.database_url)
    r = streams.connect()
    await r.set("advisor:circuit", "closed")
    await streams.consume(r, streams.ADVICE_REQUESTS, "advisor", Advisor(pg, r).handle, count=20)


if __name__ == "__main__":
    asyncio.run(main())
