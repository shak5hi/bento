# src/integrations/shared/

**Owner: Shakshi**

This folder contains utilities shared across all integrations. Every integration imports from here — no integration should duplicate this logic.

## Files

| File | Purpose |
|------|---------|
| `saveSnapshot.js` | **The only function that writes to the `snapshots` table.** All integrations must call this instead of writing to the DB directly. |
| `tokenErrorHandler.js` | Handles 401/403 responses from provider APIs. Marks the integration as `needs_reconnect` in the DB and returns `null` so the caller can skip gracefully. |

## How to use `saveSnapshot`

```js
import { saveSnapshot } from '../shared/saveSnapshot.js';

await saveSnapshot({
  projectId: 'uuid-here',
  provider: 'github',   // or 'vercel' | 'sentry'
  rawData: { commits: [...], issues: [...] },
});
```

## How to use `withTokenErrorHandling`

```js
import { withTokenErrorHandling } from '../shared/tokenErrorHandler.js';

const data = await withTokenErrorHandling(
  () => octokit.repos.get({ owner, repo }),
  projectId,
  'github'
);
if (!data) return; // token was invalid, integration marked as needs_reconnect
```
