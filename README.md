# Bento — Backend

Bento is an engineering health platform. It connects to the tools you already use — GitHub, Vercel, Sentry, and more — watches every project you own, and tells you what actually deserves your attention today. Pickle, Bento's AI assistant, turns raw engineering data into plain-English priorities instead of another wall of dashboards.

This repository contains the backend service: integrations, the health scoring engine, the AI insight layer, the API, and the weekly report system.

## How it works

1. **Connect** — a user links their tools (GitHub, Vercel, Sentry, etc.) once.
2. **Ingest** — scheduled jobs poll each tool's API and store raw data as snapshots.
3. **Score** — a rules-based engine turns raw data into a 0–100 health score per category (security, testing, dependencies, deployment, performance).
4. **Explain** — Pickle, the AI layer, reads the scored data and writes short, plain-English insights and suggested fixes.
5. **Serve** — the API exposes portfolio health, per-project detail, today's top priorities, and score trends to the frontend.
6. **Report** — every Monday, an automated email summarizes what changed, what's at risk, and what to focus on next.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Runtime | Node.js + Express | Simple, well-documented, easy to deploy |
| Database | Supabase (Postgres) | Free tier, built-in auth, generous limits for an MVP |
| Scheduling | node-cron | Runs polling and reports without a separate worker service |
| AI | Claude Haiku (Anthropic API) | Low-cost model, called on a schedule and cached, never per request |
| Email | Resend | Free tier covers weekly reports comfortably |
| Hosting | Railway / Render | Free or low-cost tiers, auto-deploys from GitHub |

Designed to run on close to $0/month until real usage requires scaling up.

## Project structure

```
src/
├── server.js                 Entry point
├── integrations/             Connects to external tools and pulls raw data
│   ├── github/
│   ├── vercel/
│   ├── sentry/
│   └── shared/                Common helpers: saving snapshots, handling errors
├── jobs/                      Scheduled polling and webhook handlers
├── scoring/                   Turns raw data into 0–100 health scores
│   └── rules/                 One scoring rule per category
├── ai/                        Pickle: generates plain-English insights
├── api/
│   ├── routes/                Endpoints consumed by the frontend
│   └── middleware/            Auth and request handling
├── reports/                   Weekly report generation and email delivery
├── db/                        Schema, migrations, and database client
└── config/                    Environment variable loading

tests/                         Unit and integration tests
```

Every folder contains its own `README.md` describing what belongs there.

## Getting started

1. Clone the repository and install dependencies:
   ```
   npm install
   ```
2. Copy the environment template and fill in your keys:
   ```
   cp .env.example .env
   ```
3. Run the schema in `src/db/schema.sql` against your Supabase project.
4. Start the development server:
   ```
   npm run dev
   ```

## Environment variables

See `.env.example` for the full list. At minimum you'll need a Supabase URL and service key, a GitHub OAuth app, and an Anthropic API key for Pickle.

## Database schema

| Table | Purpose |
|---|---|
| `users` | Registered accounts |
| `projects` | Projects a user has added to Bento |
| `integrations` | Connected tools and their access tokens, per project |
| `snapshots` | Raw data pulled from each integration, timestamped |
| `scores` | Calculated health scores per category, timestamped |
| `reports` | Generated weekly report content, per user |

Full definitions live in `src/db/schema.sql`.

## Ownership

This project is built by two contributors with a clean split of responsibility. See `OWNERSHIP.md` for the current folder-level breakdown.

| Area | Owner |
|---|---|
| Integrations & data ingestion | Shakshi |
| Scoring engine, AI layer, API, reports | Lavanya |
| Database schema & config | Shared |

## Roadmap

- [x] Core integrations (GitHub, Vercel, Sentry)
- [x] Rules-based health scoring
- [x] Pickle AI insights
- [x] Weekly email reports
- [ ] Additional integrations (Cloudflare, Docker, GitHub Actions)
- [ ] Automated fixes: Pickle proposes pull requests for routine issues, always pending human approval

## License

Proprietary — all rights reserved.

