"""Process-wide connections, created in the app lifespan."""

import asyncpg
import httpx
import redis.asyncio as redis


class State:
    pg: asyncpg.Pool
    ts: asyncpg.Pool
    redis: redis.Redis
    http: httpx.AsyncClient


state = State()
