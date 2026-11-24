# Bento backend

Python microservices connected by Redis Streams, behind one FastAPI gateway. The architecture follows
the *Bento Simulator*: a **code pipeline** (repo scans → findings → AI advice) and a **probe pipeline**
(scheduled HTTP checks → anomaly detection → incidents → alerts).

```bash
cd backend
docker compose up --build        # app on :8080, gateway on :8081
```

## Architecture

```
CODE PIPELINE
  frontend ─┐
  GitHub ───┴─► api-gateway ──► scan.jobs ──► scanner ──► postgres ──► advice.requests ──► advisor (Pickle)
               FastAPI · JWT     (stream)    sandboxed      projects,                       cached by findings
               HMAC webhooks                 dedupe by SHA  findings                        rule-based · cached

PROBE PIPELINE
  scheduler ──► probe.jobs ──► probers ×N ──► probe.results ──► analyzer ──► timescaledb (hypertable)
  Redis ZSET     (stream)      ◄── redelivery    (stream)       EWMA ·       └► incidents (postgres)
  ±10% jitter                  after 30 s                       incidents    └► alerts ──► notifier ──► in-app / Slack
                                                                                           dedup · 30 min cooldown
```

| Service | Role |
|---|---|
| **api-gateway** | The only public entry point. JWT auth, rate limits (Redis), projects/endpoints CRUD, dashboard, GitHub webhook with HMAC-SHA256 verification, `/health/services`. Owns DB migrations. |
| **scheduler** | Keeps each endpoint's next due time in a Redis ZSET, enqueues `probe.jobs`. Jitter spreads load (no thundering herd). |
| **prober** (×2) | Consumer group on `probe.jobs`; HTTP-checks each URL, writes `probe.results`. A dead prober's unacked jobs are reclaimed by a healthy one after 30 s. Private/internal addresses are blocked (SSRF). |
| **analyzer** | Batches results into TimescaleDB, keeps an EWMA latency/error baseline per endpoint, opens an incident after 3 breaching probes (latency z > 3 and > 250 ms; errors ≥ 20 % and unusual, or ≥ 50 % regardless) and closes it after 3 normal ones. Computes the Engineering Health Score every minute. If TimescaleDB rejects writes, the batch stays in the stream — nothing is dropped. |
| **notifier** | Turns alerts into in-app notifications (and Slack if configured). Repeats for an open incident are suppressed for 30 minutes. |
| **scanner** | Fetches exactly one commit (shallow, no hooks, size cap, unprivileged, tmpfs) and runs static checks: secrets in code (known token formats and high-entropy credentials; file and line only, the value is never stored), committed `.env` files, missing tests / CI / README / lockfile, known-vulnerable dependencies via [OSV](https://osv.dev), npm/PyPI dependencies a major version behind (registry lookups cached 6 h in Redis), and Dockerfile checks (unpinned base image, root user, ADD vs COPY, secrets in ENV/ARG, no HEALTHCHECK). Repository code is never executed. GitHub's duplicate deliveries are skipped by commit SHA; *Scan now* always rescans. |
| **fixer** | Auto-fix pull requests. Consumes `fix.jobs` and, with the project's GitHub App installation token, creates a `bento/fix-<finding>` branch, one commit and a PR. Fixes: missing CI (workflow for the detected language), missing README, committed `.env` files (deleted, never read; the PR says to rotate the secrets), vulnerable npm/PyPI dependencies (bumped to the OSV fixed version; the PR says when a lockfile needs regenerating). It can't write any ref outside `bento/`, so the default branch is never touched and a human always merges. One open PR per finding. |
| **advisor** | "Pickle". Rule-based: ranks a project's live incidents and code findings by severity and writes a short brief plus ≤ 3 recommendations. Skips the work when the findings hash is unchanged. No external AI service is used. |

**Data stores:** Postgres (users, projects, endpoints, scans, findings, incidents, advice, notifications) ·
TimescaleDB (`probe_results`, `project_health` hypertables, retention policies) · Redis (streams, schedule, EWMA state, dedup keys, rate limits).

## Engineering Health Score

Four report cards, computed every minute by the analyzer from raw facts (`bento_core/scoring.py`):

| Card | How it's graded | Weight |
|---|---|---|
| **Security** | the worst open problem sets it: none 100, low 85, medium 70, high 50, critical 20 (leaked secrets, `.env` files, vulnerable dependencies, secrets in Dockerfiles) | 35 |
| **Website** | last 7 days: uptime against a 99.5% target (≥99.9% 100 · ≥99.5% 85 · ≥99% 70 · ≥95% 50) × 0.6, plus p95 speed (<0.5 s 100 · <1 s 85 · <2 s 70 · <4 s 50) × 0.4. "Measuring…" until 30 checks | 30 |
| **Code basics** | checklist: README 20, tests 30, CI 30, lockfile 20; Dockerfile habits −5 each (max −15) | 20 |
| **Upkeep** | share of npm/PyPI dependencies no more than a major version behind | 15 |

The overall score is the weighted average of the cards that were measured: a card with nothing to measure
says why (*not monitored*, *measuring*, *not checked*) and is left out instead of counting as perfect.
**Security F caps the overall at 49, Security D at 69.** Grades: A 90+, B 80+, C 65+, D 50+, F below 50.

Each project also gets the single fix that raises its score most (*Do this next: +12 points*), its change
over the last week, and a `score_events` history explaining every change (*Fixed: AWS key in config.js*).
`project_scores.formula` records the version, so thresholds can be retuned and scores recomputed.

## API (via `/api`)

| | |
|---|---|
| `POST /auth/register` · `POST /auth/login` · `GET /auth/me` | accounts (JWT) |
| `GET /dashboard` | the home screen: portfolio health + trend, today's 3 tasks, biggest risk, projects worst-first, activity |
| `GET/POST /projects` · `GET/PATCH/DELETE /projects/{id}` | projects (detail includes endpoints, findings, incidents, Pickle's advice) |
| `GET /projects/{id}/latency?minutes=60` | p95 latency series |
| `POST /projects/{id}/scan` · `POST /projects/{id}/endpoints` · `DELETE /endpoints/{id}` | actions |
| `POST /projects/{id}/findings/{finding_id}/fix` | queue an auto-fix pull request (GitHub-app projects; 409 if one is already open) |
| `GET /auth/providers` · `GET /auth/github/login` · `GET /auth/github/callback` | Sign in with GitHub |
| `GET /github/status` · `POST /github/connect` · `GET /github/repos` · `POST /github/import` | connect the GitHub App, list and import repositories |
| `PUT /projects/{id}/public` | turn the public status page and badge on or off (`{"enabled": true}`); the slug is created once and kept |
| `GET /public/status/{slug}` | public status page data, no login: score, uptime 24 h / 7 d / 30 d, p95 latency (24 h), open and recently resolved incidents. Never includes code findings. Rate-limited, cached 30 s |
| `GET /badge/{slug}.svg` | README badge `bento health \| 94`, coloured by status. Private or unknown slugs get a grey `unknown` badge (never a 404). Cached 5 min |
| `POST /webhooks/github` | push, pull request (PR checks, fix-PR tracking) + installation webhooks (needs `GITHUB_WEBHOOK_SECRET`) |
| `GET/PUT /me/email` | email settings: incident alerts and weekly digest on/off |
| `GET/POST /email/unsubscribe?token=` | signed one-click unsubscribe (the GET page has a button; POST unsubscribes) |
| `GET /system` | pipeline status for the dashboard |

**Public status page and badge.** In a project's drawer, switch on *Public status page*. The page lives at
`/status/<slug>` and the drawer gives you the badge Markdown for your README:
`[![Bento health](<PUBLIC_URL>/api/badge/<slug>.svg)](<PUBLIC_URL>/status/<slug>)`. Public pages show only
uptime, latency, incidents (hostname only) and the score: code findings and vulnerabilities stay private.

Interactive docs: http://localhost:8081/api/docs · Pipeline health: http://localhost:8081/health/services

## Tests

```bash
cd backend
pip install -r tests/requirements.txt
python -m pytest tests/unit          # ~150 tests, nothing needs to be running
```

Integration tests (`tests/integration`) drive the real API against Postgres, TimescaleDB and Redis. They only
ever use the `bento_test` / `metrics_test` databases and Redis DB 15, and are skipped when the services aren't
reachable. To run them against throwaway containers (no passwords):

```bash
docker run -d --name t-pg    -p 5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine
docker run -d --name t-ts    -p 5433:5432 -e POSTGRES_HOST_AUTH_METHOD=trust timescale/timescaledb:2.17.2-pg16
docker run -d --name t-redis -p 6379:6379 redis:7-alpine
DATABASE_URL=postgresql://postgres@localhost:5432/bento TIMESCALE_URL=postgresql://postgres@localhost:5433/metrics REDIS_URL=redis://localhost:6379/0 python -m pytest
```

CI (`.github/workflows/tests.yml`) runs all of it on every push and pull request, plus `bento scan` on this
repository, the frontend lint/typecheck/build and a `docker compose build`.

## Configuration (`.env`, all optional in development)

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | signing key — **set it** anywhere shared |
| `POSTGRES_PASSWORD` | database password for both Postgres and TimescaleDB |
| `GITHUB_WEBHOOK_SECRET` | enables `/api/webhooks/github`; use the same value in the GitHub webhook settings |
| `SLACK_WEBHOOK_URL` | also send incident alerts to Slack |
| `RESEND_API_KEY` | turns on email (incident alerts, Monday digest) through [Resend](https://resend.com); without it emails are skipped with a log line |
| `EMAIL_FROM` | sender, e.g. `Bento <alerts@yourdomain.com>` (a domain verified in Resend). Default `Bento <onboarding@resend.dev>`, which Resend only delivers to your own account's address |
| `DIGEST_TIMEZONE` · `DIGEST_HOUR` | when the weekly digest goes out: Monday at this hour (default `UTC`, `8`; e.g. `Asia/Kolkata`) |
| `PROBER_REPLICAS` | number of prober workers (default 2) |
| `PROBE_INTERVAL_SECONDS` | default probe interval (default 60) |
| `ALLOW_PRIVATE_TARGETS` | `true` to allow probing localhost/private IPs (local testing only) |

To receive GitHub webhooks locally, expose port 8081 with a tunnel (e.g. `cloudflared`, `ngrok`) and point
the webhook at `https://<tunnel>/api/webhooks/github` with content type `application/json`.

## Connect GitHub (GitHub App)

Bento connects to GitHub as a **GitHub App**. That gives users "Sign in with GitHub", lets them pick
repositories (private ones too) instead of pasting URLs, and scans every push automatically. Without these
settings Bento still works with public repository URLs.

1. Open **https://github.com/settings/apps/new** and fill in:
   | Field | Value |
   |---|---|
   | GitHub App name | anything unique, e.g. `bento-yourname` (the URL slug becomes `GITHUB_APP_SLUG`) |
   | Homepage URL | your `PUBLIC_URL` (e.g. `http://localhost:8080`) |
   | Callback URL | `<PUBLIC_URL>/api/auth/github/callback` |
   | ☑ Request user authorization (OAuth) during installation | checked |
   | Setup URL | `<PUBLIC_URL>/api/auth/github/callback`, ☑ Redirect on update |
   | Webhook | ☑ Active, URL `https://<public-host>/api/webhooks/github`, secret = a long random string |
2. **Permissions** - Repository: *Contents* read & write, *Pull requests* read & write, *Workflows* read & write
   (needed to add CI files), *Checks* read & write,
   *Metadata* read. Account: *Email addresses* read.
   (Write access is used by PR checks and auto-fix pull requests; scanning only reads.)
3. **Subscribe to events**: *Push*, *Pull request*.
4. Create the app, then on its page: copy the **App ID** and **Client ID**, generate a **client secret**, and
   generate a **private key** (downloads a `.pem`).
5. Put them in `backend/.env`:
   ```bash
   GITHUB_APP_ID=123456
   GITHUB_APP_SLUG=bento-yourname
   GITHUB_CLIENT_ID=Iv23li...
   GITHUB_CLIENT_SECRET=...
   GITHUB_WEBHOOK_SECRET=<the webhook secret from step 1>
   # the .pem on one line:  awk 'NF {printf "%s\\n", $0}' your-key.pem
   GITHUB_APP_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----\n
   ```
6. `docker compose up -d` - the login page now shows **Continue with GitHub**, and **New project → From GitHub**
   lists your repositories. A repository's *Website* field on GitHub is monitored automatically.

Sign-in works on `localhost` as-is (GitHub redirects your browser). Only push webhooks need a public URL - use a
tunnel (`cloudflared tunnel --url http://localhost:8080`) locally, and update the app's webhook URL to match.

## PR checks and webhooks (local)

Push scans, PR checks and fix-PR tracking all arrive as GitHub webhooks, so GitHub must be able to reach your
Bento. Locally, a free Cloudflare quick tunnel does that:

1. Install cloudflared: `winget install --id Cloudflare.cloudflared` (macOS: `brew install cloudflared`).
2. With Bento running, start the tunnel and leave the window open:
   ```bash
   cloudflared tunnel --url http://localhost:8080
   ```
   It prints an address like `https://some-random-words.trycloudflare.com`. A quick tunnel gets a new address
   every time it starts, so repeat step 3's URL change after restarting it.
3. In the GitHub App settings (**https://github.com/settings/apps** → your app → **General**), under **Webhook**:
   tick **Active**, set **Webhook URL** to `https://<tunnel address>/api/webhooks/github`, and set
   **Webhook secret** to a long random string you make yourself. Save.
4. Put the same string in `backend/.env` as `GITHUB_WEBHOOK_SECRET=...` and run `docker compose up -d`.
5. Under **Permissions & events**: *Checks* read & write, and subscribe to **Push** and **Pull request**. Save,
   then accept the updated permissions on the installation (**https://github.com/settings/installations** →
   *Configure*).
6. Check it: **Advanced → Recent Deliveries** in the app settings should show a `ping` with a 200 response.

When a pull request is opened or updated on an imported repository, Bento scans the PR's latest commit and its
base, and posts a **Bento** check on the PR. It fails only if the PR *adds* critical or high problems, and lists
what's new, what's fixed and what was already there. Secret values are never shown.

## Layout

```
backend/
├── docker-compose.yml
├── docker/            python.Dockerfile (one recipe, SERVICE build arg) · frontend image · nginx
├── shared/bento_core/ config, db pools, Redis Streams consumer, scoring, URL safety
└── services/
    ├── api/app/       FastAPI gateway (routes/, migrations, security)
    ├── scheduler/  prober/  analyzer/  notifier/  scanner/  advisor/  fixer/
```

```bash
docker compose logs -f analyzer               # watch incidents open/close
docker compose up -d --scale prober=4         # more probe capacity
docker compose down                           # stop (data kept)
docker compose down -v                        # stop and delete all data
```
