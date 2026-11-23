<div align="center">

# 🍱 Bento

**An engineering health platform. Connect your GitHub repositories and live sites once, and Bento tells you what across your projects actually needs attention today.**

[![React](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-3178c6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Three.js](https://img.shields.io/badge/Three.js-R3F-000000?style=flat-square&logo=threedotjs)](https://threejs.org)
[![Python](https://img.shields.io/badge/Python-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-Streams-dc382d?style=flat-square&logo=redis&logoColor=white)](https://redis.io/docs/latest/develop/data-types/streams/)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-Postgres-fdb515?style=flat-square&logo=postgresql&logoColor=white)](https://www.timescale.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose/)

</div>

---

## The problem

Developers who look after several projects end up checking each repository and each live site by hand,
then working out for themselves what matters. Bento pulls all of that into one **0–100 health score per
project**, and its assistant, **Pickle**, turns the raw signals into a short, plain-English priority list:
three things to do today, not fifty alerts.

## How it works

```
CODE PIPELINE
  GitHub push ─┐
  dashboard  ──┴─► api-gateway ──► scan.jobs ──► scanner ──► findings ──► advisor (Pickle)
                   FastAPI · JWT                 sandboxed               rule-based, cached
                   GitHub App                    clone, OSV

PROBE PIPELINE
  scheduler ──► probe.jobs ──► probers ×N ──► probe.results ──► analyzer ──► incidents ──► notifier
  Redis ZSET                   HTTP checks                      EWMA          health score   in-app / Slack
```

1. **Connect.** Sign in with GitHub and pick repositories (private ones too). A repo's *Website* is monitored automatically.
2. **Scan.** Every push is scanned in a sandbox: leaked `.env` files, known-vulnerable dependencies
   ([OSV](https://osv.dev)), missing tests, CI, README or lockfile. Repository code is never executed.
3. **Probe.** Live sites are checked every minute. The analyzer learns each endpoint's normal latency and
   error rate (EWMA) and opens an incident after 3 abnormal checks in a row.
4. **Score.** `Uptime 40 + Latency 20 + Errors 20 + Code 20`, recomputed every minute.
5. **Explain.** Pickle ranks incidents and findings by severity and writes a brief plus at most three
   recommendations. It is rule-based: no external AI service.

Seven Python services talk over **Redis Streams** with consumer groups, so work survives crashes (unacked jobs
are reclaimed after 30 s) and probers scale horizontally. Details: [`backend/README.md`](backend/README.md).

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
├── frontend/              React 19 + Vite + TypeScript: 3D landing, login, dashboard
├── backend/
│   ├── docker-compose.yml the whole stack (12 containers)
│   ├── services/
│   │   ├── api/           FastAPI gateway: auth, GitHub App, projects, dashboard, webhooks
│   │   ├── scheduler/     probe schedule (Redis ZSET, jittered)
│   │   ├── prober/        HTTP checks, SSRF-safe
│   │   ├── analyzer/      EWMA anomaly detection, incidents, health scores
│   │   ├── notifier/      alerts with dedup and cooldown
│   │   ├── scanner/       sandboxed repository scans
│   │   └── advisor/       Pickle
│   └── shared/bento_core/ config, DB pools, streams, scoring, GitHub client
└── screenshots/
```

## Getting started

```bash
git clone https://github.com/shak5hi/bento.git
cd bento/backend
docker compose up --build        # app on http://localhost:8080
```

Everything has a development default, so no `.env` is needed to try it. To enable **Sign in with GitHub** and
private repositories, create a GitHub App: see [Connect GitHub](backend/README.md#connect-github-github-app).

## Roadmap

- [x] Probe pipeline: uptime, latency, anomaly detection, incidents
- [x] Code pipeline: sandboxed scans, vulnerable dependencies, hygiene checks
- [x] Engineering Health Score and Pickle's daily brief
- [x] Connect GitHub: sign in, import repositories (private too), scan on push
- [ ] Pull request checks
- [ ] Auto-fix pull requests (always waiting for human approval)
- [ ] Public status pages and README badges
- [ ] Email alerts and a weekly digest
- [ ] Deeper scanning: secrets in code, outdated dependencies, Dockerfiles
- [ ] Test suite and CI · `bento` CLI · hosted deployment

## License

Proprietary. All rights reserved.
