// src/ai/promptTemplate.js
// [Lavanya] Builds the prompt sent to Claude Haiku.
// Keep this in its own file so it's easy to iterate on without touching the API call logic.

/**
 * Build the prompt for generating a plain-English project health insight.
 *
 * @param {object} params
 * @param {string} params.projectName
 * @param {object} params.scores     - { security: 85, testing: 72, ... , overall: 79 }
 * @param {object} params.snapshot   - raw_data from the latest GitHub snapshot
 * @returns {string}                 - The complete prompt string
 */
export function buildInsightPrompt({ projectName, scores, snapshot }) {
  const worstCategory = Object.entries(scores)
    .filter(([cat]) => cat !== 'overall')
    .sort(([, a], [, b]) => a - b)[0];

  const openIssueCount = snapshot.openIssues?.length ?? 0;
  const lastCommitDate = snapshot.commits?.[0]?.date ?? 'unknown';
  const latestCiConclusion = snapshot.ciRuns?.[0]?.conclusion ?? 'unknown';

  return `You are Pickle, an AI assistant for Bento — an engineering health platform.

Your job is to write a 1-2 sentence plain-English summary of a project's engineering health.
Be direct, helpful, and actionable. Avoid jargon. Sound like a senior engineer giving a quick status update.

PROJECT: ${projectName}
OVERALL HEALTH SCORE: ${scores.overall}/100

CATEGORY SCORES:
- Security: ${scores.security}/100
- Testing: ${scores.testing}/100
- Dependencies: ${scores.dependencies}/100
- Deployment: ${scores.deployment}/100
- Performance: ${scores.performance}/100

KEY SIGNALS:
- Open issues: ${openIssueCount}
- Last commit: ${lastCommitDate}
- Latest CI run: ${latestCiConclusion}
- Weakest area: ${worstCategory[0]} (${worstCategory[1]}/100)

Write a 1-2 sentence insight that:
1. Names the biggest risk or opportunity
2. Suggests one specific, actionable next step

Do not repeat the scores. Do not use bullet points. Write in plain prose.`.trim();
}
