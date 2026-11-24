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
    # GitHub App (private repos, "Sign in with GitHub", PR checks). See README "Connect GitHub".
    github_app_id = _env("GITHUB_APP_ID")
    github_app_slug = _env("GITHUB_APP_SLUG")
    # PEM key; a single-line value with literal "\n" sequences (as in .env files) is accepted too
    github_app_private_key = (_env("GITHUB_APP_PRIVATE_KEY") or "").replace("\\n", "\n") or None
    github_client_id = _env("GITHUB_CLIENT_ID")
    github_client_secret = _env("GITHUB_CLIENT_SECRET")
    # Where browsers reach Bento (used to build OAuth redirect URLs)
    public_url = (_env("PUBLIC_URL", "http://localhost:8080") or "").rstrip("/")
    slack_webhook_url = _env("SLACK_WEBHOOK_URL")
    # Pickle's writer: a small open model served locally by Ollama. Empty OLLAMA_URL = rule-based text only.
    ollama_url = (_env("OLLAMA_URL", "http://ollama:11434") or "").rstrip("/")
    pickle_model = _env("PICKLE_MODEL", "qwen2.5:1.5b")
    # Email (Resend). Without RESEND_API_KEY emails are skipped with a log line; everything else works.
    resend_api_key = _env("RESEND_API_KEY")
    email_from = _env("EMAIL_FROM", "Bento <onboarding@resend.dev>")
    digest_timezone = _env("DIGEST_TIMEZONE", "UTC")
    digest_hour = int(_env("DIGEST_HOUR", "8"))  # Monday at this local hour

    default_probe_interval = int(_env("PROBE_INTERVAL_SECONDS", "60"))
    # Probing private/internal addresses is blocked unless explicitly allowed (SSRF protection).
    allow_private_targets = _env("ALLOW_PRIVATE_TARGETS", "false").lower() == "true"


settings = Settings()
