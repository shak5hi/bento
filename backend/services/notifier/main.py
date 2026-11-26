"""Notifier: alerts stream -> in-app notifications (+ email and Slack when configured), and the weekly digest.

The analyzer re-emits an alert for every breaching probe while an incident is open. The notifier
sends the first one and suppresses repeats for a 30-minute cooldown, so one incident = one ping
(and at most one email). Every Monday morning (DIGEST_TIMEZONE / DIGEST_HOUR) each user with the
digest switched on gets one summary email; a user's week is claimed in the database first, so
restarts or several notifier replicas never send it twice.

New accounts get a welcome email with their first portfolio report as soon as the projects they added
have been scanned (or after 15 minutes, whichever is first); claimed in the database the same way.
"""

import asyncio
from datetime import datetime, timezone

import httpx

import digest
from bento_core import mail, streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.log import setup_logging

log = setup_logging()
COOLDOWN_S = 1800
DIGEST_CHECK_S = 600
WELCOME_CHECK_S = 60


def _describe(a: dict) -> tuple[str, str]:
    if a["kind"] == "latency":
        detail = f"{a['url']} at {round(a['value'])} ms (normally ~{round(a['baseline'])} ms)"
        title = "Latency incident" if a["type"] == "open" else "Latency back to normal"
    else:
        detail = f"{a['url']} failing on {round(a['value'] * 100)}% of recent probes"
        title = "Error incident" if a["type"] == "open" else "Errors resolved"
    return title, detail


class Notifier:
    def __init__(self, pg, r, http: httpx.AsyncClient, ts=None):
        self.pg, self.r, self.http, self.ts = pg, r, http, ts

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

        await self.email_incident(a, project, title, body)

        if settings.slack_webhook_url:
            icon = ":red_circle:" if a["type"] == "open" else ":large_green_circle:"
            try:
                resp = await self.http.post(settings.slack_webhook_url, json={"text": f"{icon} *{project}* — {title}\n{body}"})
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                log.warning("slack delivery failed: %s", exc)  # in-app notification already stored


    async def email_incident(self, a: dict, project: str, title: str, body: str) -> None:
        user = await self.pg.fetchrow("SELECT email, email_incidents FROM users WHERE id = $1", a["owner_id"])
        if user is None or not user["email_incidents"]:
            return
        unsubscribe = mail.unsubscribe_url(a["owner_id"], "incidents")
        subject, html_body, text = mail.incident_email(project or "Your project", title, body, a["type"] == "open", unsubscribe)
        await mail.send(self.http, user["email"], subject, html_body, text, unsubscribe)

    async def digest_loop(self) -> None:
        while True:
            try:
                await self.send_digests(datetime.now(timezone.utc))
            except Exception:  # noqa: BLE001
                log.exception("weekly digest failed")
            await asyncio.sleep(DIGEST_CHECK_S)

    async def send_digests(self, now: datetime) -> int:
        week = digest.due_week(now, settings.digest_timezone, settings.digest_hour)
        if week is None:
            return 0
        if not mail.configured():
            if await self.r.set(f"digest:skipped:{week}", "1", nx=True, ex=8 * 86400):
                log.info("weekly digest skipped (RESEND_API_KEY not set)")
            return 0
        sent = 0
        users = await self.pg.fetch(
            "SELECT id, email FROM users WHERE email_digest AND last_digest_week IS DISTINCT FROM $1", week
        )
        for u in users:
            # claim this user's week before sending: never twice, even with restarts or several notifiers
            claimed = await self.pg.fetchval(
                """UPDATE users SET last_digest_week = $2 WHERE id = $1 AND last_digest_week IS DISTINCT FROM $2
                   RETURNING id""",
                u["id"], week,
            )
            if not claimed or not mail.deliverable(u["email"]):
                continue
            content = await digest.build(self.pg, self.ts, u["id"])
            if content is None:
                continue
            unsubscribe = mail.unsubscribe_url(u["id"], "digest")
            subject, html_body, text = mail.digest_email(content, unsubscribe)
            sent += await mail.send(self.http, u["email"], subject, html_body, text, unsubscribe)
        if users:
            log.info("weekly digest %s: %d sent", week, sent)
        return sent


    async def welcome_loop(self) -> None:
        while True:
            try:
                await self.send_welcomes()
            except Exception:  # noqa: BLE001
                log.exception("welcome emails failed")
            await asyncio.sleep(WELCOME_CHECK_S)

    async def send_welcomes(self) -> int:
        """First portfolio report for new accounts, once their projects are scanned. Never sent twice."""
        if not mail.configured():
            return 0
        # Ready: has projects, every repo has had its first scan (plus a minute for Pickle's advice),
        # or the first project was added 15+ minutes ago (a repo that can't be scanned shouldn't block it).
        users = await self.pg.fetch(
            """SELECT u.id, u.email FROM users u
                WHERE u.welcome_due AND u.email_digest
                  AND EXISTS (SELECT 1 FROM projects p WHERE p.owner_id = u.id)
                  AND (
                    (SELECT min(created_at) FROM projects p WHERE p.owner_id = u.id) < now() - interval '15 minutes'
                    OR (NOT EXISTS (SELECT 1 FROM projects p WHERE p.owner_id = u.id
                                     AND p.repo_url IS NOT NULL AND p.last_scan_at IS NULL)
                        AND COALESCE((SELECT max(last_scan_at) FROM projects p WHERE p.owner_id = u.id),
                                     (SELECT max(created_at) FROM projects p WHERE p.owner_id = u.id))
                            < now() - interval '1 minute'))"""
        )
        sent = 0
        for u in users:
            claimed = await self.pg.fetchval(
                "UPDATE users SET welcome_due = false WHERE id = $1 AND welcome_due RETURNING id", u["id"]
            )
            if not claimed or not mail.deliverable(u["email"]):
                continue
            content = await digest.build(self.pg, self.ts, u["id"])
            if content is None:
                continue
            unsubscribe = mail.unsubscribe_url(u["id"], "digest")
            subject, html_body, text = mail.digest_email(content, unsubscribe, welcome=True)
            ok = await mail.send(self.http, u["email"], subject, html_body, text, unsubscribe)
            sent += ok
            log.info("welcome email for %s: %s", u["id"], "sent" if ok else "not sent")
        return sent


async def main() -> None:
    pg = await create_pool(settings.database_url)
    ts = await create_pool(settings.timescale_url)
    r = streams.connect()
    async with httpx.AsyncClient(timeout=10) as http:
        notifier = Notifier(pg, r, http, ts)
        asyncio.create_task(notifier.digest_loop())
        asyncio.create_task(notifier.welcome_loop())
        await streams.consume(r, streams.ALERTS, "notifier", notifier.handle, count=50)


if __name__ == "__main__":
    asyncio.run(main())
