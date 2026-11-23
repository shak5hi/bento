"""Analyzer: probe.results -> TimescaleDB, EWMA baselines, incidents, alerts, health scores.

Detection rules (same as the simulator):
  * latency breach: z > 3 against the endpoint's EWMA baseline AND over 250 ms
  * error breach:   >= 20% of the last 10 probes failed AND z > 3 against the usual error rate,
                    or >= 50% failed regardless of history (baselines never learn from failing windows)
  * an incident opens after 3 breaching probes and closes after 3 normal ones

Results are written in batches. If TimescaleDB rejects writes, the batch is not acked and stays
in the stream (redelivered later), so nothing is dropped.
"""

import asyncio
import json
import math
from datetime import datetime, timezone

from bento_core import streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.log import setup_logging
from bento_core.scoring import health_score, status_for

log = setup_logging()

STATE_KEY = "ewma:{}"
BREACHES_TO_OPEN = 3
NORMALS_TO_CLOSE = 3
SCORE_EVERY_S = 60
ERROR_FLOOR = 0.5  # >= 50% of recent probes failing is always an incident


def _new_state(latency: float | None) -> dict:
    mu = latency if latency is not None else 200.0
    return {
        "mu": mu, "v": (0.25 * mu) ** 2, "emu": 0.0, "ev": 0.0004, "win": [],
        "latency": {"b": 0, "o": 0, "open": None, "peak": 0.0},
        "errors": {"b": 0, "o": 0, "open": None, "peak": 0.0},
    }


