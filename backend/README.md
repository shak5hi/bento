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
| **scanner** | Fetches exactly one commit (shallow, no hooks, size cap, unprivileged, tmpfs) and runs static checks: committed `.env` files, missing tests / CI / README / lockfile, and known-vulnerable dependencies via [OSV](https://osv.dev). Repository code is never executed. GitHub's duplicate deliveries are skipped by commit SHA. |
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
| `POST /webhooks/github` | push webhook (needs `GITHUB_WEBHOOK_SECRET`) |
| `GET /system` | pipeline status for the dashboard |

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
