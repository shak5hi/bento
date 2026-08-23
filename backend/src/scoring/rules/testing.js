// src/scoring/rules/testing.js
// [Lavanya] Testing score rule.
// Pure function: takes a GitHub snapshot and returns a 0-100 score.

/**
 * Score testing health based on:
 * - Whether CI workflow runs are passing
 * - CI failure rate in recent runs
 * - Presence of a test script in package.json
 *
 * @param {object} snapshot - raw_data from the snapshots table (github provider)
 * @returns {number} 0-100
 */
export function scoreTesting(snapshot) {
  let score = 50; // start neutral — we might not have full info

  const ciRuns = snapshot.ciRuns ?? [];
  const packageJson = snapshot.packageJson;

  // Check for test script in package.json
  const hasTestScript =
    packageJson?.scripts?.test &&
    !packageJson.scripts.test.includes('no test specified');

  if (hasTestScript) score += 20;

  // Analyse recent CI runs
  if (ciRuns.length > 0) {
    const completed = ciRuns.filter((r) => r.status === 'completed');
    const passed = completed.filter((r) => r.conclusion === 'success');
    const passRate = completed.length > 0 ? passed.length / completed.length : 0;

    // passRate 0-1 → contributes 0-30 points
    score += Math.round(passRate * 30);

    // Penalty if the most recent run failed
    const latest = ciRuns[0];
    if (latest?.conclusion === 'failure') score -= 20;
  } else {
    // No CI runs at all — slight penalty
    score -= 10;
  }

  return Math.max(0, Math.min(100, Math.round(score)));
}
