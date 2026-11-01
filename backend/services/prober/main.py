"""Prober: reads probe.jobs (consumer group "probers"), calls each endpoint, writes probe.results.

Run several replicas. If one dies mid-batch its jobs are never acked and get redelivered
to a healthy prober after 30 s.
"""

import asyncio
import json
import time
from datetime import datetime, timezone

import httpx

from bento_core import streams
from bento_core.log import setup_logging
from bento_core.net import probe_target_error

log = setup_logging()

TIMEOUT_S = 10.0
CONCURRENCY = 50


async def probe(client: httpx.AsyncClient, job: dict, sem: asyncio.Semaphore) -> dict:
    result = {
        "endpoint_id": job["endpoint_id"],
        "project_id": job["project_id"],
        "owner_id": job["owner_id"],
        "url": job["url"],
        "due": job.get("due"),
        "status": None,
        "latency_ms": None,
        "error": None,
    }
    if err := probe_target_error(job["url"]):
        result["error"] = f"blocked: {err}"
        result["time"] = datetime.now(timezone.utc).isoformat()
        return result

    async with sem:
        start = time.perf_counter()
        try:
            resp = await client.get(job["url"])
            result["status"] = resp.status_code
        except httpx.TimeoutException:
            result["error"] = "timeout"
        except httpx.HTTPError as exc:
            result["error"] = exc.__class__.__name__
        result["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
    result["time"] = datetime.now(timezone.utc).isoformat()
    return result


async def main() -> None:
    r = streams.connect()
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(
        timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": "BentoProber/2.0 (+uptime monitor)"}
    ) as client:

        async def handle(batch: list[streams.Message]) -> None:
            results = await asyncio.gather(*(probe(client, job, sem) for _, job in batch))
            pipe = r.pipeline()
            for res in results:
                pipe.xadd(streams.PROBE_RESULTS, {"data": json.dumps(res)}, maxlen=streams.MAXLEN, approximate=True)
            await pipe.execute()

        await streams.consume(r, streams.PROBE_JOBS, "probers", handle, count=100)


if __name__ == "__main__":
    asyncio.run(main())
