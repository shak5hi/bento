"""Outdated dependencies: direct npm and PyPI dependencies a major version or more behind the latest release.

Latest versions come from the public registries, with short timeouts, bounded concurrency and a Redis
cache (6 h), so rescanning many projects doesn't hammer npm or PyPI. One finding per ecosystem
(`outdated:npm`, `outdated:PyPI`) keeps the score from being swamped by a long tail of minor upgrades;
the detail lists the packages furthest behind.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote

import httpx

from checks import _pypi_packages, finding

log = logging.getLogger(__name__)

CACHE_TTL_S = 6 * 3600
MISS_TTL_S = 3600  # unknown/private packages: don't retry on every scan
LOOKUP_TIMEOUT_S = 8
CONCURRENCY = 8
MAX_PACKAGES = 150
NPM_LATEST = "https://registry.npmjs.org/{name}/latest"
PYPI_JSON = "https://pypi.org/pypi/{name}/json"

_VERSION = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def major(version: str | None) -> int | None:
    if not version:
        return None
    m = _VERSION.search(version)
    return int(m.group(1)) if m else None


def _is_prerelease(version: str) -> bool:
    return bool(re.search(r"(?i)(a|b|rc|alpha|beta|dev|pre|canary|next)\.?\d*$|-", version))


def npm_direct(root: Path) -> dict[str, str]:
    """Direct dependencies from package.json, with the installed version from the lockfile when present."""
    try:
        manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    wanted: dict[str, str] = {}
    for section in ("dependencies", "devDependencies"):
        deps = manifest.get(section)
        if isinstance(deps, dict):
            wanted.update({n: v for n, v in deps.items() if isinstance(v, str)})
    locked: dict[str, str] = {}
    try:
        lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
        for path, meta in (lock.get("packages") or {}).items():
            if path.startswith("node_modules/") and "/node_modules/" not in path and meta.get("version"):
                locked[path.removeprefix("node_modules/")] = meta["version"]
    except (OSError, ValueError):
        pass
    out = {}
    for name, spec in wanted.items():
        # skip git/file/workspace/alias specs: there's no registry version to compare
        if re.match(r"^(file:|link:|workspace:|git|github:|http|npm:|\*|latest$)", spec.strip()):
            continue
        version = locked.get(name) or re.sub(r"^[\^~>=<v\s]+", "", spec.split("||")[0].strip())
        if major(version) is not None:
            out[name] = version
    return out


async def _latest(eco: str, name: str, http: httpx.AsyncClient, r, sem: asyncio.Semaphore) -> str | None:
    key = f"registry:{eco}:{name.lower()}"
    cached = await r.get(key)
    if cached is not None:
        cached = cached.decode() if isinstance(cached, bytes) else cached
        return cached or None
    url = NPM_LATEST.format(name=quote(name, safe="@")) if eco == "npm" else PYPI_JSON.format(name=quote(name))
    latest = None
    async with sem:
        try:
            resp = await http.get(url, timeout=LOOKUP_TIMEOUT_S, headers={"Accept": "application/json"})
            if resp.status_code == 200:
                data = resp.json()
                latest = data.get("version") if eco == "npm" else (data.get("info") or {}).get("version")
            elif resp.status_code != 404:
                return None  # registry trouble: don't cache, try again next scan
        except (httpx.HTTPError, ValueError) as exc:
            log.info("registry lookup failed for %s %s: %s", eco, name, type(exc).__name__)
            return None
    await r.set(key, latest or "", ex=CACHE_TTL_S if latest else MISS_TTL_S)
    return latest


async def outdated(root: Path, http: httpx.AsyncClient, r) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)
    out = []
    for eco, pkgs in (("npm", npm_direct(root)), ("PyPI", _pypi_packages(root))):
        items = list(pkgs.items())[:MAX_PACKAGES]
        if not items:
            continue
        latest = await asyncio.gather(*(_latest(eco, n, http, r, sem) for n, _ in items))
        behind = []
        for (name, current), new in zip(items, latest):
            if not new or _is_prerelease(new):
                continue
            cur_major, new_major = major(current), major(new)
            if cur_major is None or new_major is None or new_major <= cur_major:
                continue
            behind.append((new_major - cur_major, name, current, new))
        if not behind:
            continue
        behind.sort(key=lambda b: (-b[0], b[1]))
        worst = behind[0][0]
        listed = ", ".join(f"{n} {c} → {l}" for _, n, c, l in behind[:8]) + ("…" if len(behind) > 8 else "")
        count = len(behind)
        out.append(finding(
            f"outdated:{eco}", "medium" if worst >= 2 else "low",
            f"{count} {eco} package{'s are' if count > 1 else ' is'} a major version or more behind",
            f"{listed}. Major upgrades can include breaking changes: read the changelogs and upgrade one at a time.",
            min(240, 30 * count),
        ))
    return out
