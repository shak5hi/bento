# bento CLI

Run Bento's repository checks on your own machine or in CI. These are the same checks the hosted scanner
runs (the code lives in `backend/shared/bento_core/scanning` and is bundled into the CLI), so a clean local
scan means a clean Bento dashboard.

`bento scan` only **reads** files. It never installs dependencies or runs your project's code.

## Install

Needs Python 3.10 or newer.

```bash
git clone https://github.com/shak5hi/bento.git
pip install ./bento/cli
bento --version
```

## Usage

```bash
bento scan                 # scan the current folder
bento scan path/to/repo    # scan another folder
bento scan --json          # machine-readable report
bento scan --fail-on critical   # only fail on critical findings
bento scan --offline       # no network: skip OSV and npm/PyPI lookups
```

Example output:

```
bento scan · my-app · 212 files

  CRITICAL GitHub token committed in src/config.ts
           Found on line 12 of src/config.ts (value hidden). Revoke and rotate it now, ...

  MEDIUM   Container runs as root in Dockerfile
           The final stage has no non-root USER, ...

1 critical · 1 medium  →  FAIL (--fail-on high)
```

### What it checks

| Check | Examples |
|---|---|
| Secrets in code | AWS, GitHub, Stripe and Slack tokens, private keys, hard-coded passwords. Reports file and line only: **the value is never printed** |
| Committed `.env` files | `.env`, `.env.production` (`.env.example` is fine) |
| Vulnerable dependencies | npm (`package-lock.json`) and PyPI (`requirements.txt`) packages with known advisories on [OSV](https://osv.dev) |
| Outdated dependencies | direct dependencies a major version or more behind the latest release |
| Dockerfiles | unpinned / `:latest` base image, running as root, `ADD` instead of `COPY`, secrets in `ENV`/`ARG`, no `HEALTHCHECK` |
| Hygiene | no tests, no CI, no README, no lockfile |

Dependency checks read the manifest at the root of the scanned folder; for a monorepo, scan each package
folder (e.g. `bento scan frontend`).

In a git repository, `bento scan` looks at the files git would commit: tracked files plus new files that
aren't ignored. A `.env` listed in `.gitignore` is not reported. Outside git, it scans every file except
`node_modules`, `vendor`, build output and virtual environments.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | no finding at or above the `--fail-on` severity |
| `1` | at least one finding at or above `--fail-on` (default: `high`) |
| `2` | bad arguments, e.g. the folder doesn't exist |

`--fail-on` takes `critical`, `high`, `medium`, `low` or `never` (always exit 0, report only).

### JSON

`bento scan --json` prints:

```json
{
  "tool": "bento",
  "version": "0.1.0",
  "path": "/home/me/my-app",
  "files": 212,
  "offline": false,
  "failOn": "high",
  "failed": true,
  "summary": { "critical": 1, "high": 0, "medium": 1, "low": 0 },
  "findings": [
    { "key": "secret:github-token:src/config.ts", "severity": "critical", "title": "...", "detail": "...", "effortMinutes": 30 }
  ]
}
```

`key` is stable across runs, so you can diff two reports.

## GitHub Actions

Add a step to any workflow:

```yaml
name: Bento
on: [push, pull_request]

jobs:
  bento:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: shak5hi/bento@main
        with:
          fail-on: high      # critical | high | medium | low | never
          # path: services/api
          # offline: "true"
```

The step fails when a finding reaches `fail-on`, which blocks the pull request if the check is required.
It installs into its own virtual environment and needs Python 3.10+ on the runner (GitHub's hosted runners
have it; on self-hosted runners add `actions/setup-python` first).

Prefer to pin a commit (`shak5hi/bento@<sha>`) rather than `@main` so the checks don't change under you.
