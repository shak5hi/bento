// src/api/middleware/auth.js
// [Lavanya] Supabase Auth middleware.
// Verifies the Bearer JWT from the Authorization header.
// Attaches req.user to the request on success.

import { supabase } from '../../db/client.js';

/**
 * Express middleware that validates a Supabase Auth JWT.
 * Usage: router.get('/protected', requireAuth, handler)
 */
export async function requireAuth(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing or invalid Authorization header' });
  }

  const token = authHeader.slice(7);

  const { data, error } = await supabase.auth.getUser(token);

  if (error || !data?.user) {
    return res.status(401).json({ error: 'Invalid or expired token' });
  }

  req.user = data.user;
  next();
}
