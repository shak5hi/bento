"""GitHub push webhooks -> scan.jobs. Every delivery is HMAC-verified.

GitHub retries deliveries; we enqueue each one and the scanner skips commits it has
already scanned (dedupe by commit SHA), so retries are harmless.
"""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from bento_core import streams
from bento_core.config import settings

from ..state import state

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _valid_signature(body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(settings.github_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@router.post("/github", status_code=202)
async def github(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
):
    if not settings.github_webhook_secret:
        raise HTTPException(503, "GITHUB_WEBHOOK_SECRET is not configured")
    body = await request.body()
    if not _valid_signature(body, x_hub_signature_256):
        raise HTTPException(401, "Invalid signature")

    if x_github_event == "ping":
        return {"ok": True, "pong": True}
    payload = json.loads(body)
    if x_github_event in ("installation", "installation_repositories"):
        return await _installation_event(x_github_event, payload)
    if x_github_event != "push":
        return {"ok": True, "ignored": x_github_event}

    full_name = (payload.get("repository", {}).get("full_name") or "").lower()
    sha = payload.get("after")
    if not full_name or not sha or set(sha) == {"0"}:  # branch deletion
        return {"ok": True, "ignored": "no commit"}

    rows = await state.pg.fetch("SELECT id FROM projects WHERE repo_full_name = $1", full_name)
    for row in rows:
        await streams.publish(
            state.redis,
            streams.SCAN_JOBS,
            {"project_id": str(row["id"]), "sha": sha, "delivery": x_github_delivery or "github"},
        )
    log.info("push %s@%s (delivery %s) -> %d scan job(s)", full_name, sha[:7], x_github_delivery, len(rows))
    return {"ok": True, "queued": len(rows)}


async def _installation_event(event: str, payload: dict) -> dict:
    """Keep access in sync when the Bento app is uninstalled or loses repositories."""
    inst_id = payload.get("installation", {}).get("id")
    action = payload.get("action")
    if event == "installation" and action == "deleted":
        await state.pg.execute("UPDATE projects SET installation_id = NULL WHERE installation_id = $1", inst_id)
        await state.pg.execute("DELETE FROM github_installations WHERE id = $1", inst_id)
        log.info("installation %s deleted", inst_id)
    elif event == "installation_repositories" and action == "removed":
        names = [r["full_name"].lower() for r in payload.get("repositories_removed", [])]
        await state.pg.execute(
            "UPDATE projects SET installation_id = NULL WHERE installation_id = $1 AND repo_full_name = ANY($2::text[])",
            inst_id, names,
        )
    return {"ok": True, "event": event, "action": action}
