# Bento Backend — Ownership Map

Every folder in `src/` has a primary owner. Work in your own area and coordinate via PR when touching shared code.

| Path | Owner | Responsibility |
|------|-------|---------------|
| `src/integrations/github/` | **Shakshi** | GitHub OAuth + data fetch |
| `src/integrations/vercel/` | **Shakshi** | Vercel API key auth + deployments |
| `src/integrations/sentry/` | **Shakshi** | Sentry API key auth + errors |
| `src/integrations/shared/` | **Shakshi** | `saveSnapshot()` helper + token error handler |
| `src/jobs/` | **Shakshi** | Cron scheduler + GitHub webhook receiver |
| `src/scoring/` | **Lavanya** | Scoring engine + rules |
| `src/ai/` | **Lavanya** | Prompt template + Claude Haiku calls |
| `src/api/routes/` | **Lavanya** | REST endpoints for dashboard |
| `src/api/middleware/` | **Lavanya** | Supabase Auth middleware |
| `src/reports/` | **Lavanya** | Weekly report generation + email sending |
| `src/db/` | **Shared** | Schema SQL + Supabase client |
| `src/config/` | **Shared** | Env var loading + validation |
| `src/server.js` | **Shared** | Express entry point |
| `tests/shakshi/` | **Shakshi** | Shakshi's unit tests |
| `tests/lavanya/` | **Lavanya** | Lavanya's unit tests |

## Ground Rules

1. **Integrations → snapshots only.** Every integration must write raw data through `saveSnapshot()` in `src/integrations/shared/`. No integration should write directly to any other table.
2. **Scoring + AI → read only.** The scoring engine and AI layer read from `snapshots`/`scores` only — they never call an external API.
3. **AI is scheduled, never live.** `generateInsight.js` runs on a cron schedule and caches results in the DB. It is never called per HTTP request.
4. **One file, one job.** Keep files small and single-purpose.
