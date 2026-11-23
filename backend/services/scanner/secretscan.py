"""Secrets committed in code: well-known token formats and high-entropy values assigned to secret-ish names.

The secret value itself is never stored, logged or shown: a finding only says which kind of secret
was found, in which file and on which lines. One finding per (rule, file), so the key stays stable when
lines move and the existing dedupe/resolve logic works.
"""

import math
import re
from collections import Counter
from pathlib import Path

from checks import ENV_OK, finding

MAX_FILE_BYTES = 512 * 1024
MAX_LINE_CHARS = 2_000  # longer lines are minified bundles or data blobs
MAX_FILES_SCANNED = 5_000
MAX_FINDINGS = 25

SKIP_DIRS = {"third_party", "third-party", "bower_components", ".yarn", "site-packages", "Pods", "testdata"}
LOCKFILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock",
    "pipfile.lock", "cargo.lock", "composer.lock", "go.sum", "gemfile.lock", "uv.lock",
}
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff", ".svgz", ".pdf", ".zip", ".gz", ".tgz",
    ".bz2", ".xz", ".7z", ".rar", ".jar", ".war", ".class", ".so", ".dll", ".dylib", ".exe", ".bin", ".o", ".a",
    ".pyc", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4", ".mov", ".avi", ".webm", ".wav", ".ogg",
    ".glb", ".gltf", ".fbx", ".blend", ".psd", ".sqlite", ".db", ".wasm", ".map",
}

# (rule id, label, severity, pattern)
TOKEN_RULES = [
    ("aws-access-key", "AWS access key ID", "critical", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", "GitHub token", "critical", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{60,255})\b")),
    ("stripe-live-key", "Stripe live secret key", "critical", re.compile(r"\b[sr]k_live_[A-Za-z0-9]{20,}\b")),
    ("stripe-test-key", "Stripe test secret key", "medium", re.compile(r"\b[sr]k_test_[A-Za-z0-9]{20,}\b")),
    ("slack-token", "Slack token", "critical", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("slack-webhook", "Slack webhook URL", "high", re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]{16,}")),
    ("private-key", "Private key", "critical", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
]

# name = "value" / name: 'value' where the name looks like a credential
ASSIGNMENT = re.compile(
    r"""(?ix)
    (?P<name>[a-z0-9_.\-]*(?:secret|token|passwd|password|pwd|api[_\-]?key|access[_\-]?key|private[_\-]?key|auth[_\-]?key|client[_\-]?secret)[a-z0-9_\-]*)
    ["']?\s*(?::=|=>|=|:)\s*
    (?P<q>["'`])(?P<value>[^"'`\s]{16,200})(?P=q)
    """
)
PLACEHOLDER = re.compile(
    r"(?i)(x{4,}|\*{3,}|your[_\-]|example|sample|dummy|placeholder|changeme|change[_\-]me|redacted|fake|"
    r"test|todo|replace|insert|<|>|\$\{|\{\{|%\(|process\.env|os\.environ|getenv)"
)
GENERIC_ENTROPY = 3.5  # bits per character
# a real key has base64 body text right after the header; docs only show a stub like "MIIE..."
KEY_BODY = re.compile(r"[A-Za-z0-9+/=]{40,}")


def entropy(s: str) -> float:
    counts = Counter(s)
    return -sum(c / len(s) * math.log2(c / len(s)) for c in counts.values())


def _skip(rel: str) -> bool:
    p = Path(rel)
    name = p.name.lower()
    if any(part in SKIP_DIRS for part in p.parts):
        return True
    if name in LOCKFILES or p.suffix.lower() in BINARY_EXT or name.endswith((".min.js", ".min.css")):
        return True
    # committed .env files already get their own finding (secrets-env-file)
    return name.startswith(".env") and name not in ENV_OK


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None  # binary
    return data.decode("utf-8", errors="ignore")


def _line_hits(line: str) -> list[tuple[str, str, str]]:
    """(rule, label, severity) for every secret on one line. Never returns the value."""
    hits = [(rule, label, sev) for rule, label, sev, rx in TOKEN_RULES if rx.search(line)]
    if hits:
        return hits
    for m in ASSIGNMENT.finditer(line):
        value = m.group("value")
        if PLACEHOLDER.search(value) or entropy(value) < GENERIC_ENTROPY:
            continue
        if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
            continue  # words or plain numbers, not a credential
        return [("generic-secret", "Hard-coded credential", "high")]
    return []


def secrets_in_code(root: Path, files: list[str]) -> list[dict]:
    by_key: dict[tuple[str, str], dict] = {}
    scanned = 0
    for rel in files:
        if _skip(rel):
            continue
        scanned += 1
        if scanned > MAX_FILES_SCANNED:
            break
        text = _read_text(root / rel)
        if text is None:
            continue
        lines = text.splitlines()
        for lineno, line in enumerate(lines, 1):
            if len(line) > MAX_LINE_CHARS:
                continue
            for rule, label, sev in _line_hits(line):
                if rule == "private-key":
                    after = " ".join([line.split("-----", 2)[-1], *lines[lineno:lineno + 2]])
                    if not KEY_BODY.search(after):
                        continue  # just the header, e.g. in documentation
                entry = by_key.setdefault((rule, rel), {"label": label, "severity": sev, "lines": []})
                entry["lines"].append(lineno)

    out = []
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for (rule, rel), e in sorted(by_key.items(), key=lambda kv: (order[kv[1]["severity"]], kv[0][1])):
        lines = e["lines"]
        where = f"line{'s' if len(lines) > 1 else ''} {', '.join(map(str, lines[:5]))}{'…' if len(lines) > 5 else ''}"
        is_key = rule == "private-key"
        out.append(finding(
            f"secret:{rule}:{rel}", e["severity"],
            f"{e['label']} committed in {rel}",
            f"Found on {where} of {rel} (value hidden). "
            + ("Treat the key as compromised: generate a new key pair, " if is_key else "Revoke and rotate it now, ")
            + "move it to an environment variable or secret manager, and remove it from git history.",
            30 if e["severity"] == "critical" else 20,
        ))
        if len(out) >= MAX_FINDINGS:
            break
    return out
