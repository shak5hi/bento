// src/api/routes/trends.js
// [Lavanya] GET /trends/:projectId
// Returns the score history for a project so the dashboard can render a trend chart.
// Query params: ?days=30 (default 30, max 90)

import { Router } from 'express';
import { supabase } from '../../db/client.js';
import { requireAuth } from '../middleware/auth.js';

export const trendsRouter = Router();

// GET /trends/:projectId
trendsRouter.get('/:projectId', requireAuth, async (req, res) => {
  const { projectId } = req.params;
  const days = Math.min(parseInt(req.query.days) || 30, 90);

  // Verify ownership
  const { data: project } = await supabase
    .from('projects')
    .select('id, name')
    .eq('id', projectId)
    .eq('user_id', req.user.id)
    .maybeSingle();

  if (!project) return res.status(404).json({ error: 'Project not found' });

  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

  const { data: scores, error } = await supabase
    .from('scores')
    .select('category, value, scored_at')
    .eq('project_id', projectId)
    .gte('scored_at', since)
    .order('scored_at', { ascending: true });

  if (error) return res.status(500).json({ error: error.message });

  // Group by category for easy charting
  const byCategory = {};
  for (const score of scores ?? []) {
    if (!byCategory[score.category]) byCategory[score.category] = [];
    byCategory[score.category].push({
      value: score.value,
      date: score.scored_at,
    });
  }

  res.json({
    projectId,
    projectName: project.name,
    days,
    trends: byCategory,
  });
});
