// src/api/routes/portfolioHealth.js
// [Lavanya] GET /portfolio/health
// Returns the latest scores for all projects owned by the authenticated user.

import { Router } from 'express';
import { supabase } from '../../db/client.js';
import { requireAuth } from '../middleware/auth.js';

export const portfolioHealthRouter = Router();

// GET /portfolio/health
portfolioHealthRouter.get('/', requireAuth, async (req, res) => {
  const userId = req.user.id;

  // Load all projects for the user
  const { data: projects, error: projectsError } = await supabase
    .from('projects')
    .select('id, name, created_at')
    .eq('user_id', userId)
    .order('created_at', { ascending: true });

  if (projectsError) {
    return res.status(500).json({ error: 'Failed to load projects' });
  }

  if (!projects?.length) {
    return res.json({ projects: [] });
  }

  const projectIds = projects.map((p) => p.id);

  // Load the latest score per category per project
  const { data: scores, error: scoresError } = await supabase
    .from('scores')
    .select('project_id, category, value, scored_at')
    .in('project_id', projectIds)
    .order('scored_at', { ascending: false });

  if (scoresError) {
    return res.status(500).json({ error: 'Failed to load scores' });
  }

  // Load latest AI insight per project
  const { data: insights } = await supabase
    .from('ai_insights')
    .select('project_id, insight, generated_at')
    .in('project_id', projectIds)
    .order('generated_at', { ascending: false });

  // Group: latest score per (project, category)
  const latestScoreByProject = {};
  for (const score of scores ?? []) {
    if (!latestScoreByProject[score.project_id]) {
      latestScoreByProject[score.project_id] = {};
    }
    const existing = latestScoreByProject[score.project_id][score.category];
    if (!existing) {
      latestScoreByProject[score.project_id][score.category] = score.value;
    }
  }

  const latestInsightByProject = {};
  for (const insight of insights ?? []) {
    if (!latestInsightByProject[insight.project_id]) {
      latestInsightByProject[insight.project_id] = insight.insight;
    }
  }

  const result = projects.map((project) => ({
    id: project.id,
    name: project.name,
    scores: latestScoreByProject[project.id] ?? null,
    insight: latestInsightByProject[project.id] ?? null,
  }));

  res.json({ projects: result });
});
