<div align="center">

# 🍱 Bento

**An engineering health platform. Connect your GitHub repositories and live sites once, and Bento tells you what across your projects actually needs attention today.**

[![CI](https://github.com/shak5hi/bento/actions/workflows/tests.yml/badge.svg)](https://github.com/shak5hi/bento/actions/workflows/tests.yml)
[![React](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-3178c6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Three.js](https://img.shields.io/badge/Three.js-R3F-000000?style=flat-square&logo=threedotjs)](https://threejs.org)
[![Python](https://img.shields.io/badge/Python-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-Streams-dc382d?style=flat-square&logo=redis&logoColor=white)](https://redis.io/docs/latest/develop/data-types/streams/)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-Postgres-fdb515?style=flat-square&logo=postgresql&logoColor=white)](https://www.timescale.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose/)

### **[Try it live → bento.104-43-56-1.sslip.io](https://bento.104-43-56-1.sslip.io)**

[How Bento works, in plain words](docs/how-bento-works.md) · [Animated system design](docs/system-design.html) · [Deploy your own](deploy/README.md)

</div>

---

## The problem

Developers who look after several projects end up checking each repository and each live site by hand,
then working out for themselves what matters. Bento pulls all of that into one **0–100 health score per
project**, and its assistant, **Pickle**, turns the raw signals into a short, plain-English priority list:
three things to do today, not fifty alerts.

## How it works

> New to all this? Read **[Bento, explained simply](docs/how-bento-works.md)**: every feature in everyday
> words, no programming knowledge needed. To watch requests travel through the system, download
> [`docs/system-design.html`](docs/system-design.html) and open it in your browser.

```
CODE PIPELINE
  GitHub push ─┐
  dashboard  ──┴─► api-gateway ──► scan.jobs ──► scanner ──► findings ──► advisor (Pickle)
                   FastAPI · JWT                 sandboxed               rules + local AI
                   GitHub App                    clone, OSV

PROBE PIPELINE
  scheduler ──► probe.jobs ──► probers ×N ──► probe.results ──► analyzer ──► incidents ──► notifier
  Redis ZSET                   HTTP checks                      EWMA          health score   in-app / email / Slack
```

1. **Connect.** Sign in with GitHub and pick repositories (private ones too). A repo's *Website* is monitored automatically.
2. **Scan.** Every push is scanned in a sandbox: secrets in code (AWS, GitHub, Stripe, Slack, private keys) and
   leaked `.env` files, known-vulnerable ([OSV](https://osv.dev)) and outdated dependencies, Dockerfile practices,
   missing tests, CI, README or lockfile. Repository code is never executed and secret values are never stored.
3. **Probe.** Live sites are checked every minute. The analyzer learns each endpoint's normal latency and
   error rate (EWMA) and opens an incident after 3 abnormal checks in a row.
4. **Grade.** Four report cards (**Security**, **Website**, **Code basics** and **Upkeep**) roll up into one
   0–100 score and an A–F grade. A leaked secret caps the grade, anything not measured says so, and every
   project shows the one fix that would raise its score most.
5. **Tell you.** Incident emails, a welcome report as soon as a new account's projects are scanned, and a
   Monday summary. Sent free through a Gmail account (or Resend), always to the person's own address, with
   one-click unsubscribe.
6. **Explain.** Pickle's rules rank incidents and findings and pick the top three; a small open AI model
   running on your own machine (Ollama) explains them in plain words, with step-by-step fixes. No hosted AI
   service, nothing leaves the machine, and the rule-based text is used whenever the model isn't available.

Eight Python services and a local AI model talk over **Redis Streams** with consumer groups, so work survives crashes (unacked jobs
are reclaimed after 30 s) and probers scale horizontally. Details: [`backend/README.md`](backend/README.md).

## Frontend

The landing page is a **scroll-driven 3D bento box**. The lid lifts, the trays come
apart and the food items settle into place as you scroll.

- Models made in **Blender**, exported to glTF and compressed with `gltf-pipeline`
- Rendered with **React Three Fiber + drei**; a custom `AnimationController` maps
  scroll progress to camera position and per-model transforms
- **GSAP** timelines and **Lenis** smooth scrolling, with shared scroll state in **Zustand**
- Tailwind CSS v4, React Router 7, and login and dashboard pages

## Command line and CI

The same checks run locally and in other repositories' CI with the `bento` CLI. It only reads files and
never runs your code:

```bash
pip install ./cli
bento scan .                    # exits 1 on critical/high findings
bento scan . --json --fail-on critical
```

```yaml
- uses: shak5hi/bento@main      # GitHub Action
  with: { fail-on: high }
```

Details: [`cli/README.md`](cli/README.md).

## Repository layout

```
bento/
├── frontend/              React 19 + Vite + TypeScript: 3D landing, login, dashboard
├── cli/                   `bento scan`: the scanner's checks on the command line (pip install ./cli)
├── action.yml             GitHub Action that runs `bento scan`
├── docs/                  plain-language guide + animated system design (system-design.html)
├── deploy/                server setup and the deployment walkthrough
├── backend/
│   ├── docker-compose.yml the whole stack (14 containers)
│   ├── services/
│   │   ├── api/           FastAPI gateway: auth, GitHub App, projects, dashboard, webhooks
│   │   ├── scheduler/     probe schedule (Redis ZSET, jittered)
│   │   ├── prober/        HTTP checks, SSRF-safe
│   │   ├── analyzer/      EWMA anomaly detection, incidents, health scores
│   │   ├── notifier/      alerts, welcome report and weekly digest emails
│   │   ├── scanner/       sandboxed repository scans
│   │   ├── advisor/       Pickle: rules decide, a local open model explains
│   │   └── fixer/         auto-fix pull requests (never touches the default branch)
│   └── shared/bento_core/ config, DB pools, streams, scoring, GitHub client
└── screenshots/
```

## Getting started

```bash
git clone https://github.com/shak5hi/bento.git
cd bento/backend
docker compose up --build        # app on http://localhost:8080
```

Everything has a development default, so no `.env` is needed to try it. To put Bento online (one server,
automatic HTTPS, daily backups), follow [`deploy/README.md`](deploy/README.md). To enable **Sign in with GitHub** and
private repositories, create a GitHub App: see [Connect GitHub](backend/README.md#connect-github-github-app).

## Roadmap

- [x] Probe pipeline: uptime, latency, anomaly detection, incidents
- [x] Code pipeline: sandboxed scans, vulnerable dependencies, hygiene checks
- [x] Engineering Health Score and Pickle's daily brief
- [x] Connect GitHub: sign in, import repositories (private too), scan on push
- [x] Pull request checks
- [x] Auto-fix pull requests (always waiting for human approval)
- [x] Public status pages and README badges
- [x] Email alerts, a welcome report and a weekly digest (free through Gmail)
- [x] Deeper scanning: secrets in code, outdated dependencies, Dockerfiles
- [x] `bento` CLI and GitHub Action
- [x] Test suite and CI
- [x] Hosted deployment: [bento.104-43-56-1.sslip.io](https://bento.104-43-56-1.sslip.io) (Azure, Caddy HTTPS, daily backups)

## License

Proprietary. All rights reserved.
