import os


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def require(name: str) -> str:
    value = _env(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


class Settings:
    service = _env("SERVICE_NAME", "bento")
    database_url = _env("DATABASE_URL", "postgresql://bento:bento@postgres:5432/bento")
    timescale_url = _env("TIMESCALE_URL", "postgresql://bento:bento@timescaledb:5432/metrics")
    redis_url = _env("REDIS_URL", "redis://redis:6379/0")

    jwt_secret = _env("JWT_SECRET")
    jwt_ttl_hours = int(_env("JWT_TTL_HOURS", "168"))
    github_webhook_secret = _env("GITHUB_WEBHOOK_SECRET")
    slack_webhook_url = _env("SLACK_WEBHOOK_URL")

    default_probe_interval = int(_env("PROBE_INTERVAL_SECONDS", "60"))
    # Probing private/internal addresses is blocked unless explicitly allowed (SSRF protection).
    allow_private_targets = _env("ALLOW_PRIVATE_TARGETS", "false").lower() == "true"


settings = Settings()
