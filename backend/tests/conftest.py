"""Shared test setup.

Unit tests need nothing running. Integration tests (tests/integration) need Postgres, TimescaleDB and
Redis; they always use separate `*_test` databases and Redis DB 15, derived from DATABASE_URL /
TIMESCALE_URL / REDIS_URL, so they can never touch real data.
"""

import importlib.util
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


def _test_db(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{name}"))


# ---- environment, before any Bento module reads settings at import time ----
# Test-only constants: not secrets, they only sign tokens inside this test process.
os.environ["JWT_SECRET"] = "test-only-jwt-signing-key-not-a-secret-0000"
os.environ["GITHUB_WEBHOOK_SECRET"] = "test-only-webhook-key-not-a-secret-00000"
for name in ("GITHUB_APP_ID", "GITHUB_APP_SLUG", "GITHUB_APP_PRIVATE_KEY", "GITHUB_CLIENT_ID",
             "GITHUB_CLIENT_SECRET", "SLACK_WEBHOOK_URL"):
    os.environ[name] = ""
os.environ["ALLOW_PRIVATE_TARGETS"] = "false"
os.environ["PUBLIC_URL"] = "http://bento.test"
os.environ["DATABASE_URL"] = _test_db(os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/bento"), "bento_test")
os.environ["TIMESCALE_URL"] = _test_db(os.environ.get("TIMESCALE_URL", "postgresql://postgres@localhost:5433/metrics"), "metrics_test")
os.environ["REDIS_URL"] = _test_db(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), "15")

for p in (BACKEND / "shared", BACKEND / "services" / "api", BACKEND / "services" / "fixer", REPO / "cli"):
    sys.path.insert(0, str(p))


def load_service(service: str, module: str = "main"):
    """Import services/<service>/<module>.py under a unique name (every service has a main.py)."""
    path = BACKEND / "services" / service / f"{module}.py"
    spec = importlib.util.spec_from_file_location(f"{service}_{module}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod
