// src/integrations/github/auth.js
// [Shakshi] GitHub OAuth 2.0 flow.
// Exposes two Express route handlers: redirectToGitHub and handleCallback.

import { config } from '../../config/index.js';
import { supabase } from '../../db/client.js';

const GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize';
const GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token';

const SCOPES = ['repo', 'read:user', 'read:org'].join(' ');

/**
 * GET /integrations/github/connect
 * Redirects the user to GitHub's OAuth consent screen.
 * Expects req.query.projectId to be passed as the state param so we know
 * which project to attach the token to on return.
 */
export function redirectToGitHub(req, res) {
  const { projectId } = req.query;
  if (!projectId) {
    return res.status(400).json({ error: 'projectId is required' });
  }

  const params = new URLSearchParams({
    client_id: config.github.clientId,
    redirect_uri: config.github.redirectUri,
    scope: SCOPES,
    state: projectId, // use projectId as CSRF state
  });

  res.redirect(`${GITHUB_AUTHORIZE_URL}?${params}`);
}

/**
 * GET /integrations/github/callback
 * GitHub redirects here after the user grants access.
 * Exchanges the code for an access token and stores it in the integrations table.
 */
export async function handleCallback(req, res) {
  const { code, state: projectId } = req.query;

  if (!code || !projectId) {
    return res.status(400).json({ error: 'Missing code or state' });
  }

  // Exchange code for access token
  const tokenRes = await fetch(GITHUB_TOKEN_URL, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: config.github.clientId,
      client_secret: config.github.clientSecret,
      code,
      redirect_uri: config.github.redirectUri,
    }),
  });

  const tokenData = await tokenRes.json();

  if (tokenData.error) {
    return res.status(400).json({ error: tokenData.error_description || tokenData.error });
  }

  const accessToken = tokenData.access_token;

  // Upsert the integration row
  const { error } = await supabase.from('integrations').upsert({
    project_id: projectId,
    provider: 'github',
    access_token: accessToken,
    status: 'connected',
  }, { onConflict: 'project_id,provider' });

  if (error) {
    return res.status(500).json({ error: 'Failed to store GitHub token' });
  }

  // Redirect back to frontend
  res.redirect(`${config.frontendUrl}/projects/${projectId}?github=connected`);
}
