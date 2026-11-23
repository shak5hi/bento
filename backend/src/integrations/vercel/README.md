# src/integrations/vercel/

**Owner: Shakshi**

This folder will handle the Vercel integration: API key auth, deployment data fetching, and snapshot creation.

## Status: 🚧 Stub — not yet implemented

## Planned files

| File | Purpose |
|------|---------|
| `fetchData.js` | Call Vercel REST API v6 to fetch recent deployments, build errors, and preview URLs |
| `index.js` | Orchestrator: read stored token → fetch → `saveSnapshot()` |

## Auth approach

Vercel uses personal API tokens (not OAuth). The user pastes their token in-app; we store it in `integrations.access_token`.

## Data to fetch

- Last N deployments (status: ready/error/building)
- Build errors and logs
- Associated git commit SHA (for linking to GitHub data)

## API reference

https://vercel.com/docs/rest-api/endpoints/deployments
