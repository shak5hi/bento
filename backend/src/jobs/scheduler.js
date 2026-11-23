// src/jobs/scheduler.js
// [Shakshi] Cron scheduler — polls all connected projects every 6 hours.
// Import and call startScheduler() from server.js once on startup.

import cron from 'node-cron';
import { supabase } from '../db/client.js';
import { syncGitHub } from '../integrations/github/index.js';
import { syncVercel } from '../integrations/vercel/index.js';
import { syncSentry } from '../integrations/sentry/index.js';
import { runScoringEngine } from '../scoring/engine.js';
import { generateInsight } from '../ai/generateInsight.js';

/**
 * Sync all connected integrations for every project, then re-score.
 * Called by the cron job and can also be triggered manually for testing.
 */
export async function pollAllProjects() {
  console.log('[scheduler] Starting poll cycle...');

  // Load all projects that have at least one connected integration
  const { data: projects, error } = await supabase
    .from('projects')
    .select('id, name, integrations(provider, status)')
    .eq('integrations.status', 'connected');

  if (error) {
    console.error('[scheduler] Failed to load projects:', error.message);
    return;
  }

  for (const project of projects ?? []) {
    console.log(`[scheduler] Processing project: ${project.name} (${project.id})`);

    const providers = project.integrations?.map((i) => i.provider) ?? [];

    // Run integrations in parallel per project
    await Promise.allSettled([
      providers.includes('github')
        ? syncGitHub(project.id, project.githubOwner, project.githubRepo)
        : Promise.resolve(),
      providers.includes('vercel')
        ? syncVercel(project.id, project.vercelProjectId)
        : Promise.resolve(),
      providers.includes('sentry')
        ? syncSentry(project.id, project.sentryOrgSlug, project.sentryProjectSlug)
        : Promise.resolve(),
    ]);

    // Re-score after syncing
    await runScoringEngine(project.id).catch((err) =>
      console.error(`[scheduler] Scoring failed for ${project.id}:`, err.message)
    );
  }

  console.log('[scheduler] Poll cycle complete.');
}

/**
 * Generate AI insights for all projects once per day (2am UTC).
 */
async function generateAllInsights() {
  console.log('[scheduler] Generating AI insights...');

  const { data: projects } = await supabase.from('projects').select('id');
  for (const project of projects ?? []) {
    await generateInsight(project.id).catch((err) =>
      console.error(`[scheduler] Insight generation failed for ${project.id}:`, err.message)
    );
  }

  console.log('[scheduler] AI insights done.');
}

/**
 * Start all scheduled jobs. Call this once from server.js.
 */
export function startScheduler() {
  // Sync all projects every 6 hours
  cron.schedule('0 */6 * * *', pollAllProjects);

  // Generate AI insights daily at 2am UTC
  cron.schedule('0 2 * * *', generateAllInsights);

  console.log('[scheduler] Jobs scheduled: sync every 6h, AI insights daily at 2am UTC');
}
