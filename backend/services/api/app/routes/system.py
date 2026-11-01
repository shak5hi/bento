"""Health of the whole pipeline: databases, Redis, every worker, every queue."""

import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from bento_core import streams

from ..security import current_user_id
from ..state import state

router = APIRouter(tags=["system"])

WORKERS = ["scheduler", "prober", "analyzer", "notifier", "scanner", "advisor"]
QUEUES = {
    streams.PROBE_JOBS: "probers",
    streams.PROBE_RESULTS: "analyzer",
    streams.ALERTS: "notifier",
    streams.SCAN_JOBS: "scanner",
    streams.ADVICE_REQUESTS: "advisor",
}


@router.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}


async def _check(coro) -> str:
    try:
        await coro
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


@router.get("/api/system", dependencies=[Depends(current_user_id)])
async def system_for_dashboard():
    """Same data for the signed-in dashboard (nginx only exposes /api/* to the browser).
    Always 200: a degraded pipeline is information to show, not a failed request."""
    return await _collect()


@router.get("/health/services")
async def services():
    """For load balancers and uptime checks: 503 when anything is down."""
    content = await _collect()
    return JSONResponse(status_code=200 if content["status"] == "ok" else 503, content=content)


async def _collect() -> dict:
    deps = {
        "postgres": await _check(state.pg.fetchval("SELECT 1")),
        "timescaledb": await _check(state.ts.fetchval("SELECT 1")),
        "redis": await _check(state.redis.ping()),
    }

    now = int(time.time())
    workers: dict[str, dict] = {}
    for name in WORKERS:
        keys = [k async for k in state.redis.scan_iter(f"heartbeat:{name}:*")]
        beats = [int(v) for v in await state.redis.mget(keys)] if keys else []
        alive = sum(1 for b in beats if now - b < 30)
        workers[name] = {"instances": alive, "status": "ok" if alive else "down"}

    queues: dict[str, dict] = {}
    for stream, group in QUEUES.items():
        try:
            info = next((g for g in await state.redis.xinfo_groups(stream) if g["name"] == group), None)
            queues[stream] = {"waiting": info.get("lag") or 0, "unacked": info["pending"]} if info else {"waiting": 0, "unacked": 0}
        except Exception:  # noqa: BLE001 - stream not created yet
            queues[stream] = {"waiting": 0, "unacked": 0}

    circuit = await state.redis.get("advisor:circuit") or "closed"
    alerts = {
        "sent": int(await state.redis.get("stats:alerts_sent") or 0),
        "suppressed": int(await state.redis.get("stats:alerts_suppressed") or 0),
    }

    healthy = all(v == "ok" for v in deps.values()) and all(w["status"] == "ok" for w in workers.values())
    return {
        "status": "ok" if healthy else "degraded",
        "dependencies": deps,
        "workers": workers,
        "queues": queues,
        "advisorCircuit": circuit,
        "alerts": alerts,
    }
