"""Dockerfile checks: unpinned base images, running as root, ADD instead of COPY, secrets in ENV/ARG,
no HEALTHCHECK. Keys are `docker:<check>:<path>` so they stay stable across commits."""

import re
from pathlib import Path

from checks import finding

MAX_DOCKERFILE_BYTES = 256 * 1024
SECRET_NAME = re.compile(r"(?i)(secret|token|passw(or)?d|pwd|api[_-]?key|access[_-]?key|private[_-]?key|credential)")
SKIP_DIRS = {"third_party", "bower_components", "testdata", "examples", "fixtures"}


def is_dockerfile(rel: str) -> bool:
    p = Path(rel)
    name = p.name.lower()
    if any(part in SKIP_DIRS for part in p.parts):
        return False
    return name == "dockerfile" or name.startswith("dockerfile.") or name.endswith(".dockerfile")


def instructions(text: str) -> list[tuple[int, str, str]]:
    """(line, INSTRUCTION, arguments) with continuations joined and comments dropped."""
    out: list[tuple[int, str, str]] = []
    buf, start = "", 0
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not buf and (not line or line.startswith("#")):
            continue
        if buf and line.startswith("#"):
            continue  # comment inside a continuation
        if not buf:
            start = n
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        buf += line
        parts = buf.split(None, 1)
        if parts:
            out.append((start, parts[0].upper(), parts[1] if len(parts) > 1 else ""))
        buf = ""
    return out


def _unpinned(image: str, stages: set[str]) -> str | None:
    """'latest' / 'untagged' when the base image floats, else None."""
    if image.lower() in stages or image == "scratch" or "$" in image or "@sha256:" in image:
        return None
    last = image.rsplit("/", 1)[-1]
    if ":" not in last:
        return "untagged"
    return "latest" if last.split(":", 1)[1] == "latest" else None


def _env_pairs(instr: str, args: str) -> list[tuple[str, str]]:
    """Name/value pairs from ENV a=b c=d, ENV a b, ARG a=b. Values are only used to decide, never reported."""
    if instr == "ENV" and "=" not in args.split(None, 1)[0]:
        parts = args.split(None, 1)  # legacy form: ENV NAME value
        return [(parts[0], parts[1] if len(parts) > 1 else "")]
    pairs = []
    for m in re.finditer(r"""([A-Za-z_][A-Za-z0-9_]*)(?:=("[^"]*"|'[^']*'|\S*))?""", args):
        pairs.append((m.group(1), (m.group(2) or "").strip("\"'")))
    return pairs


def check_dockerfile(rel: str, text: str) -> list[dict]:
    ins = instructions(text)
    if not any(i == "FROM" for _, i, _ in ins):
        return []
    out = []
    stages: set[str] = set()
    floating: list[str] = []
    final_user: str | None = None
    adds: list[int] = []
    secret_vars: list[str] = []
    has_healthcheck = False

    for line, instr, args in ins:
        if instr == "FROM":
            words = [w for w in args.split() if not w.startswith("--")]
            if words:
                if kind := _unpinned(words[0], stages):
                    floating.append(f"{words[0]} ({kind}, line {line})")
                if len(words) >= 3 and words[1].lower() == "as":
                    stages.add(words[2].lower())
            final_user = None  # USER resets per stage; only the final stage runs
            has_healthcheck = False
        elif instr == "USER":
            final_user = args.split()[0] if args.split() else None
        elif instr == "ADD":
            srcs = [w for w in args.split() if not w.startswith("--")][:-1]
            # ADD is right for remote URLs and local tarballs it should unpack
            if srcs and not any(s.startswith(("http://", "https://", "git@")) or re.search(r"\.(tar(\.\w+)?|tgz)$", s) for s in srcs):
                adds.append(line)
        elif instr in ("ENV", "ARG"):
            for name, value in _env_pairs(instr, args):
                if SECRET_NAME.search(name) and value and not value.startswith("$"):
                    secret_vars.append(f"{instr} {name} (line {line})")
        elif instr == "HEALTHCHECK":
            has_healthcheck = not args.strip().upper().startswith("NONE")

    if secret_vars:
        out.append(finding(
            f"docker:secret-env:{rel}", "high", f"Secret baked into the image in {rel}",
            f"{', '.join(secret_vars[:4])} sets a credential at build time (value hidden). ENV and ARG values are "
            "stored in the image layers and history: pass it at runtime or use a BuildKit secret mount, and rotate it.",
            30,
        ))
    if floating:
        out.append(finding(
            f"docker:unpinned-base:{rel}", "medium", f"Unpinned base image in {rel}",
            f"{', '.join(floating[:3])}. A floating tag changes under you and builds stop being reproducible: "
            "pin a version tag (e.g. python:3.12-slim) or a digest.",
            10,
        ))
    if final_user is None or final_user.split(":")[0] in ("root", "0"):
        out.append(finding(
            f"docker:runs-as-root:{rel}", "medium", f"Container runs as root in {rel}",
            "The final stage has no non-root USER, so a compromise of the app is root in the container. "
            "Create a user (e.g. RUN useradd -u 10001 app) and add USER app.",
            15,
        ))
    if adds:
        out.append(finding(
            f"docker:add-instead-of-copy:{rel}", "low", f"ADD used where COPY would do in {rel}",
            f"Line{'s' if len(adds) > 1 else ''} {', '.join(map(str, adds[:5]))}. ADD also fetches URLs and unpacks "
            "archives, which can surprise you; COPY only copies files.",
            5,
        ))
    if not has_healthcheck:
        out.append(finding(
            f"docker:no-healthcheck:{rel}", "low", f"No HEALTHCHECK in {rel}",
            "Without a HEALTHCHECK, Docker can't tell a hung container from a healthy one. "
            "Add one that hits a cheap endpoint, e.g. HEALTHCHECK CMD wget -qO- http://127.0.0.1:8000/health || exit 1.",
            10,
        ))
    return out


def dockerfiles(root: Path, files: list[str]) -> list[dict]:
    out = []
    for rel in [f for f in files if is_dockerfile(f)][:20]:
        path = root / rel
        try:
            if path.stat().st_size > MAX_DOCKERFILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        out.extend(check_dockerfile(rel, text))
    return out
