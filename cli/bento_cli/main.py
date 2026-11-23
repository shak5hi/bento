"""`bento scan [path]`: Bento's repository checks on a local folder. Reads files only, never runs them.

Exit codes: 0 = nothing at or above the --fail-on threshold, 1 = threshold reached, 2 = usage error.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

from . import __version__

try:  # installed: the wheel bundles the checks as bento_cli.scanning
    from .scanning import SEVERITIES, list_files, run_checks
except ImportError:  # running from a source checkout
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "shared"))
    from bento_core.scanning import SEVERITIES, list_files, run_checks

SKIP_PARTS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", "vendor", ".next"}
FAIL_ON = (*SEVERITIES, "never")


def tracked_files(root: Path) -> list[str] | None:
    """Files git would commit: tracked plus untracked-but-not-ignored. None if this isn't a git repo.

    Uses git only to list paths. fsmonitor is disabled so a repository's config can't make git run
    a program; hooks don't run for ls-files.
    """
    try:
        out = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(root), "ls-files", "-z",
             "--cached", "--others", "--exclude-standard"],
            capture_output=True, timeout=60, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    files = []
    for rel in out.decode("utf-8", errors="replace").split("\0"):
        if not rel or any(part in SKIP_PARTS for part in Path(rel).parts):
            continue
        path = root / rel
        if path.is_file() and not path.is_symlink():
            files.append(rel)
    return files


class Style:
    def __init__(self, enabled: bool):
        self.on = enabled

    def __call__(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.on else text


SEV_STYLE = {"critical": "1;31", "high": "31", "medium": "33", "low": "2"}


def use_color(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("GITHUB_ACTIONS") == "true":
        return True
    return hasattr(stream, "isatty") and stream.isatty()


def counts(findings: list[dict]) -> dict[str, int]:
    return {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}


def failed(findings: list[dict], fail_on: str) -> bool:
    if fail_on == "never":
        return False
    limit = SEVERITIES.index(fail_on)
    return any(SEVERITIES.index(f["severity"]) <= limit for f in findings)


def text_report(root: Path, n_files: int, findings: list[dict], fail_on: str, offline: bool, style: Style) -> str:
    lines = [f"{style('bento scan', '1')} · {root.name or root} · {n_files} files"
             + (" · offline (no dependency lookups)" if offline else ""), ""]
    if not findings:
        lines.append(style("  Nothing to fix. Nice.", "32"))
    for f in findings:
        sev = f["severity"]
        lines.append(f"  {style(sev.upper().ljust(9), SEV_STYLE[sev])}{f['title']}")
        if f.get("detail"):
            lines.append(f"  {' ' * 9}{style(f['detail'], '2')}")
        lines.append("")
    c = counts(findings)
    summary = " · ".join(f"{c[s]} {s}" for s in SEVERITIES if c[s]) or "no findings"
    verdict = (style("FAIL", "1;31") + f" (--fail-on {fail_on})") if failed(findings, fail_on) else style("PASS", "1;32")
    lines.append(f"{summary}  →  {verdict}")
    return "\n".join(lines)


def json_report(root: Path, n_files: int, findings: list[dict], fail_on: str, offline: bool) -> str:
    return json.dumps({
        "tool": "bento",
        "version": __version__,
        "path": str(root),
        "files": n_files,
        "offline": offline,
        "failOn": fail_on,
        "failed": failed(findings, fail_on),
        "summary": counts(findings),
        "findings": [
            {"key": f["key"], "severity": f["severity"], "title": f["title"], "detail": f["detail"],
             "effortMinutes": f["effort_minutes"]}
            for f in findings
        ],
    }, indent=2)


async def scan(root: Path, offline: bool) -> tuple[int, list[dict]]:
    files = tracked_files(root)
    if files is None:
        files = list_files(root)
    if offline:
        return len(files), await run_checks(root, files, None)
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": f"bento-cli/{__version__}"}) as http:
        return len(files), await run_checks(root, files, http)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bento", description="Bento's repository health checks, locally or in CI.")
    parser.add_argument("--version", action="version", version=f"bento {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser(
        "scan", help="scan a folder for secrets, vulnerable or outdated dependencies, Dockerfile and hygiene issues",
        description="Scan a folder. Only reads files: project code is never executed.",
    )
    s.add_argument("path", nargs="?", default=".", help="folder to scan (default: current directory)")
    s.add_argument("--json", action="store_true", help="print a JSON report instead of text")
    s.add_argument("--fail-on", choices=FAIL_ON, default="high",
                   help="exit with code 1 if any finding is this severe or worse (default: high; 'never' always exits 0)")
    s.add_argument("--offline", action="store_true",
                   help="skip the online lookups (OSV advisories, latest versions on npm/PyPI)")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows pipes default to a legacy code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"bento: {args.path} is not a folder", file=sys.stderr)
        return 2
    try:
        n_files, findings = asyncio.run(scan(root, args.offline))
    except KeyboardInterrupt:
        return 130
    if args.json:
        print(json_report(root, n_files, findings, args.fail_on, args.offline))
    else:
        print(text_report(root, n_files, findings, args.fail_on, args.offline, Style(use_color(sys.stdout))))
    return 1 if failed(findings, args.fail_on) else 0


if __name__ == "__main__":
    sys.exit(main())
