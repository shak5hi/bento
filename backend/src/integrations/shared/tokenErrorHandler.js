// src/integrations/shared/tokenErrorHandler.js
// [Shakshi] Handles expired or revoked OAuth/API tokens.
// Call this whenever an integration receives a 401 or 403 from a provider.
// Marks the integration as 'needs_reconnect' so the user sees a reconnect prompt.

import { supabase } from '../../db/client.js';

/**
 * Mark an integration as needing reconnection.
 *
 * @param {string} projectId  - UUID of the project
 * @param {string} provider   - 'github' | 'vercel' | 'sentry'
 * @returns {Promise<void>}
 */
export async function handleTokenError(projectId, provider) {
  const { error } = await supabase
    .from('integrations')
    .update({ status: 'needs_reconnect' })
    .eq('project_id', projectId)
    .eq('provider', provider);

  if (error) {
    console.error(`tokenErrorHandler: failed to update status for ${provider}/${projectId}:`, error.message);
  } else {
    console.warn(`tokenErrorHandler: marked ${provider}/${projectId} as needs_reconnect`);
  }
}

/**
 * Wraps an integration fetch function and handles 401/403 automatically.
 *
 * @param {Function} fetchFn    - async function that fetches from the provider
 * @param {string}   projectId  - UUID of the project
 * @param {string}   provider   - 'github' | 'vercel' | 'sentry'
 * @returns {Promise<any|null>} - result of fetchFn, or null if token is broken
 */
export async function withTokenErrorHandling(fetchFn, projectId, provider) {
  try {
    return await fetchFn();
  } catch (err) {
    const status = err?.status ?? err?.response?.status;
    if (status === 401 || status === 403) {
      await handleTokenError(projectId, provider);
      return null;
    }
    throw err;
  }
}
