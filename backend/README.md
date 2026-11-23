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
| **advisor** | "Pickle". Rule-based: ranks a project's live incidents and code findings by severity and writes a short brief plus ≤ 3 recommendations. Skips the work when the findings hash is unchanged. No external AI service is used. |

**Data stores:** Postgres (users, projects, endpoints, scans, findings, incidents, advice, notifications) ·
TimescaleDB (`probe_results`, `project_health` hypertables, retention policies) · Redis (streams, schedule, EWMA state, dedup keys, rate limits).

## Engineering Health Score

`Uptime 40 + Latency 20 + Errors 20 + Code 20` over the last 30 minutes of probes. Code starts at 20 and
loses 8 / 4 / 1.5 / 0.5 points per open critical / high / medium / low finding. A project with no
endpoints is scored on code alone and marked "code only".

## API (via `/api`)

| | |
|---|---|
| `POST /auth/register` · `POST /auth/login` · `GET /auth/me` | accounts (JWT) |
| `GET /dashboard` | the home screen: portfolio health + trend, today's 3 tasks, biggest risk, projects worst-first, activity |
| `GET/POST /projects` · `GET/PATCH/DELETE /projects/{id}` | projects (detail includes endpoints, findings, incidents, Pickle's advice) |
| `GET /projects/{id}/latency?minutes=60` | p95 latency series |
| `POST /projects/{id}/scan` · `POST /projects/{id}/endpoints` · `DELETE /endpoints/{id}` | actions |
| `GET /auth/providers` · `GET /auth/github/login` · `GET /auth/github/callback` | Sign in with GitHub |
| `GET /github/status` · `POST /github/connect` · `GET /github/repos` · `POST /github/import` | connect the GitHub App, list and import repositories |
| `PUT /projects/{id}/public` | turn the public status page and badge on or off (`{"enabled": true}`); the slug is created once and kept |
| `GET /public/status/{slug}` | public status page data, no login: score, uptime 24 h / 7 d / 30 d, p95 latency (24 h), open and recently resolved incidents. Never includes code findings. Rate-limited, cached 30 s |
| `GET /badge/{slug}.svg` | README badge `bento health \| 94`, coloured by status. Private or unknown slugs get a grey `unknown` badge (never a 404). Cached 5 min |
| `POST /webhooks/github` | push + installation webhooks (needs `GITHUB_WEBHOOK_SECRET`) |
| `GET /system` | pipeline status for the dashboard |

**Public status page and badge.** In a project's drawer, switch on *Public status page*. The page lives at
`/status/<slug>` and the drawer gives you the badge Markdown for your README:
`[![Bento health](<PUBLIC_URL>/api/badge/<slug>.svg)](<PUBLIC_URL>/status/<slug>)`. Public pages show only
uptime, latency, incidents (hostname only) and the score: code findings and vulnerabilities stay private.

Interactive docs: http://localhost:8081/api/docs · Pipeline health: http://localhost:8081/health/services

## Configuration (`.env`, all optional in development)

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | signing key — **set it** anywhere shared |
| `POSTGRES_PASSWORD` | database password for both Postgres and TimescaleDB |
| `GITHUB_WEBHOOK_SECRET` | enables `/api/webhooks/github`; use the same value in the GitHub webhook settings |
| `SLACK_WEBHOOK_URL` | also send incident alerts to Slack |
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
2. **Permissions** - Repository: *Contents* read & write, *Pull requests* read & write, *Checks* read & write,
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

## Layout

```
backend/
├── docker-compose.yml
├── docker/            python.Dockerfile (one recipe, SERVICE build arg) · frontend image · nginx
├── shared/bento_core/ config, db pools, Redis Streams consumer, scoring, URL safety
└── services/
    ├── api/app/       FastAPI gateway (routes/, migrations, security)
    ├── scheduler/  prober/  analyzer/  notifier/  scanner/  advisor/
```

```bash
docker compose logs -f analyzer               # watch incidents open/close
docker compose up -d --scale prober=4         # more probe capacity
docker compose down                           # stop (data kept)
docker compose down -v                        # stop and delete all data
```
