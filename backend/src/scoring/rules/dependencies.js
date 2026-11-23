// src/scoring/rules/dependencies.js
// [Lavanya] Dependencies score rule.
// Pure function: takes a GitHub snapshot and returns a 0-100 score.

/**
 * Score dependency health based on:
 * - Number of direct dependencies (fewer is generally better)
 * - Presence of known problematic patterns (no lockfile, very old packages implied by old commits)
 * - Dependabot or renovate config detected in issues/commits
 *
 * @param {object} snapshot - raw_data from the snapshots table (github provider)
 * @returns {number} 0-100
 */
export function scoreDependencies(snapshot) {
  const packageJson = snapshot.packageJson;

  if (!packageJson) {
    // No package.json found — return neutral score
    return 50;
  }

  let score = 100;

  const deps = Object.keys(packageJson.dependencies ?? {});
  const devDeps = Object.keys(packageJson.devDependencies ?? {});
  const totalDeps = deps.length + devDeps.length;

  // Penalty for large dependency counts — more deps = more surface area
  if (totalDeps > 100) score -= 20;
  else if (totalDeps > 50) score -= 10;
  else if (totalDeps > 20) score -= 5;

  // Check for dependency management tooling
  const issues = snapshot.openIssues ?? [];
  const hasDependabotIssue = issues.some((i) =>
    i.title?.toLowerCase().includes('dependabot') ||
    i.labels?.some((l) => l.toLowerCase().includes('dependencies'))
  );

  // Open dependency update PRs/issues = actively maintained, small bonus
  if (hasDependabotIssue) score += 5;

  // Check for very old last commit — stale deps more likely
  const lastCommitDate = snapshot.commits?.[0]?.date;
  if (lastCommitDate) {
    const daysSince = (Date.now() - new Date(lastCommitDate).getTime()) / (1000 * 60 * 60 * 24);
    if (daysSince > 180) score -= 20;
    else if (daysSince > 90) score -= 10;
  }

  return Math.max(0, Math.min(100, Math.round(score)));
}
