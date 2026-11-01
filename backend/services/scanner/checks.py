"""Static repository checks. Nothing from the repository is ever executed."""

import json
import logging
import re
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", "vendor", ".next"}
SOURCE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rb", ".java", ".kt", ".rs", ".php", ".cs", ".swift"}
TEST_PATTERNS = [re.compile(p) for p in (r"(^|/)tests?/", r"(^|/)__tests__/", r"\.(test|spec)\.\w+$", r"(^|/)test_\w+\.py$", r"_test\.(go|py)$")]
ENV_OK = {".env.example", ".env.sample", ".env.template", ".env.dist"}
OSV_URL = "https://api.osv.dev/v1/querybatch"
MAX_FILES = 20_000


def finding(key: str, severity: str, title: str, detail: str, effort: int) -> dict:
    return {"key": key, "severity": severity, "title": title, "detail": detail, "effort_minutes": effort}


def list_files(root: Path) -> list[str]:
    files: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.is_file() and not path.is_symlink():
            files.append(rel.as_posix())
            if len(files) >= MAX_FILES:
                break
    return files


def hygiene(files: list[str]) -> list[dict]:
    out: list[dict] = []
    names = {f.lower() for f in files}
    basenames = {Path(f).name.lower() for f in files}

    leaked = [f for f in files if Path(f).name.startswith(".env") and Path(f).name not in ENV_OK]
    if leaked:
        out.append(finding("secrets-env-file", "critical", "Environment file committed to the repository",
                           f"{', '.join(leaked[:3])} is tracked in git. Rotate any secrets in it, delete it and add it to .gitignore.", 15))

    sources = [f for f in files if Path(f).suffix in SOURCE_EXT]
    tests = [f for f in files if any(p.search(f.lower()) for p in TEST_PATTERNS)]
    if len(sources) >= 5 and not tests:
        out.append(finding("no-tests", "medium", "Production code but no automated tests",
                           f"{len(sources)} source files and no test files. Start with tests around the most-used paths.", 120))

    has_ci = any(f.startswith(".github/workflows/") for f in names) or ".gitlab-ci.yml" in names or "bitbucket-pipelines.yml" in names
    if sources and not has_ci:
        out.append(finding("no-ci", "low", "No CI pipeline",
                           "Nothing builds or tests this project on push. A minimal GitHub Actions workflow takes a few minutes.", 30))

    if not any(b.startswith("readme") for b in basenames):
        out.append(finding("no-readme", "low", "No README", "Add a README explaining what this project is and how to run it.", 20))

    if "package.json" in names and not ({"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"} & names):
        out.append(finding("no-lockfile", "medium", "Dependencies are not locked",
                           "package.json has no lockfile, so every install can pull different versions. Commit a lockfile.", 10))
    return out


def _npm_packages(root: Path) -> dict[str, str]:
    lock = root / "package-lock.json"
    if not lock.is_file():
        return {}
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    pkgs: dict[str, str] = {}
    for path, meta in (data.get("packages") or {}).items():
        # only direct dependencies: "node_modules/<name>" (not nested)
        if path.startswith("node_modules/") and "/node_modules/" not in path and meta.get("version"):
            pkgs[path.removeprefix("node_modules/")] = meta["version"]
    return pkgs


def _pypi_packages(root: Path) -> dict[str, str]:
    req = root / "requirements.txt"
    if not req.is_file():
        return {}
    pkgs: dict[str, str] = {}
    for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*([A-Za-z0-9_.\-]+)", line)
        if m:
            pkgs[m.group(1).lower()] = m.group(2)
    return pkgs


async def vulnerabilities(root: Path, http: httpx.AsyncClient) -> list[dict]:
    """Look up pinned dependencies in the OSV database (osv.dev)."""
    queries = [("npm", n, v) for n, v in _npm_packages(root).items()][:500]
    queries += [("PyPI", n, v) for n, v in _pypi_packages(root).items()][:500]
    if not queries:
        return []
    try:
        resp = await http.post(
            OSV_URL,
            json={"queries": [{"package": {"ecosystem": e, "name": n}, "version": v} for e, n, v in queries]},
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("OSV lookup failed, skipping vulnerability check: %s", exc)
        return []

    out = []
    for (eco, name, version), res in zip(queries, results):
        vulns = res.get("vulns") or []
        if not vulns:
            continue
        ids = [v["id"] for v in vulns]
        severity = "critical" if len(vulns) >= 3 else "high"
        out.append(finding(
            f"vuln:{eco}:{name}", severity,
            f"{name} {version} has {len(ids)} known vulnerabilit{'y' if len(ids) == 1 else 'ies'}",
            f"Advisories: {', '.join(ids[:5])}{'…' if len(ids) > 5 else ''}. Upgrade {name} to a patched release.",
            20,
        ))
    return out
