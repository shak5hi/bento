// src/reports/weeklyReport.js
// [Lavanya] Generates a week-over-week score comparison report for each user.
// Called by the scheduler every Monday. Saves the report to the reports table.

import { supabase } from '../db/client.js';
import { sendWeeklyEmail } from './sendEmail.js';

/**
 * Generate and send weekly reports for all users.
 */
export async function generateAndSendWeeklyReports() {
  console.log('[reports] Generating weekly reports...');

  const { data: users, error } = await supabase.from('users').select('id, email');
  if (error) {
    console.error('[reports] Failed to load users:', error.message);
    return;
  }

  for (const user of users ?? []) {
    try {
      await generateUserReport(user);
    } catch (err) {
      console.error(`[reports] Failed for user ${user.id}:`, err.message);
    }
  }

  console.log('[reports] Weekly reports done.');
}

/**
 * Generate a report for a single user.
 *
 * @param {{ id: string, email: string }} user
 */
async function generateUserReport(user) {
  const now = new Date();
  const oneWeekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const twoWeeksAgo = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);

  // Load all projects for the user
  const { data: projects } = await supabase
    .from('projects')
    .select('id, name')
    .eq('user_id', user.id);

  if (!projects?.length) return;

  const projectIds = projects.map((p) => p.id);

  // Load scores for this week and last week
  const { data: thisWeekScores } = await supabase
    .from('scores')
    .select('project_id, category, value')
    .in('project_id', projectIds)
    .eq('category', 'overall')
    .gte('scored_at', oneWeekAgo.toISOString())
    .order('scored_at', { ascending: false });

  const { data: lastWeekScores } = await supabase
    .from('scores')
    .select('project_id, category, value')
    .in('project_id', projectIds)
    .eq('category', 'overall')
    .gte('scored_at', twoWeeksAgo.toISOString())
    .lt('scored_at', oneWeekAgo.toISOString())
    .order('scored_at', { ascending: false });

  // Latest score per project this week / last week
  const thisWeekMap = {};
  for (const s of thisWeekScores ?? []) {
    if (!thisWeekMap[s.project_id]) thisWeekMap[s.project_id] = s.value;
  }

  const lastWeekMap = {};
  for (const s of lastWeekScores ?? []) {
    if (!lastWeekMap[s.project_id]) lastWeekMap[s.project_id] = s.value;
  }

  // Build report content
  const projectSummaries = projects.map((project) => {
    const thisScore = thisWeekMap[project.id] ?? null;
    const lastScore = lastWeekMap[project.id] ?? null;
    const delta = thisScore != null && lastScore != null ? thisScore - lastScore : null;

    return {
      projectId: project.id,
      projectName: project.name,
      overallScore: thisScore,
      previousScore: lastScore,
      delta,
      trend: delta == null ? 'unknown' : delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat',
    };
  });

  const reportContent = {
    weekEnding: now.toISOString(),
    projects: projectSummaries,
  };

  // Save to DB
  await supabase.from('reports').insert({
    user_id: user.id,
    content: reportContent,
    sent_at: now.toISOString(),
  });

  // Send email
  await sendWeeklyEmail({ to: user.email, report: reportContent });

  console.log(`[reports] Report sent to ${user.email}`);
}
