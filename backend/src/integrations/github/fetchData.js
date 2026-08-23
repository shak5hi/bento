// src/integrations/github/fetchData.js
// [Shakshi] Fetches all data needed for scoring from a GitHub repo.
// Returns a single structured object — does NOT write to the DB.
// The caller (index.js) passes the result to saveSnapshot().

import { Octokit } from '@octokit/rest';

/**
 * Fetch commits, open issues, workflow runs (CI), and package.json from a repo.
 *
 * @param {string} accessToken  - GitHub OAuth token
 * @param {string} owner        - GitHub org or username
 * @param {string} repo         - Repository name
 * @returns {Promise<object>}   - Structured snapshot data
 */
export async function fetchGitHubData(accessToken, owner, repo) {
  const octokit = new Octokit({ auth: accessToken });

  // Run all fetches in parallel for speed
  const [commitsRes, issuesRes, workflowRunsRes, packageJsonRes, repoRes] = await Promise.allSettled([
    // Last 30 commits
    octokit.repos.listCommits({ owner, repo, per_page: 30 }),

    // Open issues (excludes PRs)
    octokit.issues.listForRepo({ owner, repo, state: 'open', per_page: 50 }),

    // Most recent workflow runs (CI)
    octokit.actions.listWorkflowRunsForRepo({ owner, repo, per_page: 10 }),

    // package.json for dependency analysis
    octokit.repos.getContent({ owner, repo, path: 'package.json' }).catch(() => null),

    // Repo metadata (open issues count, has_issues, default branch)
    octokit.repos.get({ owner, repo }),
  ]);

  const getValue = (res) => (res.status === 'fulfilled' ? res.value?.data : null);

  const commits = getValue(commitsRes) ?? [];
  const issues = getValue(issuesRes) ?? [];
  const workflowRuns = getValue(workflowRunsRes)?.workflow_runs ?? [];
  const packageJsonRaw = getValue(packageJsonRes);
  const repoMeta = getValue(repoRes);

  // Decode package.json from base64 if present
  let packageJson = null;
  if (packageJsonRaw?.content) {
    try {
      packageJson = JSON.parse(Buffer.from(packageJsonRaw.content, 'base64').toString('utf8'));
    } catch {
      packageJson = null;
    }
  }

  return {
    owner,
    repo,
    fetchedAt: new Date().toISOString(),
    commits: commits.map((c) => ({
      sha: c.sha,
      message: c.commit?.message,
      date: c.commit?.author?.date,
      author: c.commit?.author?.name,
    })),
    openIssues: issues
      .filter((i) => !i.pull_request) // exclude PRs
      .map((i) => ({
        id: i.number,
        title: i.title,
        labels: i.labels.map((l) => l.name),
        createdAt: i.created_at,
      })),
    ciRuns: workflowRuns.map((r) => ({
      id: r.id,
      name: r.name,
      status: r.status,
      conclusion: r.conclusion,
      createdAt: r.created_at,
    })),
    packageJson,
    repoMeta: repoMeta
      ? {
          defaultBranch: repoMeta.default_branch,
          openIssuesCount: repoMeta.open_issues_count,
          hasIssues: repoMeta.has_issues,
          stargazersCount: repoMeta.stargazers_count,
          language: repoMeta.language,
        }
      : null,
  };
}
