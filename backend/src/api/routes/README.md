# src/api/routes/

**Owner: Lavanya**

This folder contains the REST API route handlers for the Bento dashboard.

## Endpoints

| File | Method | Path | Description |
|------|--------|------|-------------|
| `portfolioHealth.js` | `GET` | `/portfolio/health` | All projects + latest scores + AI insight for the authenticated user |
| `projects.js` | `GET` | `/projects` | List all projects |
| `projects.js` | `POST` | `/projects` | Create a new project |
| `projects.js` | `DELETE` | `/projects/:id` | Delete a project |
| `today.js` | `GET` | `/today` | Today's priority list (weakest projects first) |
| `trends.js` | `GET` | `/trends/:projectId?days=30` | Score history for a project (for chart rendering) |

## Auth

All routes use the `requireAuth` middleware from `src/api/middleware/auth.js`.
The frontend sends the Supabase session JWT in the `Authorization: Bearer <token>` header.

## Adding a new route

1. Create a new file in this folder (one resource per file)
2. Export a named `Router` instance
3. Import and mount it in `src/server.js`
4. Add a test in `tests/lavanya/`

## Data contract

Routes only READ from `scores`, `ai_insights`, and `projects` — they never call the scoring engine or AI layer directly.
