"""What each fix changes. Pure functions over repository text, so they're easy to test without GitHub.

Supported finding keys: no-ci, no-readme, secrets-env-file, vuln:npm:<name>, vuln:PyPI:<name>.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import httpx
from packaging.version import InvalidVersion, Version

from bento_core.github import fixable_finding as fixable  # one definition, shared with the API

from gh import FixError

ENV_OK = {".env.example", ".env.sample", ".env.template", ".env.dist"}
OSV_QUERY = "https://api.osv.dev/v1/query"
FOOTER = (
    "\n\n---\n"
    "Opened by **Bento**. Bento never merges: review the change, let CI run, and merge it yourself. "
    "Once it's merged, the next scan marks the finding as resolved."
)




def branch_for(key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")[:60]
    return f"bento/fix-{slug}"


@dataclass
class Fix:
    title: str
    body: str
    message: str
    changes: dict[str, str | None] = field(default_factory=dict)


# ---------- language detection ----------

def detect_language(files: list[str]) -> str:
    names = {PurePosixPath(f).name for f in files if f.count("/") <= 1}
    top = set(files)
    if "package.json" in top:
        return "node"
    if top & {"requirements.txt", "pyproject.toml", "setup.py", "Pipfile"}:
        return "python"
    if "go.mod" in top:
        return "go"
    if "Cargo.toml" in top:
        return "rust"
    if names & {"pom.xml", "build.gradle", "build.gradle.kts"}:
        return "java"
    return "other"


# ---------- no-ci ----------

def _node_workflow(files: list[str], pkg: dict) -> str:
    top = set(files)
    if "pnpm-lock.yaml" in top:
        setup, install, run = "      - uses: pnpm/action-setup@v4\n", "pnpm install --frozen-lockfile", "pnpm"
        cache = "pnpm"
    elif "yarn.lock" in top:
        setup, install, run, cache = "", "yarn install --frozen-lockfile", "yarn", "yarn"
    else:
        setup, run, cache = "", "npm", "npm"
        install = "npm ci" if "package-lock.json" in top else "npm install"
    scripts = pkg.get("scripts") or {}
    steps = [f"      - run: {install}"]
    for s in ("lint", "test", "build"):
        if s in scripts and not (s == "test" and "no test specified" in str(scripts[s])):
            steps.append(f"      - run: {run} run {s}")
    cache_line = f"          cache: {cache}\n"
    return (
        "name: CI\n\non:\n  push:\n  pull_request:\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n"
        f"{setup}"
        "      - uses: actions/setup-node@v4\n        with:\n          node-version: 22\n"
        f"{cache_line}"
        + "\n".join(steps) + "\n"
    )


def _python_workflow(files: list[str]) -> str:
    top = set(files)
    if "requirements.txt" in top:
        install = "pip install -r requirements.txt"
    elif "pyproject.toml" in top or "setup.py" in top:
        install = "pip install ."
    else:
        install = "pip install pipenv && pipenv install --system --dev"
    has_tests = any(re.search(r"(^|/)(tests?/|test_[^/]+\.py$|[^/]+_test\.py$)", f) for f in files)
    test = "pip install pytest && pytest" if has_tests else "python -m compileall -q ."
    return (
        "name: CI\n\non:\n  push:\n  pull_request:\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n          cache: pip\n"
        f"      - run: {install}\n"
        f"      - run: {test}\n"
    )


SIMPLE_WORKFLOWS = {
    "go": "      - uses: actions/setup-go@v5\n        with:\n          go-version: stable\n      - run: go build ./...\n      - run: go test ./...\n",
    "rust": "      - run: cargo build --locked\n      - run: cargo test --locked\n",
    "java": "      - uses: actions/setup-java@v4\n        with:\n          distribution: temurin\n          java-version: '21'\n"
            "      - run: if [ -f mvnw ] || [ -f pom.xml ]; then mvn -B verify; else gradle build; fi\n",
    "other": "      - run: echo \"Add your build and test commands here\"\n",
}


def fix_no_ci(files: list[str], package_json: str | None) -> Fix:
    lang = detect_language(files)
    if lang == "node":
        try:
            pkg = json.loads(package_json or "{}")
        except ValueError:
            pkg = {}
        workflow = _node_workflow(files, pkg)
    elif lang == "python":
        workflow = _python_workflow(files)
    else:
        workflow = (
            "name: CI\n\non:\n  push:\n  pull_request:\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n" + SIMPLE_WORKFLOWS[lang]
        )
    path = ".github/workflows/ci.yml"
    if path in files:
        path = ".github/workflows/bento-ci.yml"
    label = {"node": "Node.js", "python": "Python", "go": "Go", "rust": "Rust", "java": "Java", "other": "a generic"}[lang]
    return Fix(
        title="Add a CI workflow",
        message="Add a GitHub Actions CI workflow",
        changes={path: workflow},
        body=(
            f"Bento found no CI pipeline, so nothing builds or tests this project on push.\n\n"
            f"This adds `{path}`, a {label} GitHub Actions workflow that runs on every push and pull request.\n\n"
            "**Before merging:** check the commands match how you build and test locally. The workflow runs on "
            "this pull request, so you can see it work (or fail) right here."
            + ("\n\nI couldn't detect the language, so the build step is a placeholder to fill in." if lang == "other" else "")
            + FOOTER
        ),
    )


# ---------- no-readme ----------

RUN_STEPS = {
    "node": "```bash\nnpm install\nnpm run dev\n```",
    "python": "```bash\npython -m venv .venv\nsource .venv/bin/activate\npip install -r requirements.txt\n```",
    "go": "```bash\ngo run .\n```",
    "rust": "```bash\ncargo run\n```",
    "java": "```bash\nmvn package\n```",
    "other": "Describe how to install and run the project.",
}


def fix_no_readme(files: list[str], repo: dict) -> Fix:
    name = repo.get("name") or "Project"
    desc = repo.get("description") or "One or two sentences on what this project does and who it's for."
    homepage = repo.get("homepage")
    lang = detect_language(files)
    text = (
        f"# {name}\n\n{desc}\n\n"
        + (f"**Live:** {homepage}\n\n" if homepage else "")
        + f"## Getting started\n\n{RUN_STEPS[lang]}\n\n"
        "## Project structure\n\nA quick map of the main folders.\n\n"
        "## Contributing\n\nOpen an issue or a pull request.\n"
    )
    return Fix(
        title="Add a README",
        message="Add a starter README",
        changes={"README.md": text},
        body=(
            "Bento found no README. This adds a starter `README.md` with the repository's name and description "
            "and a *Getting started* section guessed from the project's language.\n\n"
            "**Before merging:** fill in the placeholders. A README is often the first thing people read." + FOOTER
        ),
    )


# ---------- committed .env files ----------

def env_files(files: list[str]) -> list[str]:
    return [f for f in files if PurePosixPath(f).name.startswith(".env") and PurePosixPath(f).name not in ENV_OK]


def fix_env_file(files: list[str], gitignore: str | None) -> Fix:
    leaked = env_files(files)
    if not leaked:
        raise FixError("No committed .env file found any more; the next scan will resolve this finding.")
    lines = (gitignore or "").splitlines()
    have = {l.strip() for l in lines}
    add = [p for p in (".env", ".env.*", "!.env.example") if p not in have]
    changes: dict[str, str | None] = {f: None for f in leaked}  # delete; contents are never read
    if add:
        base = (gitignore or "").rstrip("\n")
        changes[".gitignore"] = (base + "\n\n" if base else "") + "# Local environment files (secrets)\n" + "\n".join(add) + "\n"
    listed = "\n".join(f"- `{f}`" for f in leaked)
    return Fix(
        title="Stop tracking .env files",
        message="Remove committed .env files and ignore them",
        changes=changes,
        body=(
            "Bento found environment files committed to the repository:\n\n"
            f"{listed}\n\n"
            "This removes them from the repository and adds them to `.gitignore` so they aren't committed again. "
            "Your local copies are not touched.\n\n"
            "> [!WARNING]\n"
            "> **Rotate every secret in these files now.** Removing a file doesn't remove it from git history: "
            "anyone who cloned the repo, or can see an old commit, can still read them. Generate new API keys, "
            "passwords and tokens, and revoke the old ones. To purge the history as well, use "
            "[`git filter-repo`](https://github.com/newren/git-filter-repo) and force-push.\n\n"
            "If the app needs these values, document them in a `.env.example` with placeholder values." + FOOTER
        ),
    )


# ---------- vulnerable dependencies ----------

def _v(s: str) -> Version | None:
    try:
        return Version(s)
    except InvalidVersion:
        return None


async def fixed_version(eco: str, name: str, current: str, http: httpx.AsyncClient) -> tuple[str, list[str]]:
    """Smallest version that fixes every known advisory affecting `current`, per OSV."""
    try:
        res = await http.post(OSV_QUERY, json={"package": {"ecosystem": eco, "name": name}, "version": current}, timeout=20)
        res.raise_for_status()
        vulns = res.json().get("vulns") or []
    except (httpx.HTTPError, ValueError) as exc:
        raise FixError(f"Could not reach OSV to look up a fixed version ({type(exc).__name__})") from None
    if not vulns:
        raise FixError(f"OSV lists no current advisories for {name} {current}; the next scan should resolve this finding.")
    cur = _v(current)
    needed: list[Version] = []
    unfixed: list[str] = []
    for vuln in vulns:
        candidates = []
        for aff in vuln.get("affected", []):
            pkg = aff.get("package", {})
            if pkg.get("ecosystem") != eco or pkg.get("name", "").lower() != name.lower():
                continue
            for rng in aff.get("ranges", []):
                for ev in rng.get("events", []):
                    fv = _v(ev.get("fixed", "")) if "fixed" in ev else None
                    if fv and (cur is None or fv > cur):
                        candidates.append(fv)
        if candidates:
            needed.append(min(candidates))
        else:
            unfixed.append(vuln["id"])
    if not needed:
        raise FixError(f"No fixed release of {name} is published yet for {', '.join(unfixed[:3])}.")
    return str(max(needed)), unfixed


def _indent(text: str) -> int | str:
    m = re.search(r"\n([ \t]+)\S", text)
    if not m:
        return 2
    return "\t" if m.group(1).startswith("\t") else len(m.group(1))


def bump_package_json(text: str, name: str, version: str) -> tuple[str, bool]:
    """(new package.json, transitive). A direct dependency's version is bumped in place, keeping the file's
    formatting. A package that only comes in through another one gets an npm `overrides` entry instead
    (npm 8.3+), which makes every copy of it at least the fixed version."""
    data = json.loads(text)
    sections = [s for s in ("dependencies", "devDependencies", "optionalDependencies") if name in (data.get(s) or {})]
    if sections:
        out = text
        for s in sections:
            old = data[s][name]
            prefix = re.match(r"^[\^~]?", old).group(0)
            pattern = re.compile(r'("' + re.escape(name) + r'"\s*:\s*")' + re.escape(old) + '"')
            out = pattern.sub(lambda m: m.group(1) + prefix + version + '"', out)
        return out, False
    overrides = data.get("overrides")
    if overrides is not None and not isinstance(overrides, dict):
        raise FixError("package.json has an overrides field Bento doesn't understand; add the override by hand.")
    data["overrides"] = {**(overrides or {}), name: f"^{version}"}
    out = json.dumps(data, indent=_indent(text), ensure_ascii=False)
    return out + ("\n" if text.endswith("\n") else ""), True


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def bump_requirements(text: str, name: str, version: str) -> tuple[str, bool]:
    out, changed = [], False
    for line in text.splitlines(keepends=True):
        m = re.match(r"^(\s*)([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*==\s*([A-Za-z0-9_.\-]+)(.*)$", line.rstrip("\r\n"))
        if m and _norm(m.group(2)) == _norm(name):
            eol = line[len(line.rstrip("\r\n")):]
            out.append(f"{m.group(1)}{m.group(2)}{m.group(3) or ''}=={version}{m.group(5)}{eol}")
            changed = True
        else:
            out.append(line)
    return "".join(out), changed


def npm_locked_version(lock: str | None, name: str) -> str | None:
    if not lock:
        return None
    try:
        data = json.loads(lock)
    except ValueError:
        return None
    return ((data.get("packages") or {}).get(f"node_modules/{name}") or {}).get("version")


def vuln_fix_body(eco: str, name: str, current: str, fixed: str, unfixed: list[str], lock_note: str) -> str:
    return (
        f"Bento found known vulnerabilities in **{name} {current}** ([OSV](https://osv.dev/list?ecosystem={eco}&q={name})).\n\n"
        f"This bumps it to **{fixed}**, the lowest release that fixes every advisory with a published fix.\n\n"
        + (f"Still unfixed upstream: {', '.join(unfixed[:5])}.\n\n" if unfixed else "")
        + lock_note
        + "**Before merging:** check the changelog for breaking changes"
        + (" (this crosses a major version)" if (_v(fixed) and _v(current) and _v(fixed).major > _v(current).major) else "")
        + " and make sure CI passes."
        + FOOTER
    )
