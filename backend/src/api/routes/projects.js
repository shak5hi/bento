// src/api/routes/projects.js
// [Lavanya] CRUD endpoints for projects.
// GET /projects         — list all projects for the user
// POST /projects        — create a new project
// DELETE /projects/:id  — delete a project

import { Router } from 'express';
import { supabase } from '../../db/client.js';
import { requireAuth } from '../middleware/auth.js';

export const projectsRouter = Router();

// GET /projects
projectsRouter.get('/', requireAuth, async (req, res) => {
  const { data, error } = await supabase
    .from('projects')
    .select('id, name, created_at, integrations(provider, status)')
    .eq('user_id', req.user.id)
    .order('created_at', { ascending: false });

  if (error) return res.status(500).json({ error: error.message });
  res.json({ projects: data });
});

// POST /projects
projectsRouter.post('/', requireAuth, async (req, res) => {
  const { name } = req.body;
  if (!name?.trim()) return res.status(400).json({ error: 'name is required' });

  const { data, error } = await supabase
    .from('projects')
    .insert({ name: name.trim(), user_id: req.user.id })
    .select()
    .single();

  if (error) return res.status(500).json({ error: error.message });
  res.status(201).json({ project: data });
});

// DELETE /projects/:id
projectsRouter.delete('/:id', requireAuth, async (req, res) => {
  const { id } = req.params;

  // Verify ownership
  const { data: project } = await supabase
    .from('projects')
    .select('id')
    .eq('id', id)
    .eq('user_id', req.user.id)
    .maybeSingle();

  if (!project) return res.status(404).json({ error: 'Project not found' });

  const { error } = await supabase.from('projects').delete().eq('id', id);
  if (error) return res.status(500).json({ error: error.message });

  res.status(204).send();
});
