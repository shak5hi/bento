// src/scoring/rules/deployment.js
// [Lavanya] Deployment score rule.
// Pure function: takes a combined snapshot object and returns a 0-100 score.
// Reads from GitHub CI runs; will also read Vercel data once that integration is live.

/**
 * Score deployment health based on:
 * - Recent CI workflow run conclusions
 * - Deployment frequency (commit cadence as a proxy)
 * - Vercel deployment status (if available in snapshot)
 *
 * @param {object} snapshot - raw_data from the snapshots table
 * @returns {number} 0-100
 */
export function scoreDeployment(snapshot) {
  let score = 60; // start moderately — deployment data may be partial

  const ciRuns = snapshot.ciRuns ?? [];

  if (ciRuns.length === 0) {
    // No deployment pipeline detected
    return 40;
  }

  // Look at the last 5 CI runs
  const recent = ciRuns.slice(0, 5);
  const successful = recent.filter((r) => r.conclusion === 'success');
  const successRate = successful.length / recent.length;

  score += Math.round(successRate * 30);

  // Penalty for consecutive failures
  const latestTwo = recent.slice(0, 2);
  const bothFailed = latestTwo.every((r) => r.conclusion === 'failure');
  if (bothFailed) score -= 25;

  // Deployment frequency: commits per week as a proxy
  const commits = snapshot.commits ?? [];
  const oneWeekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const recentCommits = commits.filter(
    (c) => c.date && new Date(c.date).getTime() > oneWeekAgo
  );

  if (recentCommits.length >= 5) score += 10;
  else if (recentCommits.length >= 2) score += 5;
  else if (recentCommits.length === 0) score -= 10;

  // TODO: incorporate vercel snapshot data when available
  // if (snapshot.vercelDeployments) { ... }

  return Math.max(0, Math.min(100, Math.round(score)));
}
