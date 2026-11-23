"""API gateway: the single public entry point to Bento's backend."""

import os
from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bento_core import streams
from bento_core.config import settings
from bento_core.db import create_pool
from bento_core.log import setup_logging

from .migrations import migrate
from .routes import auth, dashboard, github, projects, public, system, webhooks
from .state import state

log = setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    state.pg = await create_pool(settings.database_url)
    state.ts = await create_pool(settings.timescale_url)
    state.redis = streams.connect()
    state.http = httpx.AsyncClient(timeout=15)
    await migrate(state.pg, state.ts)
    log.info("api gateway ready")
    yield
    await state.pg.close()
    await state.ts.close()
    await state.redis.aclose()
    await state.http.aclose()


app = FastAPI(title="Bento API", version="2.0.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    details = [
        {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"].removeprefix("Value error, ")}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details[0]["message"] if details else "Invalid request", "errors": details})


for router in (system.router, auth.router, github.router, projects.router, public.router, dashboard.router, webhooks.router):
    app.include_router(router)
