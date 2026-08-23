# src/jobs/

**Owner: Shakshi**

This folder contains background jobs: the cron scheduler and the GitHub webhook receiver.

## Files

| File | Purpose |
|------|---------|
| `scheduler.js` | Registers two cron jobs: sync all integrations every 6 hours, and generate AI insights daily at 2am UTC. Call `startScheduler()` from `server.js`. |
| `webhooks.js` | Express router for GitHub webhooks. Verifies the `X-Hub-Signature-256` header, then triggers an immediate sync for the affected project. Mount at `/webhooks` in `server.js`. |

## Cron schedule

| Job | Schedule | What it does |
|-----|----------|-------------|
| `pollAllProjects` | Every 6 hours (`0 */6 * * *`) | Syncs all connected integrations → re-scores |
| `generateAllInsights` | Daily 2am UTC (`0 2 * * *`) | Calls Claude Haiku once per project → caches insight |

## Webhook setup (GitHub)

1. Go to your repo → Settings → Webhooks → Add webhook
2. Set Payload URL to `https://your-domain.com/webhooks/github`
3. Content type: `application/json`
4. Secret: same as `GITHUB_WEBHOOK_SECRET` in `.env`
5. Select events: Push, Pull requests, Workflow runs

## Important

The webhook handler responds with `202 Accepted` immediately and runs the sync in the background — it does not block GitHub's delivery.
