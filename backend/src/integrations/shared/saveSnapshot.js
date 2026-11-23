// src/integrations/shared/saveSnapshot.js
// [Shakshi] THE only place that writes to the snapshots table.
// Every integration must call this — never write to snapshots directly.

import { supabase } from '../../db/client.js';

/**
 * Save raw provider data into the snapshots table.
 *
 * @param {object} params
 * @param {string} params.projectId   - UUID of the project
 * @param {string} params.provider    - 'github' | 'vercel' | 'sentry'
 * @param {object} params.rawData     - The full raw API response to store
 * @returns {Promise<object>}         - The inserted snapshot row
 */
export async function saveSnapshot({ projectId, provider, rawData }) {
  const { data, error } = await supabase
    .from('snapshots')
    .insert({
      project_id: projectId,
      provider,
      raw_data: rawData,
      fetched_at: new Date().toISOString(),
    })
    .select()
    .single();

  if (error) {
    throw new Error(`saveSnapshot failed for ${provider}/${projectId}: ${error.message}`);
  }

  return data;
}
