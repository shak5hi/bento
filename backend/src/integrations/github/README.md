# src/integrations/github/

**Owner: Shakshi**

This folder handles the GitHub integration: OAuth login, data fetching, and snapshot creation.

## Files

| File | Purpose |
|------|---------|
| `auth.js` | OAuth 2.0 route handlers. Mount these at `/integrations/github/connect` and `/integrations/github/callback` in `server.js`. |
| `fetchData.js` | Pure data-fetching function. Calls GitHub API via Octokit. Returns a structured object — does NOT write to DB. |
| `index.js` | Orchestrator. Reads the stored token, calls `fetchData.js`, then calls `saveSnapshot()`. This is what the scheduler invokes. |

## OAuth Setup

1. Create a GitHub OAuth App at https://github.com/settings/developers
2. Set callback URL to `GITHUB_REDIRECT_URI` in your `.env`
3. Copy Client ID and Secret into `.env`

## Data fetched per sync

- Last 30 commits (date, author, message)
- Open issues (title, labels, age)
- Last 10 CI workflow runs (status, conclusion)
- `package.json` (for dependency scoring)
- Repo metadata (language, default branch)

## Adding more fields

Add to `fetchData.js` → `fetchGitHubData()`. The raw object is stored verbatim in `snapshots.raw_data`, so the scoring engine can read any field you add without a schema change.
