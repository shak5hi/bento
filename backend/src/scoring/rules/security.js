// src/scoring/rules/security.js
// [Lavanya] Security score rule.
// Pure function: takes a GitHub snapshot and returns a 0-100 score.

/**
 * Score security health based on:
 * - Presence of known security labels in open issues (CVE, vulnerability, security)
 * - High/critical security issues → heavy penalty
 * - Dependabot alerts (if present in snapshot)
 *
 * @param {object} snapshot - raw_data from the snapshots table (github provider)
 * @returns {number} 0-100
 */
export function scoreSecrity(snapshot) {
  let score = 100;

  const issues = snapshot.openIssues ?? [];

  const securityLabels = ['security', 'vulnerability', 'cve', 'critical', 'dependabot'];

  const securityIssues = issues.filter((issue) =>
    issue.labels?.some((label) =>
      securityLabels.some((sl) => label.toLowerCase().includes(sl))
    )
  );

  // -15 points per security issue, capped at -60
  const penalty = Math.min(securityIssues.length * 15, 60);
  score -= penalty;

  // Bonus: recent commits show active maintenance (+5 if commit in last 7 days)
  const recentCommit = snapshot.commits?.[0];
  if (recentCommit?.date) {
    const daysSince = (Date.now() - new Date(recentCommit.date).getTime()) / (1000 * 60 * 60 * 24);
    if (daysSince <= 7) score += 5;
  }

  return Math.max(0, Math.min(100, Math.round(score)));
}
