// src/integrations/vercel/index.js
// [Shakshi] Orchestrator for the Vercel integration.
// TODO: implement after fetchData.js is complete.

import { supabase } from '../../db/client.js';
import { fetchVercelData } from './fetchData.js';
import { saveSnapshot } from '../shared/saveSnapshot.js';
import { withTokenErrorHandling } from '../shared/tokenErrorHandler.js';

/**
 * Run a full Vercel data sync for a project.
 *
 * @param {string} projectId       - Bento project UUID
 * @param {string} vercelProjectId - Vercel project ID
 * @returns {Promise<object|null>}
 */
export async function syncVercel(projectId, vercelProjectId) {
  const { data: integration, error } = await supabase
    .from('integrations')
    .select('access_token, status')
    .eq('project_id', projectId)
    .eq('provider', 'vercel')
    .single();

  if (error || !integration || integration.status === 'needs_reconnect') return null;

  const rawData = await withTokenErrorHandling(
    () => fetchVercelData(integration.access_token, vercelProjectId),
    projectId,
    'vercel'
  );

  if (!rawData) return null;

  return saveSnapshot({ projectId, provider: 'vercel', rawData });
}
