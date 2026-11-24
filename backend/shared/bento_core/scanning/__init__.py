"""Bento's repository checks, shared by the scanner service and the `bento` CLI.

Everything here only reads files: repository code is never executed. Imports inside this package are
relative and it depends on nothing but httpx, so the CLI can ship it on its own.
"""

import asyncio
from pathlib import Path

import httpx

from .checks import finding, hygiene, list_files, vulnerabilities
from .dockerfile import dockerfiles
from .outdated import outdated
from .secretscan import secrets_in_code

SEVERITIES = ("critical", "high", "medium", "low")

__all__ = ["SEVERITIES", "MemoryCache", "finding", "list_files", "local_checks", "network_checks", "run_checks"]


class MemoryCache:
    """In-process stand-in for the Redis cache (expiry ignored: a CLI run is short)."""

    def __init__(self):
        self._data: dict[str, str] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._data[key] = value


def local_checks(root: Path, files: list[str]) -> list[dict]:
    """Checks that only read the files: hygiene, secrets in code, Dockerfiles."""
    return hygiene(files) + secrets_in_code(root, files) + dockerfiles(root, files)


async def network_checks(root: Path, http: httpx.AsyncClient, cache, facts: dict | None = None) -> list[dict]:
    """Checks that look dependencies up online: OSV advisories and registry versions."""
    vulns, old = await asyncio.gather(vulnerabilities(root, http, cache), outdated(root, http, cache, facts))
    return vulns + old


async def run_checks(
    root: Path, files: list[str], http: httpx.AsyncClient | None, cache=None, facts: dict | None = None
) -> list[dict]:
    """All checks, worst first. Pass http=None to stay offline. `facts` collects raw scan facts."""
    if facts is not None:
        facts["files"] = len(files)
    found = await asyncio.to_thread(local_checks, root, files)  # file reads are blocking
    if http is not None:
        found += await network_checks(root, http, cache or MemoryCache(), facts)
    return sorted(found, key=lambda f: SEVERITIES.index(f["severity"]))
