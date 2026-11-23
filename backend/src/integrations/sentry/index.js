// src/integrations/sentry/index.js
// [Shakshi] Orchestrator for the Sentry integration.
// TODO: implement after fetchData.js is complete.

import { supabase } from '../../db/client.js';
import { fetchSentryData } from './fetchData.js';
import { saveSnapshot } from '../shared/saveSnapshot.js';
import { withTokenErrorHandling } from '../shared/tokenErrorHandler.js';

/**
 * Run a full Sentry data sync for a project.
 *
 * @param {string} projectId    - Bento project UUID
 * @param {string} orgSlug      - Sentry organization slug
 * @param {string} projectSlug  - Sentry project slug
 * @returns {Promise<object|null>}
 */
export async function syncSentry(projectId, orgSlug, projectSlug) {
  const { data: integration, error } = await supabase
    .from('integrations')
    .select('access_token, status')
    .eq('project_id', projectId)
    .eq('provider', 'sentry')
    .single();

  if (error || !integration || integration.status === 'needs_reconnect') return null;

  const rawData = await withTokenErrorHandling(
    () => fetchSentryData(integration.access_token, orgSlug, projectSlug),
    projectId,
    'sentry'
  );

  if (!rawData) return null;

  return saveSnapshot({ projectId, provider: 'sentry', rawData });
}
