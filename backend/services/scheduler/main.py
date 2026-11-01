"""Scheduler: keeps every endpoint's next due time in a Redis ZSET and enqueues probe jobs.

Due times are spread with +-10% jitter so endpoints never all fire on the same second
(the "thundering herd" in the simulator).
"""

import asyncio
import json
import random
import time

from bento_core import streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.log import setup_logging

log = setup_logging()

SCHEDULE = "probe:schedule"  # ZSET endpoint_id -> next due (epoch seconds)
META = "probe:meta"  # HASH endpoint_id -> job payload
JITTER = 0.10


async def sync_endpoints(pg, r) -> None:
    """Mirror the endpoints table into Redis: add new ones (spread over their interval), drop deleted ones."""
    rows = await pg.fetch(
        """SELECT e.id, e.url, e.interval_s, e.project_id, p.owner_id
             FROM endpoints e JOIN projects p ON p.id = e.project_id"""
    )
    now = time.time()
    current = {str(r_["id"]): r_ for r_ in rows}
    scheduled = set(await r.zrange(SCHEDULE, 0, -1))

    pipe = r.pipeline()
    for eid, row in current.items():
        meta = {
            "endpoint_id": eid,
            "project_id": str(row["project_id"]),
            "owner_id": str(row["owner_id"]),
            "url": row["url"],
            "interval_s": row["interval_s"],
        }
        pipe.hset(META, eid, json.dumps(meta))
        if eid not in scheduled:
            # first probe soon, spread so a bulk import doesn't fire at once
            pipe.zadd(SCHEDULE, {eid: now + random.uniform(1, min(10, row["interval_s"]))}, nx=True)
    removed = scheduled - current.keys()
    if removed:
        pipe.zrem(SCHEDULE, *removed)
        pipe.hdel(META, *removed)
    await pipe.execute()
    if removed:
        log.info("unscheduled %d deleted endpoint(s)", len(removed))


async def tick(r) -> int:
    now = time.time()
    due = await r.zrangebyscore(SCHEDULE, "-inf", now, withscores=True)
    if not due:
        return 0
    metas = await r.hmget(META, [eid for eid, _ in due])
    pipe = r.pipeline()
    for (eid, due_at), raw in zip(due, metas):
        if raw is None:
            pipe.zrem(SCHEDULE, eid)
            continue
        meta = json.loads(raw)
        interval = meta["interval_s"]
        payload = {**meta, "due": due_at}
        pipe.xadd(streams.PROBE_JOBS, {"data": json.dumps(payload)}, maxlen=streams.MAXLEN, approximate=True)
        nxt = due_at + interval * (1 + random.uniform(-JITTER, JITTER))
        if nxt < now:  # we fell behind (scheduler was down): don't burst, restart the cadence
            nxt = now + interval * random.uniform(0.5, 1.0)
        pipe.zadd(SCHEDULE, {eid: nxt})
    await pipe.execute()
    return len(due)


async def main() -> None:
    pg = await create_pool(settings.database_url)
    r = streams.connect()
    asyncio.create_task(streams.heartbeat(r, streams.consumer_name()))
    log.info("scheduler started")
    last_sync = 0.0
    while True:
        try:
            if time.monotonic() - last_sync > 10:
                await sync_endpoints(pg, r)
                last_sync = time.monotonic()
            await tick(r)
        except Exception:  # noqa: BLE001 - keep scheduling through transient failures
            log.exception("scheduler tick failed")
            await asyncio.sleep(2)
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
