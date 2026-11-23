// src/server.js
// Express app entry point. Mounts all routes, middleware, and starts the scheduler.

import express from 'express';
import cors from 'cors';
import { config } from './config/index.js';

// Route routers
import { portfolioHealthRouter } from './api/routes/portfolioHealth.js';
import { projectsRouter } from './api/routes/projects.js';
import { todayRouter } from './api/routes/today.js';
import { trendsRouter } from './api/routes/trends.js';

// Integration routes
import { redirectToGitHub, handleCallback } from './integrations/github/auth.js';

// Webhook router
import { webhooksRouter } from './jobs/webhooks.js';

// Scheduler
import { startScheduler } from './jobs/scheduler.js';

const app = express();

// ─── Global Middleware ─────────────────────────────────────────────────────
app.use(cors({ origin: config.frontendUrl, credentials: true }));

// Capture raw body for webhook signature verification BEFORE json parser
app.use((req, res, next) => {
  let raw = '';
  req.on('data', (chunk) => (raw += chunk));
  req.on('end', () => {
    req.rawBody = raw;
    next();
  });
});

app.use(express.json());

// ─── Health Check ──────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  res.json({ status: 'ok', service: 'bento-api', env: config.nodeEnv });
});

// ─── Integration OAuth Routes ──────────────────────────────────────────────
app.get('/integrations/github/connect', redirectToGitHub);
app.get('/integrations/github/callback', handleCallback);

// ─── Webhook Routes ────────────────────────────────────────────────────────
app.use('/webhooks', webhooksRouter);

// ─── API Routes ────────────────────────────────────────────────────────────
app.use('/portfolio/health', portfolioHealthRouter);
app.use('/projects', projectsRouter);
app.use('/today', todayRouter);
app.use('/trends', trendsRouter);

// ─── 404 Handler ──────────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).json({ error: `Route ${req.method} ${req.path} not found` });
});

// ─── Global Error Handler ─────────────────────────────────────────────────
app.use((err, req, res, next) => {
  console.error('[server] Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// ─── Start ─────────────────────────────────────────────────────────────────
app.listen(config.port, () => {
  console.log(`🍱 Bento API running on http://localhost:${config.port} (${config.nodeEnv})`);
  startScheduler();
});

export default app;
