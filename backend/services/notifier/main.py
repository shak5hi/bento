"""Notifier: alerts stream -> in-app notifications (+ Slack when configured).

The analyzer re-emits an alert for every breaching probe while an incident is open. The notifier
sends the first one and suppresses repeats for a 30-minute cooldown, so one incident = one ping.
"""

import asyncio

import httpx

from bento_core import streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.log import setup_logging

log = setup_logging()
COOLDOWN_S = 1800


def _describe(a: dict) -> tuple[str, str]:
    if a["kind"] == "latency":
        detail = f"{a['url']} at {round(a['value'])} ms (normally ~{round(a['baseline'])} ms)"
        title = "Latency incident" if a["type"] == "open" else "Latency back to normal"
    else:
        detail = f"{a['url']} failing on {round(a['value'] * 100)}% of recent probes"
        title = "Error incident" if a["type"] == "open" else "Errors resolved"
    return title, detail


class Notifier:
    def __init__(self, pg, r, http: httpx.AsyncClient):
        self.pg, self.r, self.http = pg, r, http

    async def handle(self, batch: list[streams.Message]) -> None:
        for _, alert in batch:
            await self.deliver(alert)

    async def deliver(self, a: dict) -> None:
        key = f"notify:{a['endpoint_id']}:{a['kind']}"
        if a["type"] == "open":
            if not await self.r.set(key, a["incident_id"], nx=True, ex=COOLDOWN_S):
                await self.r.incr("stats:alerts_suppressed")
                return
        else:
            await self.r.delete(key)

        title, body = _describe(a)
        project = await self.pg.fetchval("SELECT name FROM projects WHERE id = $1", a["project_id"])
        await self.pg.execute(
            "INSERT INTO notifications (owner_id, project_id, kind, title, body) VALUES ($1, $2, $3, $4, $5)",
            a["owner_id"], a["project_id"], "incident" if a["type"] == "open" else "resolved", title, body,
        )
        await self.r.incr("stats:alerts_sent")
        log.info("[%s] %s — %s: %s", "ALERT" if a["type"] == "open" else "RESOLVED", project, title, body)

        if settings.slack_webhook_url:
            icon = ":red_circle:" if a["type"] == "open" else ":large_green_circle:"
            try:
                resp = await self.http.post(settings.slack_webhook_url, json={"text": f"{icon} *{project}* — {title}\n{body}"})
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                log.warning("slack delivery failed: %s", exc)  # in-app notification already stored


async def main() -> None:
    pg = await create_pool(settings.database_url)
    r = streams.connect()
    async with httpx.AsyncClient(timeout=10) as http:
        await streams.consume(r, streams.ALERTS, "notifier", Notifier(pg, r, http).handle, count=50)


if __name__ == "__main__":
    asyncio.run(main())
