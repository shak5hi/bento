// src/integrations/github/index.js
// [Shakshi] Orchestrator for the GitHub integration.
// Reads the stored token, fetches data, and saves a snapshot.
// This is the function the scheduler calls — one job per project.

import { supabase } from '../../db/client.js';
import { fetchGitHubData } from './fetchData.js';
import { saveSnapshot } from '../shared/saveSnapshot.js';
import { withTokenErrorHandling } from '../shared/tokenErrorHandler.js';

/**
 * Run a full GitHub data sync for a project.
 * Reads the integration's stored access token, fetches fresh data,
 * and writes a new snapshot row.
 *
 * @param {string} projectId  - UUID of the project
 * @param {string} owner      - GitHub org or username
 * @param {string} repo       - Repository name
 * @returns {Promise<object|null>} - The saved snapshot, or null if token is broken
 */
export async function syncGitHub(projectId, owner, repo) {
  // Load the stored access token
  const { data: integration, error } = await supabase
    .from('integrations')
    .select('access_token, status')
    .eq('project_id', projectId)
    .eq('provider', 'github')
    .single();

  if (error || !integration) {
    console.warn(`syncGitHub: no GitHub integration found for project ${projectId}`);
    return null;
  }

  if (integration.status === 'needs_reconnect') {
    console.warn(`syncGitHub: project ${projectId} needs GitHub reconnect — skipping`);
    return null;
  }

  // Fetch with automatic token error handling
  const rawData = await withTokenErrorHandling(
    () => fetchGitHubData(integration.access_token, owner, repo),
    projectId,
    'github'
  );

  if (!rawData) return null;

  // Persist via the shared helper — the only path to the snapshots table
  const snapshot = await saveSnapshot({
    projectId,
    provider: 'github',
    rawData,
  });

  console.log(`syncGitHub: saved snapshot ${snapshot.id} for project ${projectId}`);
  return snapshot;
}
