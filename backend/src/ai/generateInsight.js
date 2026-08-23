// src/ai/generateInsight.js
// [Lavanya] Calls Claude Haiku to generate a plain-English project health insight.
// This is NEVER called per HTTP request. It runs on a cron schedule (daily at 2am UTC)
// and caches the result in the ai_insights table.

import Anthropic from '@anthropic-ai/sdk';
import { supabase } from '../db/client.js';
import { config } from '../config/index.js';
import { buildInsightPrompt } from './promptTemplate.js';

const anthropic = new Anthropic({ apiKey: config.anthropic.apiKey });

/**
 * Load the latest scores for a project as a score object.
 *
 * @param {string} projectId
 * @returns {Promise<object|null>} { security, testing, dependencies, deployment, performance, overall }
 */
async function getLatestScores(projectId) {
  const categories = ['security', 'testing', 'dependencies', 'deployment', 'performance', 'overall'];

  const { data, error } = await supabase
    .from('scores')
    .select('category, value')
    .eq('project_id', projectId)
    .in('category', categories)
    .order('scored_at', { ascending: false })
    .limit(categories.length * 2); // get recent rows for each category

  if (error || !data?.length) return null;

  // Take the most recent score per category
  const scores = {};
  for (const category of categories) {
    const row = data.find((r) => r.category === category);
    if (row) scores[category] = Math.round(row.value);
  }

  return Object.keys(scores).length === categories.length ? scores : null;
}

/**
 * Load the latest GitHub snapshot for a project.
 *
 * @param {string} projectId
 * @returns {Promise<object|null>}
 */
async function getLatestSnapshot(projectId) {
  const { data, error } = await supabase
    .from('snapshots')
    .select('raw_data')
    .eq('project_id', projectId)
    .eq('provider', 'github')
    .order('fetched_at', { ascending: false })
    .limit(1)
    .maybeSingle();

  return error ? null : (data?.raw_data ?? null);
}

/**
 * Generate and cache a plain-English insight for a project using Claude Haiku.
 * Skips generation if an insight was already generated today.
 *
 * @param {string} projectId  - UUID of the project
 * @returns {Promise<string|null>} - The generated insight text, or null if skipped
 */
export async function generateInsight(projectId) {
  // Check if we already generated an insight today
  const startOfDay = new Date();
  startOfDay.setUTCHours(0, 0, 0, 0);

  const { data: existing } = await supabase
    .from('ai_insights')
    .select('insight')
    .eq('project_id', projectId)
    .gte('generated_at', startOfDay.toISOString())
    .maybeSingle();

  if (existing) {
    console.log(`[ai] Insight already generated today for project ${projectId} — skipping`);
    return existing.insight;
  }

  // Load data needed for the prompt
  const [project, scores, snapshot] = await Promise.all([
    supabase.from('projects').select('name').eq('id', projectId).single().then((r) => r.data),
    getLatestScores(projectId),
    getLatestSnapshot(projectId),
  ]);

  if (!scores || !snapshot) {
    console.warn(`[ai] Missing scores or snapshot for project ${projectId} — skipping`);
    return null;
  }

  const prompt = buildInsightPrompt({
    projectName: project?.name ?? 'Unknown Project',
    scores,
    snapshot,
  });

  // Call Claude Haiku — cheapest Anthropic model
  const message = await anthropic.messages.create({
    model: 'claude-haiku-4-5',
    max_tokens: 150,
    messages: [{ role: 'user', content: prompt }],
  });

  const insight = message.content[0]?.text?.trim() ?? '';

  if (!insight) {
    console.warn(`[ai] Empty response from Claude for project ${projectId}`);
    return null;
  }

  // Cache in DB
  await supabase.from('ai_insights').insert({
    project_id: projectId,
    insight,
    generated_at: new Date().toISOString(),
  });

  console.log(`[ai] Generated insight for project ${projectId}`);
  return insight;
}
