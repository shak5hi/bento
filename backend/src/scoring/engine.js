// src/scoring/engine.js
// [Lavanya] The scoring engine.
// Reads the latest snapshot for a project, runs it through all 5 rules,
// computes an overall score, and persists all 6 score rows to the DB.
// Never calls any external API — only reads from snapshots, writes to scores.

import { supabase } from '../db/client.js';
import { scoreSecrity } from './rules/security.js';
import { scoreTesting } from './rules/testing.js';
import { scoreDependencies } from './rules/dependencies.js';
import { scoreDeployment } from './rules/deployment.js';
import { scorePerformance } from './rules/performance.js';

// Category weights for the overall score (must sum to 1)
const WEIGHTS = {
  security: 0.30,
  testing: 0.25,
  dependencies: 0.20,
  deployment: 0.15,
  performance: 0.10,
};

/**
 * Load the latest snapshot for a given project and provider.
 *
 * @param {string} projectId
 * @param {string} provider
 * @returns {Promise<object|null>} raw_data or null
 */
async function getLatestSnapshot(projectId, provider) {
  const { data, error } = await supabase
    .from('snapshots')
    .select('raw_data')
    .eq('project_id', projectId)
    .eq('provider', provider)
    .order('fetched_at', { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) {
    console.error(`engine: failed to load ${provider} snapshot for ${projectId}:`, error.message);
    return null;
  }

  return data?.raw_data ?? null;
}

/**
 * Persist score rows to the scores table.
 *
 * @param {string} projectId
 * @param {object} scores  - { security: 85, testing: 72, ... , overall: 79 }
 */
async function saveScores(projectId, scores) {
  const scoredAt = new Date().toISOString();

  const rows = Object.entries(scores).map(([category, value]) => ({
    project_id: projectId,
    category,
    value,
    scored_at: scoredAt,
  }));

  const { error } = await supabase.from('scores').insert(rows);

  if (error) {
    throw new Error(`engine: failed to save scores for ${projectId}: ${error.message}`);
  }
}

/**
 * Run the full scoring engine for a project.
 * Reads the latest GitHub snapshot, scores it across all categories,
 * and writes the results to the scores table.
 *
 * @param {string} projectId - UUID of the project
 * @returns {Promise<object>} - The computed scores
 */
export async function runScoringEngine(projectId) {
  // Load latest snapshots (GitHub is primary; others will be merged in future)
  const githubSnapshot = await getLatestSnapshot(projectId, 'github');

  if (!githubSnapshot) {
    console.warn(`engine: no GitHub snapshot found for project ${projectId} — skipping`);
    return null;
  }

  // Run all rules — each returns 0-100
  const categoryScores = {
    security: scoreSecrity(githubSnapshot),
    testing: scoreTesting(githubSnapshot),
    dependencies: scoreDependencies(githubSnapshot),
    deployment: scoreDeployment(githubSnapshot),
    performance: scorePerformance(githubSnapshot),
  };

  // Weighted overall score
  const overall = Math.round(
    Object.entries(categoryScores).reduce((sum, [category, value]) => {
      return sum + value * WEIGHTS[category];
    }, 0)
  );

  const allScores = { ...categoryScores, overall };

  console.log(`engine: scores for project ${projectId}:`, allScores);

  await saveScores(projectId, allScores);

  return allScores;
}
