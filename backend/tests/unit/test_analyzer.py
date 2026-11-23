"""Analyzer incident logic: EWMA baselines, open after 3 breaches, close after 3 normal probes."""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from helpers import load_service

analyzer = load_service("analyzer")


class FakeRedis:
    def __init__(self):
        self.kv, self.streams = {}, {}

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, value, ex=None):
        self.kv[key] = value

    async def xadd(self, stream, fields, maxlen=None, approximate=True):
        self.streams.setdefault(stream, []).append(json.loads(fields["data"]))
        return "0-1"


class FakePg:
    def __init__(self):
        self.incidents = {}

    async def fetchval(self, sql, *args):
        assert sql.strip().startswith("INSERT INTO incidents")
        iid = uuid4()
        project_id, endpoint_id, url, kind, baseline, peak = args
        self.incidents[str(iid)] = {"kind": kind, "status": "open", "baseline": baseline, "peak": peak}
        return iid

    async def execute(self, sql, *args):
        inc = self.incidents[str(args[0])]
        if "status = 'closed'" in sql:
            inc.update(status="closed", peak=args[1])
        elif "GREATEST" in sql:
            inc["peak"] = max(inc["peak"], args[1])


@pytest.fixture
def setup():
    pg, r = FakePg(), FakeRedis()
    a = analyzer.Analyzer(pg, None, r)
    ep, proj = str(uuid4()), str(uuid4())
    clock = {"t": datetime(2026, 1, 1, tzinfo=timezone.utc)}

    async def probe(latency=120.0, status=200):
        clock["t"] += timedelta(minutes=1)
        await a.detect({
            "time": clock["t"].isoformat(), "endpoint_id": ep, "project_id": proj, "owner_id": str(uuid4()),
            "url": "https://example.com", "status": status, "latency_ms": latency if status else None, "error": None,
        })

    return a, pg, r, probe


def open_incidents(pg, kind):
    return [i for i in pg.incidents.values() if i["kind"] == kind and i["status"] == "open"]


async def warm_up(probe, n=20):
    for i in range(n):
        await probe(latency=100 + (i % 5) * 4)  # 100..116 ms


async def test_steady_traffic_opens_nothing(setup):
    _, pg, _, probe = setup
    await warm_up(probe, 50)
    assert pg.incidents == {}


async def test_two_slow_probes_are_not_an_incident(setup):
    _, pg, _, probe = setup
    await warm_up(probe)
    await probe(latency=900)
    await probe(latency=900)
    await probe(latency=105)
    assert pg.incidents == {}


async def test_latency_incident_opens_after_three_breaches_and_closes_after_three_normals(setup):
    _, pg, r, probe = setup
    await warm_up(probe)
    for lat in (800, 950, 900):
        await probe(latency=lat)
    (inc,) = open_incidents(pg, "latency")
    assert inc["baseline"] < 150
    assert inc["peak"] == 950, "the peak is the worst probe of the breach, not the third one"

    await probe(latency=1200)  # still breaching: peak grows, alert re-emitted
    assert inc["peak"] == 1200
    assert sum(1 for a in r.streams["alerts"] if a["type"] == "open") >= 2

    for _ in range(2):
        await probe(latency=105)
    assert inc["status"] == "open"
    await probe(latency=105)
    assert inc["status"] == "closed" and inc["peak"] == 1200
    assert r.streams["alerts"][-1]["type"] == "resolved"


async def test_baseline_does_not_learn_during_an_incident(setup):
    _, _, r, probe = setup
    await warm_up(probe)
    (state_key,) = r.kv
    mu_before = json.loads(r.kv[state_key])["mu"]
    for _ in range(10):
        await probe(latency=1500)
    assert json.loads(r.kv[state_key])["mu"] == pytest.approx(mu_before)


async def test_slow_but_under_250ms_is_not_an_incident(setup):
    _, pg, _, probe = setup
    for _ in range(20):
        await probe(latency=20)
    for _ in range(5):
        await probe(latency=200)  # 10x the baseline, but still fast
    assert open_incidents(pg, "latency") == []


async def test_error_incident_when_mostly_failing(setup):
    _, pg, r, probe = setup
    await warm_up(probe)
    for _ in range(6):
        await probe(status=503)
    (inc,) = open_incidents(pg, "errors")
    # The 10-probe window needs 10 good probes to reach 0% failing, then 3 normal readings close it.
    for _ in range(11):
        await probe()
    assert inc["status"] == "open"
    await probe()
    assert inc["status"] == "closed"


async def test_endpoint_down_from_the_start_still_opens_an_incident(setup):
    """'Always failing' must not be learned as normal."""
    _, pg, _, probe = setup
    for _ in range(8):
        await probe(status=None)  # no response at all
    assert len(open_incidents(pg, "errors")) == 1


async def test_incident_opens_once(setup):
    _, pg, _, probe = setup
    await warm_up(probe)
    for _ in range(10):
        await probe(latency=2000)
    assert len(pg.incidents) == 1
