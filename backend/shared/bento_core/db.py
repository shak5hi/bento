import asyncio
import json
import logging

import asyncpg

log = logging.getLogger(__name__)


async def _init_connection(conn: asyncpg.Connection) -> None:
    # jsonb <-> Python objects
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(dsn: str, attempts: int = 30, delay: float = 2.0) -> asyncpg.Pool:
    """Connect with retries, so services survive starting before the database is ready."""
    for attempt in range(1, attempts + 1):
        try:
            return await asyncpg.create_pool(dsn, min_size=1, max_size=10, init=_init_connection)
        except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as exc:
            if attempt == attempts:
                raise
            log.warning("database not ready (%s), retry %d/%d", exc.__class__.__name__, attempt, attempts)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")
