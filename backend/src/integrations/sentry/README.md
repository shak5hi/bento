# src/integrations/sentry/

**Owner: Shakshi**

This folder will handle the Sentry integration: API key auth, error data fetching, and snapshot creation.

## Status: 🚧 Stub — not yet implemented

## Planned files

| File | Purpose |
|------|---------|
| `fetchData.js` | Call Sentry API to fetch recent issues, error counts, and crash rates |
| `index.js` | Orchestrator: read stored token → fetch → `saveSnapshot()` |

## Auth approach

Sentry uses auth tokens (not OAuth). Users generate a token at https://sentry.io/settings/account/api/auth-tokens/ and paste it in-app.

## Data to fetch

- Open issues (title, level: error/warning/info, count, first seen, last seen)
- Error rate over last 7 days
- Top 5 most frequent errors

## API reference

https://docs.sentry.io/api/projects/list-a-projects-issues/
