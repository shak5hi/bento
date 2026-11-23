// src/integrations/sentry/fetchData.js
// [Shakshi] Fetches error/issue data from the Sentry API.
// TODO: implement with Sentry REST API — https://docs.sentry.io/api/

/**
 * Fetch recent issues and error counts from a Sentry project.
 *
 * @param {string} authToken    - Sentry auth token (stored in integrations table)
 * @param {string} orgSlug      - Sentry organization slug
 * @param {string} projectSlug  - Sentry project slug
 * @returns {Promise<object>}
 */
export async function fetchSentryData(authToken, orgSlug, projectSlug) {
  // TODO: implement
  // const res = await fetch(
  //   `https://sentry.io/api/0/projects/${orgSlug}/${projectSlug}/issues/?limit=25`,
  //   { headers: { Authorization: `Bearer ${authToken}` } }
  // );
  // const issues = await res.json();
  // return { issues, fetchedAt: new Date().toISOString() };

  throw new Error('Sentry integration not yet implemented');
}
