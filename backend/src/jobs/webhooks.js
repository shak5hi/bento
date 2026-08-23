// src/jobs/webhooks.js
// [Shakshi] GitHub webhook receiver.
// Receives push/PR/workflow events from GitHub and triggers an immediate sync.
// Mount this router in server.js at /webhooks.

import { Router } from 'express';
import crypto from 'crypto';
import { config } from '../config/index.js';
import { supabase } from '../db/client.js';
import { syncGitHub } from '../integrations/github/index.js';
import { runScoringEngine } from '../scoring/engine.js';

export const webhooksRouter = Router();

/**
 * Verify the X-Hub-Signature-256 header to ensure the request came from GitHub.
 */
function verifyGitHubSignature(req) {
  const signature = req.headers['x-hub-signature-256'];
  if (!signature) return false;

  const hmac = crypto.createHmac('sha256', config.github.webhookSecret);
  const digest = 'sha256=' + hmac.update(req.rawBody ?? '').digest('hex');

  return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(digest));
}

// POST /webhooks/github
webhooksRouter.post('/github', async (req, res) => {
  if (!verifyGitHubSignature(req)) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  const event = req.headers['x-github-event'];
  const payload = req.body;

  // We care about push, pull_request, and workflow_run events
  const relevantEvents = ['push', 'pull_request', 'workflow_run'];
  if (!relevantEvents.includes(event)) {
    return res.status(200).json({ message: `Event '${event}' ignored` });
  }

  const repoFullName = payload.repository?.full_name;
  const [owner, repo] = repoFullName?.split('/') ?? [];

  if (!owner || !repo) {
    return res.status(400).json({ error: 'Could not parse repository from payload' });
  }

  // Find the Bento project linked to this GitHub repo
  // (requires a github_repo column on projects — add to schema as needed)
  const { data: project } = await supabase
    .from('projects')
    .select('id')
    .eq('github_repo', repoFullName)
    .maybeSingle();

  if (!project) {
    // Not a tracked repo — ignore silently
    return res.status(200).json({ message: 'Repo not tracked' });
  }

  // Trigger a sync immediately in the background
  syncGitHub(project.id, owner, repo)
    .then(() => runScoringEngine(project.id))
    .catch((err) => console.error('[webhook] Sync error:', err.message));

  // Respond immediately — don't wait for the sync to complete
  res.status(202).json({ message: 'Sync triggered' });
});
