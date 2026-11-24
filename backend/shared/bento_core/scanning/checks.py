"""Static repository checks. Nothing from the repository is ever executed."""

import asyncio
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


def _npm_dev_only(root: Path) -> set[str]:
    """Packages the lockfile marks as development-only (they never ship to users)."""
    try:
        data = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {
        path.removeprefix("node_modules/")
        for path, meta in (data.get("packages") or {}).items()
        if path.startswith("node_modules/") and "/node_modules/" not in path and meta.get("dev")
    }


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


OSV_VULN_URL = "https://api.osv.dev/v1/vulns/{id}"
OSV_SEVERITY = {"CRITICAL": "critical", "HIGH": "high", "MODERATE": "medium", "MEDIUM": "medium", "LOW": "low"}
SEVERITY_RANK = ("critical", "high", "medium", "low")
ADVISORY_CACHE_S = 7 * 24 * 3600
UNKNOWN_SEVERITY = "high"  # advisory details unavailable: assume serious rather than hide it


async def _advisory_severity(vuln_id: str, http: httpx.AsyncClient, cache, sem: asyncio.Semaphore) -> str:
    key = f"osv:severity:{vuln_id}"
    if cache is not None and (hit := await cache.get(key)):
        return hit.decode() if isinstance(hit, bytes) else hit
    async with sem:
        try:
            res = await http.get(OSV_VULN_URL.format(id=vuln_id), timeout=10)
            res.raise_for_status()
            raw = (res.json().get("database_specific") or {}).get("severity", "")
        except (httpx.HTTPError, ValueError):
            return UNKNOWN_SEVERITY  # not cached: try again next scan
    severity = OSV_SEVERITY.get(str(raw).upper(), "medium")  # advisory without a rating: moderate
    if cache is not None:
        await cache.set(key, severity, ex=ADVISORY_CACHE_S)
    return severity


async def vulnerabilities(root: Path, http: httpx.AsyncClient, cache=None) -> list[dict]:
    """Pinned dependencies with known advisories in OSV (osv.dev), graded by the advisories' own severity.

    A dependency only used during development counts one level lower: it never ships to users.
    """
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

    affected = [(q, [v["id"] for v in (res.get("vulns") or [])]) for q, res in zip(queries, results)]
    affected = [(q, ids) for q, ids in affected if ids]
    unique = list(dict.fromkeys(i for _, ids in affected for i in ids))[:400]
    sem = asyncio.Semaphore(8)
    graded = dict(zip(unique, await asyncio.gather(*(_advisory_severity(i, http, cache, sem) for i in unique))))
    dev_only = _npm_dev_only(root)

    out = []
    for (eco, name, version), ids in affected:
        worst = min((graded.get(i, UNKNOWN_SEVERITY) for i in ids), key=SEVERITY_RANK.index)
        dev = eco == "npm" and name in dev_only
        severity = SEVERITY_RANK[min(SEVERITY_RANK.index(worst) + (1 if dev else 0), len(SEVERITY_RANK) - 1)]
        out.append({**finding(
            f"vuln:{eco}:{name}", severity,
            f"{name} {version} has {len(ids)} known vulnerabilit{'y' if len(ids) == 1 else 'ies'}",
            f"Worst advisory: {worst}{' (development-only dependency, so it never reaches your users)' if dev else ''}. "
            f"Advisories: {', '.join(ids[:5])}{'…' if len(ids) > 5 else ''}. Upgrade {name} to a patched release.",
            20,
        ), "meta": {"advisories": len(ids), "worst": worst, "dev": dev}})
    return out
