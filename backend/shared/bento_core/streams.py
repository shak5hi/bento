"""Redis Streams helpers: at-least-once delivery with consumer groups and redelivery.

A worker that dies mid-batch never acks; after CLAIM_IDLE_MS its jobs are claimed by a
healthy consumer (XAUTOCLAIM), so nothing is lost.
"""

import asyncio
import json
import logging
import os
import socket
import time
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis
from redis.exceptions import ResponseError

from .config import settings

log = logging.getLogger(__name__)

# Stream names (match the architecture diagram)
PROBE_JOBS = "probe.jobs"
PROBE_RESULTS = "probe.results"
ALERTS = "alerts"
SCAN_JOBS = "scan.jobs"
ADVICE_REQUESTS = "advice.requests"
FIX_JOBS = "fix.jobs"

CLAIM_IDLE_MS = 30_000
MAXLEN = 200_000

Message = tuple[str, dict[str, Any]]
BatchHandler = Callable[[list[Message]], Awaitable[None]]


def connect() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def consumer_name() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


async def publish(r: redis.Redis, stream: str, payload: dict[str, Any]) -> str:
    return await r.xadd(stream, {"data": json.dumps(payload, default=str)}, maxlen=MAXLEN, approximate=True)


async def ensure_group(r: redis.Redis, stream: str, group: str) -> None:
    try:
        await r.xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def _decode(entries: list) -> list[Message]:
    out: list[Message] = []
    for msg_id, fields in entries or []:
        if fields and "data" in fields:
            out.append((msg_id, json.loads(fields["data"])))
    return out


async def heartbeat(r: redis.Redis, name: str) -> None:
    """Workers report liveness; the API gateway reads these for /health/services."""
    while True:
        try:
            await r.set(f"heartbeat:{settings.service}:{name}", int(time.time()), ex=30)
        except Exception:  # noqa: BLE001 - liveness must never crash the worker
            log.warning("heartbeat failed")
        await asyncio.sleep(10)


async def consume(
    r: redis.Redis,
    stream: str,
    group: str,
    handler: BatchHandler,
    count: int = 100,
    block_ms: int = 2000,
) -> None:
    """Read batches forever. The handler must finish successfully for the batch to be acked;
    if it raises, the messages stay pending and are redelivered after CLAIM_IDLE_MS."""
    name = consumer_name()
    await ensure_group(r, stream, group)
    asyncio.create_task(heartbeat(r, name))
    log.info("consuming %s as %s/%s", stream, group, name)
    last_claim = 0.0

    while True:
        try:
            batch: list[Message] = []
            if time.monotonic() - last_claim > 5:
                last_claim = time.monotonic()
                claimed = await r.xautoclaim(stream, group, name, min_idle_time=CLAIM_IDLE_MS, start_id="0-0", count=count)
                batch = _decode(claimed[1])
                if batch:
                    log.warning("reclaimed %d unacked messages from %s (redelivery)", len(batch), stream)
            if not batch:
                resp = await r.xreadgroup(group, name, {stream: ">"}, count=count, block=block_ms)
                batch = _decode(resp[0][1]) if resp else []
            if not batch:
                continue
            try:
                await handler(batch)
            except Exception:  # noqa: BLE001
                log.exception("handler failed; %d messages left pending for redelivery", len(batch))
                await asyncio.sleep(2)
                continue
            await r.xack(stream, group, *[msg_id for msg_id, _ in batch])
        except (redis.ConnectionError, redis.TimeoutError) as exc:
            log.warning("redis unavailable (%s), retrying", exc)
            await asyncio.sleep(2)