class Analyzer:
    def __init__(self, pg, ts, r):
        self.pg, self.ts, self.r = pg, ts, r

    async def handle(self, batch: list[streams.Message]) -> None:
        results = [msg for _, msg in batch]
        await self.store(results)  # raises -> batch not acked -> redelivered
        for res in sorted(results, key=lambda x: x["time"]):
            await self.detect(res)

    async def store(self, results: list[dict]) -> None:
        rows = [
            (
                datetime.fromisoformat(r["time"]),
                datetime.fromtimestamp(r["due"], timezone.utc) if r.get("due") else None,
                r["endpoint_id"],
                r["project_id"],
                r["status"],
                r["latency_ms"],
                r["status"] is not None and r["status"] < 500,
                r["error"],
            )
            for r in results
        ]
        await self.ts.executemany(
            """INSERT INTO probe_results (time, due, endpoint_id, project_id, status, latency_ms, ok, error)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            rows,
        )

    async def detect(self, res: dict) -> None:
        key = STATE_KEY.format(res["endpoint_id"])
        raw = await self.r.get(key)
        ok = res["status"] is not None and res["status"] < 500
        lat = res["latency_ms"]
        st = json.loads(raw) if raw else _new_state(lat if ok else None)

        st["win"] = (st["win"] + [0 if ok else 1])[-10:]
        rate = sum(st["win"]) / len(st["win"])
        sd_l = max(math.sqrt(st["v"]), 5.0, 0.05 * st["mu"])
        sd_e = max(math.sqrt(st["ev"]), 0.02)
        z_l = (lat - st["mu"]) / sd_l if ok and lat is not None else 0.0
        z_e = (rate - st["emu"]) / sd_e

        lat_breach = ok and z_l > 3 and lat > 250
        # Unusual error rate, or mostly failing regardless of history: an endpoint that has been
        # down since it was added must not have "always failing" learned as its normal.
        err_breach = len(st["win"]) >= 5 and rate >= 0.2 and (z_e > 3 or rate >= ERROR_FLOOR)

        await self.track(st, res, "latency", lat_breach, ok and not lat_breach, lat or 0.0)
        await self.track(st, res, "errors", err_breach, rate < 0.1, rate)

        # Baselines only learn from normal behaviour, never during an incident.
        if ok and not lat_breach and not st["latency"]["open"]:
            d = lat - st["mu"]
            st["mu"] += 0.1 * d
            st["v"] = 0.9 * (st["v"] + 0.1 * d * d)
        if not err_breach and not st["errors"]["open"] and rate < 0.2:
            d = rate - st["emu"]
            st["emu"] += 0.1 * d
            st["ev"] = 0.9 * (st["ev"] + 0.1 * d * d)

        await self.r.set(key, json.dumps(st), ex=7 * 24 * 3600)

    async def track(self, st: dict, res: dict, kind: str, breach: bool, normal: bool, value: float) -> None:
        tr = st[kind]
        if breach:
            tr["b"] += 1
            tr["o"] = 0
            tr["peak"] = max(tr["peak"], value)
        elif normal:
            tr["b"] = 0
            tr["o"] += 1
            if not tr["open"]:
                tr["peak"] = 0.0  # a breach run that never became an incident: forget its peak

        alert_base = {
            "kind": kind,
            "project_id": res["project_id"],
            "owner_id": res["owner_id"],
            "endpoint_id": res["endpoint_id"],
            "url": res["url"],
            "baseline": st["mu"] if kind == "latency" else st["emu"],
        }

        if not tr["open"] and tr["b"] >= BREACHES_TO_OPEN:
            tr["o"] = 0
            # the worst probe of the breach run that opened it, not just the last one
            incident_id = await self.pg.fetchval(
                """INSERT INTO incidents (project_id, endpoint_id, url, kind, baseline, peak)
                   VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
                res["project_id"], res["endpoint_id"], res["url"], kind, alert_base["baseline"], tr["peak"],
            )
            tr["open"] = str(incident_id)
            log.warning("OPEN %s incident on %s (value %.2f, baseline %.2f)", kind, res["url"], value, alert_base["baseline"])
            await streams.publish(self.r, streams.ADVICE_REQUESTS, {"project_id": res["project_id"]})

        if tr["open"] and breach:
            # Re-emitted on every breaching probe; the notifier dedups with a cooldown.
            await streams.publish(self.r, streams.ALERTS, {**alert_base, "type": "open", "incident_id": tr["open"], "value": value})
            await self.pg.execute("UPDATE incidents SET peak = GREATEST(peak, $2) WHERE id = $1", tr["open"], value)

        if tr["open"] and tr["o"] >= NORMALS_TO_CLOSE:
            await self.pg.execute(
                "UPDATE incidents SET status = 'closed', closed_at = now(), peak = $2 WHERE id = $1", tr["open"], tr["peak"]
            )
            log.info("CLOSE %s incident on %s (peak %.2f)", kind, res["url"], tr["peak"])
            await streams.publish(self.r, streams.ALERTS, {**alert_base, "type": "resolved", "incident_id": tr["open"], "value": tr["peak"]})
            await streams.publish(self.r, streams.ADVICE_REQUESTS, {"project_id": res["project_id"]})
            tr.update(open=None, peak=0.0, b=0)

    async def score_loop(self) -> None:
        """Every minute: Engineering Health Score per project -> Postgres (current) + Timescale (history)."""
        while True:
            try:
                await self.score_all()
            except Exception:  # noqa: BLE001
                log.exception("scoring failed")
            await asyncio.sleep(SCORE_EVERY_S)

    async def score_all(self) -> None:
        projects = await self.pg.fetch("SELECT id, owner_id, last_scan_at FROM projects")
        if not projects:
            return
        stats = {
            r["project_id"]: r
            for r in await self.ts.fetch(
                """SELECT project_id, count(*) AS total,
                          count(*) FILTER (WHERE status IS NOT NULL) AS responded,
                          count(*) FILTER (WHERE status >= 500) AS failed,
                          percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE ok) AS p95
                     FROM probe_results WHERE time > now() - interval '30 minutes'
                    GROUP BY project_id"""
            )
        }
        sev: dict = {}
        for f in await self.pg.fetch("SELECT project_id, severity FROM findings WHERE status = 'open'"):
            sev.setdefault(f["project_id"], []).append(f["severity"])

        now = datetime.now(timezone.utc)
        history = []
        for p in projects:
            s = stats.get(p["id"])
            score = health_score(
                s["total"] if s else 0, s["responded"] if s else 0, s["failed"] if s else 0,
                s["p95"] if s else None, sev.get(p["id"], []), code_known=p["last_scan_at"] is not None,
            )
            if score is None:  # nothing measured yet: clear any stale score instead of inventing one
                await self.pg.execute("DELETE FROM project_scores WHERE project_id = $1", p["id"])
                continue
            prev = await self.pg.fetchval("SELECT total FROM project_scores WHERE project_id = $1", p["id"])
            await self.pg.execute(
                """INSERT INTO project_scores (project_id, total, uptime, latency, errors, code, basis, computed_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, now())
                   ON CONFLICT (project_id) DO UPDATE SET total = $2, uptime = $3, latency = $4, errors = $5,
                     code = $6, basis = $7, computed_at = now()""",
                p["id"], score.total, score.uptime, score.latency, score.errors, score.code, score.basis,
            )
            history.append((now, p["id"], p["owner_id"], score.total))
            if prev is not None and status_for(prev) != score.status:
                await streams.publish(self.r, streams.ADVICE_REQUESTS, {"project_id": str(p["id"])})
        await self.ts.executemany(
            "INSERT INTO project_health (time, project_id, owner_id, total) VALUES ($1, $2, $3, $4)", history
        )


async def main() -> None:
    pg = await create_pool(settings.database_url)
    ts = await create_pool(settings.timescale_url)
    r = streams.connect()
    analyzer = Analyzer(pg, ts, r)
    asyncio.create_task(analyzer.score_loop())
    await streams.consume(r, streams.PROBE_RESULTS, "analyzer", analyzer.handle, count=500)


if __name__ == "__main__":
    asyncio.run(main())
