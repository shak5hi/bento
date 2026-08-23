// src/integrations/vercel/fetchData.js
// [Shakshi] Fetches deployment data from the Vercel API.
// TODO: implement with Vercel API v6 — https://vercel.com/docs/rest-api

import { config } from '../../config/index.js';

/**
 * Fetch recent deployments for a Vercel project.
 *
 * @param {string} accessToken  - User's Vercel API token (stored in integrations table)
 * @param {string} vercelProjectId - Vercel project ID (stored in integrations metadata)
 * @returns {Promise<object>}
 */
export async function fetchVercelData(accessToken, vercelProjectId) {
  // TODO: implement
  // const res = await fetch(`https://api.vercel.com/v6/deployments?projectId=${vercelProjectId}`, {
  //   headers: { Authorization: `Bearer ${accessToken}` },
  // });
  // const data = await res.json();
  // return { deployments: data.deployments };

  throw new Error('Vercel integration not yet implemented');
}
