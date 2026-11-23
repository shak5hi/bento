"""Integration fixtures: the real FastAPI app against real Postgres, TimescaleDB and Redis.

Databases are `bento_test` / `metrics_test` and Redis DB 15 (see tests/conftest.py); every test starts
from empty tables. GitHub is never called: tests swap in an httpx.MockTransport.
"""

import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
import redis
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

TABLES = "users, projects, endpoints, scans, findings, incidents, project_scores, advice, notifications, github_installations, fix_prs"


def _admin_url(url: str) -> str:
    return urlunsplit(urlsplit(url)._replace(path="/postgres"))


async def _ensure_db(url: str) -> None:
    name = urlsplit(url).path.lstrip("/")
    assert name.endswith("_test"), f"refusing to run integration tests against {name!r}"
    conn = await asyncpg.connect(_admin_url(url), timeout=5)
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
            await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def client():
    try:
        for url in (os.environ["DATABASE_URL"], os.environ["TIMESCALE_URL"]):
            asyncio.run(_ensure_db(url))
        redis.Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=3).ping()
    except (OSError, asyncpg.PostgresError, redis.RedisError, asyncio.TimeoutError) as exc:
        if os.environ.get("BENTO_REQUIRE_INTEGRATION"):  # CI: a skipped suite must not look green
            pytest.fail(f"integration services unreachable: {exc}")
        pytest.skip(f"integration services unreachable: {exc}")

    from app.main import app
    from bento_core.config import settings

    settings.allow_private_targets = True  # endpoint URLs in tests don't need DNS
    with TestClient(app, base_url="http://testserver") as c:
        yield c


@pytest.fixture(autouse=True)
def clean(client):
    from app.state import state

    async def wipe():
        await state.pg.execute(f"TRUNCATE {TABLES} CASCADE")
        await state.ts.execute("TRUNCATE probe_results, project_health")
        await state.redis.flushdb()

    client.portal.call(wipe)
    yield


@pytest.fixture
def db(client):
    """Run a coroutine function on the app's event loop with access to its pools: db(fn, *args)."""
    from app.state import state

    def run(fn, *args):
        return client.portal.call(fn, state, *args)

    return run


@pytest.fixture
def user(client):
    """Register a fresh user; returns (headers, user json)."""
    counter = {"n": 0}

    def make(email: str | None = None):
        counter["n"] += 1
        res = client.post("/api/auth/register", json={
            "email": email or f"user{counter['n']}@example.com", "password": "correct-horse-9", "name": "Test User",
        })
        assert res.status_code == 201, res.text
        body = res.json()
        return {"Authorization": f"Bearer {body['token']}"}, body["user"]

    return make
