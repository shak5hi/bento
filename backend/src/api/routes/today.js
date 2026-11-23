// src/api/routes/today.js
// [Lavanya] GET /today
// Returns today's top priorities for the authenticated user across all their projects.
// Priorities are derived from lowest-scoring categories + cached AI insights.

import { Router } from 'express';
import { supabase } from '../../db/client.js';
import { requireAuth } from '../middleware/auth.js';

export const todayRouter = Router();

// GET /today
todayRouter.get('/', requireAuth, async (req, res) => {
  const userId = req.user.id;

  // Load user's projects
  const { data: projects, error } = await supabase
    .from('projects')
    .select('id, name')
    .eq('user_id', userId);

  if (error) return res.status(500).json({ error: error.message });
  if (!projects?.length) return res.json({ priorities: [] });

  const projectIds = projects.map((p) => p.id);
  const projectMap = Object.fromEntries(projects.map((p) => [p.id, p.name]));

  // Load latest scores
  const { data: scores } = await supabase
    .from('scores')
    .select('project_id, category, value, scored_at')
    .in('project_id', projectIds)
    .order('scored_at', { ascending: false });

  // Load latest insights
  const { data: insights } = await supabase
    .from('ai_insights')
    .select('project_id, insight')
    .in('project_id', projectIds)
    .order('generated_at', { ascending: false });

  // Find the most recent overall score per project
  const latestOverallByProject = {};
  const lowestCategoryByProject = {};

  for (const score of scores ?? []) {
    if (score.category === 'overall' && !latestOverallByProject[score.project_id]) {
      latestOverallByProject[score.project_id] = score.value;
    }
    if (score.category !== 'overall') {
      if (
        !lowestCategoryByProject[score.project_id] ||
        score.value < lowestCategoryByProject[score.project_id].value
      ) {
        lowestCategoryByProject[score.project_id] = { category: score.category, value: score.value };
      }
    }
  }

  const latestInsightByProject = {};
  for (const insight of insights ?? []) {
    if (!latestInsightByProject[insight.project_id]) {
      latestInsightByProject[insight.project_id] = insight.insight;
    }
  }

  // Build priority list — sort by worst overall score first
  const priorities = projectIds
    .filter((id) => latestOverallByProject[id] !== undefined)
    .sort((a, b) => latestOverallByProject[a] - latestOverallByProject[b])
    .map((id) => ({
      projectId: id,
      projectName: projectMap[id],
      overallScore: latestOverallByProject[id],
      lowestCategory: lowestCategoryByProject[id] ?? null,
      insight: latestInsightByProject[id] ?? null,
    }));

  res.json({ priorities });
});
