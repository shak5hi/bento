// src/scoring/rules/performance.js
// [Lavanya] Performance score rule.
// Pure function: takes a snapshot and returns a 0-100 score.
// Currently uses GitHub signals as a proxy; will incorporate Sentry data later.

/**
 * Score performance health based on:
 * - Open issues labelled 'performance', 'slow', 'memory', 'timeout'
 * - CI run duration trends (long runs may indicate bloat)
 * - Sentry error rate (if available — future)
 *
 * @param {object} snapshot - raw_data from the snapshots table
 * @returns {number} 0-100
 */
export function scorePerformance(snapshot) {
  let score = 80; // start optimistic — performance issues are usually explicitly filed

  const issues = snapshot.openIssues ?? [];

  const perfLabels = ['performance', 'slow', 'memory', 'timeout', 'latency', 'bottleneck', 'oom'];

  const perfIssues = issues.filter((issue) =>
    issue.labels?.some((label) =>
      perfLabels.some((pl) => label.toLowerCase().includes(pl))
    ) ||
    perfLabels.some((pl) => issue.title?.toLowerCase().includes(pl))
  );

  // -10 points per open performance issue, capped at -40
  const penalty = Math.min(perfIssues.length * 10, 40);
  score -= penalty;

  // TODO: incorporate Sentry crash-free rate and error volume once available
  // if (snapshot.sentryErrorRate) { ... }

  return Math.max(0, Math.min(100, Math.round(score)));
}
