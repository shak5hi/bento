<div align="center">

# 🍱 Bento

**An engineering health platform. Connect GitHub, Vercel and Sentry once, and Bento tells you what across your projects actually needs attention today.**

[![React](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-3178c6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Three.js](https://img.shields.io/badge/Three.js-R3F-000000?style=flat-square&logo=threedotjs)](https://threejs.org)
[![GSAP](https://img.shields.io/badge/GSAP-animation-88ce02?style=flat-square&logo=greensock&logoColor=black)](https://gsap.com)
[![Node.js](https://img.shields.io/badge/Node.js-Express-339933?style=flat-square&logo=nodedotjs&logoColor=white)](https://expressjs.com)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres-3ecf8e?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com)
[![Claude](https://img.shields.io/badge/AI-Claude_Haiku-d97757?style=flat-square&logo=anthropic&logoColor=white)](https://www.anthropic.com)

</div>

---

## The problem

Developers who look after several projects end up switching between GitHub, Vercel,
Sentry and dependency alerts, then working out for themselves what matters. Bento
pulls all of that into one **0–100 health score per project**. Its AI assistant,
**Pickle**, turns the raw signals into a short, plain-English priority list.

## How it works

```
 GitHub ─┐                ┌────────────┐     ┌───────────────┐     ┌─────────────┐
 Vercel ─┼─► Ingest jobs ─►│ snapshots  │ ──► │ Scoring engine│ ──► │   scores    │
 Sentry ─┘   (node-cron,   └────────────┘     │ 5 rule sets   │     └──────┬──────┘
             webhooks)                         └───────────────┘            │
                                                                            ▼
           React dashboard ◄── REST API ◄── Pickle (Claude Haiku, cached) ◄─┘
                                       └──► Weekly email report (Resend)
```

1. **Connect.** Link your tools once (GitHub OAuth; Vercel and Sentry API keys).
2. **Ingest.** Scheduled jobs and GitHub webhooks save raw data as timestamped snapshots.
3. **Score.** A rules engine scores **security, testing, dependencies, deployment and performance**.
4. **Explain.** Pickle writes the insights and suggested fixes. It runs on a schedule
   and its results are cached, never generated per request, so AI costs stay near $0.
5. **Report.** Every Monday an email summarises what changed and what's at risk.

## Frontend

The landing page is a **scroll-driven 3D bento box**. The lid lifts, the trays come
apart and the food items settle into place as you scroll.

- Models made in **Blender**, exported to glTF and compressed with `gltf-pipeline`
- Rendered with **React Three Fiber + drei**; a custom `AnimationController` maps
  scroll progress to camera position and per-model transforms
- **GSAP** timelines and **Lenis** smooth scrolling, with shared scroll state in **Zustand**
- Tailwind CSS v4, React Router 7, and login and dashboard pages

## Repository layout

```
bento/
├── frontend/          React 19 + Vite + TypeScript, 3D landing, login, dashboard
│   ├── src/experience/   R3F models, animation controller, scroll state
│   └── public/models/    Optimised .glb assets
└── backend/           Express API, integrations, scoring, AI, reports
    ├── src/integrations/ GitHub · Vercel · Sentry → snapshots
    ├── src/scoring/      Engine + per-category rules
    ├── src/ai/           Pickle prompt + insight generation
    └── src/jobs/         Cron scheduler + webhooks
```

See [`backend/README.md`](backend/README.md) for the database schema and design rules.

## Getting started

```bash
git clone https://github.com/shak5hi/bento.git
cd bento

# Frontend
cd frontend && npm install && npm run dev

# Backend (new terminal)
cd backend && cp .env.example .env   # Supabase, GitHub OAuth, Anthropic, Resend keys
npm install && npm run dev
```

## Roadmap

- [x] GitHub, Vercel and Sentry integrations
- [x] Rules-based health scoring
- [x] Pickle AI insights and weekly email reports
- [x] 3D landing experience
- [ ] More integrations (Cloudflare, Docker, GitHub Actions)
- [ ] Pickle opens pull requests for routine fixes (always waiting for human approval)

## Team

| | Area |
|---|---|
| **[Shakshi Sharma](https://github.com/shak5hi)** | Frontend: the 3D landing experience, Blender models, animation system, login and dashboard; integrations and ingestion (per [`OWNERSHIP.md`](backend/OWNERSHIP.md)) |
| **[Lavanya Verma](https://github.com/lavanyaaax)** | Backend: scoring engine, AI layer, API, reports |

## License

Proprietary. All rights reserved.
