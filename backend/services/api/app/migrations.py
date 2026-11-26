"""Schema for both databases. The gateway owns migrations; workers start after it is healthy."""

import logging

import asyncpg

log = logging.getLogger(__name__)

POSTGRES = """
CREATE TABLE IF NOT EXISTS users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT NOT NULL UNIQUE,
  name          TEXT,
  password_hash TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id       UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  name           TEXT NOT NULL,
  repo_url       TEXT,
  repo_full_name TEXT,
  last_scan_at   TIMESTAMPTZ,
  last_scan_sha  TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS projects_owner_idx ON projects (owner_id);
CREATE INDEX IF NOT EXISTS projects_repo_idx ON projects (repo_full_name);

CREATE TABLE IF NOT EXISTS endpoints (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  UUID NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  url         TEXT NOT NULL,
  interval_s  INT  NOT NULL DEFAULT 60 CHECK (interval_s BETWEEN 15 AND 3600),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, url)
);

-- one row per (project, commit): GitHub retries the same webhook, we scan once
CREATE TABLE IF NOT EXISTS scans (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     UUID NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  sha            TEXT NOT NULL,
  status         TEXT NOT NULL CHECK (status IN ('running', 'done', 'failed')),
  delivery_count INT  NOT NULL DEFAULT 1,
  error          TEXT,
  started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at    TIMESTAMPTZ,
  UNIQUE (project_id, sha)
);

CREATE TABLE IF NOT EXISTS findings (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     UUID NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  key            TEXT NOT NULL,
  severity       TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
  title          TEXT NOT NULL,
  detail         TEXT,
  effort_minutes INT,
  status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
  first_seen     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at    TIMESTAMPTZ,
  UNIQUE (project_id, key)
);

CREATE TABLE IF NOT EXISTS incidents (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  UUID NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  endpoint_id UUID REFERENCES endpoints (id) ON DELETE SET NULL,
  url         TEXT NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('latency', 'errors')),
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  baseline    DOUBLE PRECISION,
  peak        DOUBLE PRECISION,
  opened_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS incidents_project_status_idx ON incidents (project_id, status);

CREATE TABLE IF NOT EXISTS project_scores (
  project_id  UUID PRIMARY KEY REFERENCES projects (id) ON DELETE CASCADE,
  total       INT,
  uptime      REAL,
  latency     REAL,
  errors      REAL,
  code        REAL,
  basis       TEXT,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pickle's per-project advice, cached by a hash of the findings + open incidents
CREATE TABLE IF NOT EXISTS advice (
  project_id      UUID PRIMARY KEY REFERENCES projects (id) ON DELETE CASCADE,
  findings_hash   TEXT,
  brief           TEXT NOT NULL,
  recommendations JSONB NOT NULL DEFAULT '[]',
  source          TEXT NOT NULL DEFAULT 'rules',
  generated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pickle is rule-based only: drop the old constraint on the advice source
ALTER TABLE advice DROP CONSTRAINT IF EXISTS advice_source_check;

CREATE TABLE IF NOT EXISTS notifications (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id   UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects (id) ON DELETE CASCADE,
  kind       TEXT NOT NULL,
  title      TEXT NOT NULL,
  body       TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  read_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS notifications_owner_idx ON notifications (owner_id, created_at DESC);

-- Why the most recent scan attempt failed (NULL after a successful scan)
ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_scan_error TEXT;

-- GitHub: accounts created via "Sign in with GitHub" have no password
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS github_id BIGINT UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS github_login TEXT;

-- Installations of the Bento GitHub App a user has access to (an org install can be shared)
CREATE TABLE IF NOT EXISTS github_installations (
  id            BIGINT NOT NULL,
  owner_id      UUID   NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  account_login TEXT   NOT NULL,
  account_type  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id, owner_id)
);

-- Projects imported through the app are cloned with an installation token (private repos work)
ALTER TABLE projects ADD COLUMN IF NOT EXISTS installation_id BIGINT;
CREATE INDEX IF NOT EXISTS projects_installation_idx ON projects (installation_id);

-- Public status page + README badge: private by default. The slug is kept when the page is
-- turned off, so turning it back on restores the same URL (and existing badges keep working).
ALTER TABLE projects ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_slug TEXT UNIQUE;

-- Auto-fix pull requests: one row per attempt. At most one queued/open PR per finding.
CREATE TABLE IF NOT EXISTS fix_prs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  UUID NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  finding_key TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'open', 'merged', 'closed', 'failed')),
  branch      TEXT,
  pr_number   INT,
  pr_url      TEXT,
  error       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS fix_prs_active_idx ON fix_prs (project_id, finding_key) WHERE status IN ('queued', 'open');
CREATE INDEX IF NOT EXISTS fix_prs_pr_idx ON fix_prs (project_id, pr_number);

-- Report-card scoring (bento_core.scoring): raw facts in, explained cards out
ALTER TABLE findings ADD COLUMN IF NOT EXISTS meta JSONB;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS scan_facts JSONB;
ALTER TABLE project_scores ADD COLUMN IF NOT EXISTS grade TEXT;
ALTER TABLE project_scores ADD COLUMN IF NOT EXISTS cards JSONB;
ALTER TABLE project_scores ADD COLUMN IF NOT EXISTS next_action JSONB;
ALTER TABLE project_scores ADD COLUMN IF NOT EXISTS capped TEXT;
ALTER TABLE project_scores ADD COLUMN IF NOT EXISTS inputs JSONB;
ALTER TABLE project_scores ADD COLUMN IF NOT EXISTS formula TEXT;

-- Every change of a project's score, with the reason ("Fixed: leaked key in config.js")
CREATE TABLE IF NOT EXISTS score_events (
  id          BIGSERIAL PRIMARY KEY,
  project_id  UUID NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  total       INT NOT NULL,
  previous    INT,
  grade       TEXT,
  reason      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS score_events_project_idx ON score_events (project_id, at DESC);

-- Email: per-user switches for incident alerts and the weekly digest, and the last digest's ISO week
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_incidents BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_digest BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_digest_week TEXT;

-- GitHub: an installation on someone else's account (a collaborator's, an org's) only exposes the repos
-- this user can open themselves. own = the installation is on the user's own GitHub account.
ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS own BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE github_installations ADD COLUMN IF NOT EXISTS repos TEXT[] NOT NULL DEFAULT '{}';
-- Welcome email: new accounts get their first portfolio report once their projects are scanned.
-- Added as false (existing accounts never get one), then defaulted to true for every account made after.
ALTER TABLE users ADD COLUMN IF NOT EXISTS welcome_due BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ALTER COLUMN welcome_due SET DEFAULT true;
UPDATE github_installations i SET own = true FROM users u
 WHERE u.id = i.owner_id AND NOT i.own AND lower(u.github_login) = lower(i.account_login);
"""

TIMESCALE = """
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS probe_results (
  time        TIMESTAMPTZ NOT NULL,
  due         TIMESTAMPTZ,
  endpoint_id UUID NOT NULL,
  project_id  UUID NOT NULL,
  status      INT,
  latency_ms  DOUBLE PRECISION,
  ok          BOOLEAN NOT NULL,
  error       TEXT
);
SELECT create_hypertable('probe_results', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS probe_results_project_time_idx ON probe_results (project_id, time DESC);
CREATE INDEX IF NOT EXISTS probe_results_endpoint_time_idx ON probe_results (endpoint_id, time DESC);

CREATE TABLE IF NOT EXISTS project_health (
  time       TIMESTAMPTZ NOT NULL,
  project_id UUID NOT NULL,
  owner_id   UUID NOT NULL,
  total      INT NOT NULL
);
SELECT create_hypertable('project_health', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS project_health_owner_time_idx ON project_health (owner_id, time DESC);
"""

RETENTION = [
    "SELECT add_retention_policy('probe_results', INTERVAL '30 days', if_not_exists => TRUE)",
    "SELECT add_retention_policy('project_health', INTERVAL '180 days', if_not_exists => TRUE)",
]


async def migrate(pg: asyncpg.Pool, ts: asyncpg.Pool) -> None:
    async with pg.acquire() as conn:
        await conn.execute(POSTGRES)
    async with ts.acquire() as conn:
        await conn.execute(TIMESCALE)
        for stmt in RETENTION:
            try:
                await conn.execute(stmt)
            except asyncpg.PostgresError as exc:  # policies need the licensed edition in some images
                log.warning("retention policy skipped: %s", exc)
    log.info("migrations applied")
