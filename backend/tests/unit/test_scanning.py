"""Scanner checks (bento_core.scanning). Fake credentials are assembled at runtime, never real."""

import json

import httpx
import pytest

from bento_core.scanning import MemoryCache, local_checks, run_checks
from bento_core.scanning.checks import hygiene, list_files, vulnerabilities
from bento_core.scanning.dockerfile import check_dockerfile, is_dockerfile
from bento_core.scanning.outdated import _is_prerelease, major, npm_direct, outdated
from bento_core.scanning.secretscan import entropy, secrets_in_code

FAKE_GH = "ghp_" + "Ab3" * 12
FAKE_AWS = "AKIA" + "Q7" * 8
FAKE_GENERIC = "k9Fq2LmX7pRt4ZsW8vB1"


def write(root, files: dict[str, str | bytes]):
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return sorted(files)


def keys(findings):
    return {f["key"] for f in findings}


# ---------- secrets ----------

def test_known_token_formats_are_found_and_masked(tmp_path):
    files = write(tmp_path, {"src/app.py": f'GH = "{FAKE_GH}"\nAWS = "{FAKE_AWS}"\napi_key = "{FAKE_GENERIC}"\n'})
    found = secrets_in_code(tmp_path, files)
    assert keys(found) == {"secret:github-token:src/app.py", "secret:aws-access-key:src/app.py", "secret:generic-secret:src/app.py"}
    dump = json.dumps(found)
    for value in (FAKE_GH, FAKE_AWS, FAKE_GENERIC):
        assert value not in dump, "a secret value leaked into a finding"
    gh = next(f for f in found if "github" in f["key"])
    assert gh["severity"] == "critical" and "line 1" in gh["detail"]


@pytest.mark.parametrize(
    "line",
    [
        'password = os.environ["DB_PASSWORD"]',
        'token = "your_token_here_123456"',
        'api_key = "xxxxxxxxxxxxxxxxxxxx"',
        'secret = "${SECRET_FROM_ENV_1234}"',
        'password = "correcthorsebatterystaple"',  # no digits: words, not a generated credential
        'token = "1234567890123456789"',  # digits only
    ],
)
def test_placeholders_and_env_lookups_are_not_secrets(tmp_path, line):
    files = write(tmp_path, {"config.py": line + "\n"})
    assert secrets_in_code(tmp_path, files) == []


def test_skips_lockfiles_binaries_vendored_and_env_files(tmp_path):
    files = write(tmp_path, {
        "package-lock.json": FAKE_GH,
        "logo.png": FAKE_GH,
        "data.bin": b"\x00\x01" + FAKE_GH.encode(),
        "third_party/lib.js": FAKE_GH,
        "app.min.js": FAKE_GH,
        ".env": f"TOKEN={FAKE_GH}",  # reported by the .env check instead
    })
    assert secrets_in_code(tmp_path, files) == []


def test_large_files_are_skipped(tmp_path):
    files = write(tmp_path, {"big.txt": "x" * 600_000 + f"\n{FAKE_GH}\n"})
    assert secrets_in_code(tmp_path, files) == []


def test_private_key_needs_key_material(tmp_path):
    header = "-----BEGIN RSA PRIVATE KEY-----"
    files = write(tmp_path, {
        "docs.md": f"KEY={header}\\nMIIE...\\n-----END RSA PRIVATE KEY-----\n",
        "header-only.txt": header + "\n",
        "server.key": header + "\n" + "Qm9n" * 16 + "\n",
    })
    assert keys(secrets_in_code(tmp_path, files)) == {"secret:private-key:server.key"}


def test_one_finding_per_rule_and_file_lists_lines(tmp_path):
    files = write(tmp_path, {"a.py": f'A = "{FAKE_GH}"\n\nB = "{FAKE_GH}"\n'})
    (f,) = secrets_in_code(tmp_path, files)
    assert "lines 1, 3" in f["detail"]


def test_entropy():
    assert entropy("aaaaaaaa") == 0
    assert entropy(FAKE_GENERIC) > 3.5


# ---------- Dockerfiles ----------

@pytest.mark.parametrize(
    ("path", "expected"),
    [("Dockerfile", True), ("api/Dockerfile.prod", True), ("docker/frontend.Dockerfile", True),
     ("scanning/dockerfile.py", False), ("Dockerfile.dockerignore", False), ("docs/dockerfile.md", False),
     ("examples/Dockerfile", False)],
)
def test_dockerfile_detection(path, expected):
    assert is_dockerfile(path) is expected


def test_dockerfile_problems():
    text = (
        "FROM node AS build\n"
        "ADD . /src\n"
        "FROM python:latest\n"
        "ENV API_TOKEN=abc123def DEBUG=1\n"
        "ARG NPM_TOKEN\n"
        "ADD https://example.com/a.tgz /tmp/\n"
    )
    found = {f["key"]: f for f in check_dockerfile("Dockerfile", text)}
    assert set(found) == {
        "docker:secret-env:Dockerfile", "docker:unpinned-base:Dockerfile", "docker:runs-as-root:Dockerfile",
        "docker:add-instead-of-copy:Dockerfile", "docker:no-healthcheck:Dockerfile",
    }
    assert "abc123def" not in json.dumps(found)  # the ENV value is never shown
    assert "NPM_TOKEN" not in found["docker:secret-env:Dockerfile"]["detail"]  # ARG without a value is fine
    assert "Line 2" in found["docker:add-instead-of-copy:Dockerfile"]["detail"]  # the URL ADD isn't flagged


def test_good_dockerfile_is_clean():
    text = (
        "# syntax=docker/dockerfile:1\n"
        "FROM python:3.12-slim AS base\n"
        "FROM base\n"  # an earlier stage, not an image
        "COPY . .\n"
        "RUN pip install \\\n    -r requirements.txt\n"
        "USER app\n"
        "HEALTHCHECK CMD curl -f http://localhost/ || exit 1\n"
    )
    assert check_dockerfile("Dockerfile", text) == []


def test_user_resets_per_stage_and_root_counts_as_root():
    multi = "FROM a:1 AS build\nUSER app\nFROM b:2\nHEALTHCHECK CMD true\n"
    assert "docker:runs-as-root:Dockerfile" in keys(check_dockerfile("Dockerfile", multi))
    root = "FROM a:1\nUSER root\nHEALTHCHECK CMD true\n"
    assert "docker:runs-as-root:Dockerfile" in keys(check_dockerfile("Dockerfile", root))


def test_digest_pinned_and_variable_images_are_fine():
    text = "ARG BASE=python:3.12\nFROM ${BASE}\nFROM alpine@sha256:abc\nUSER 10001\nHEALTHCHECK CMD true\n"
    assert check_dockerfile("Dockerfile", text) == []


def test_not_a_dockerfile_without_from():
    assert check_dockerfile("Dockerfile", "# empty\n") == []


# ---------- hygiene ----------

def test_hygiene_on_an_empty_project():
    assert keys(hygiene(["package.json"] + [f"src/{i}.js" for i in range(5)])) == {"no-tests", "no-ci", "no-readme", "no-lockfile"}


def test_hygiene_on_a_tidy_project():
    files = ["README.md", ".github/workflows/ci.yml", "package.json", "package-lock.json", "src/a.ts", "src/a.test.ts",
             ".env.example"]
    assert hygiene(files) == []


def test_committed_env_file_is_critical():
    (f,) = [f for f in hygiene([".env.production", "README.md"]) if f["key"] == "secrets-env-file"]
    assert f["severity"] == "critical" and ".env.production" in f["detail"]


def test_list_files_skips_dependencies(tmp_path):
    write(tmp_path, {"a.py": "", "node_modules/x/index.js": "", ".git/config": "", "sub/b.py": ""})
    assert sorted(list_files(tmp_path)) == ["a.py", "sub/b.py"]


# ---------- dependencies (OSV and registries mocked) ----------

def mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_vulnerabilities_from_osv(tmp_path):
    write(tmp_path, {
        "package-lock.json": json.dumps({"packages": {"": {}, "node_modules/lodash": {"version": "4.17.15"},
                                                      "node_modules/a/node_modules/nested": {"version": "1.0.0"}}}),
        "requirements.txt": "requests==2.19.0\nflask>=2\n",
    })
    seen = {}

    def handler(request):
        seen["queries"] = json.loads(request.content)["queries"]
        return httpx.Response(200, json={"results": [{"vulns": [{"id": "GHSA-1"}, {"id": "GHSA-2"}, {"id": "GHSA-3"}]}, {}]})

    async with mock_client(handler) as http:
        found = await vulnerabilities(tmp_path, http)
    assert [q["package"]["name"] for q in seen["queries"]] == ["lodash", "requests"]  # nested deps and >= pins skipped
    (f,) = found
    assert f["key"] == "vuln:npm:lodash" and f["severity"] == "critical"


async def test_osv_outage_is_not_fatal(tmp_path):
    write(tmp_path, {"requirements.txt": "requests==2.19.0\n"})
    async with mock_client(lambda r: httpx.Response(503)) as http:
        assert await vulnerabilities(tmp_path, http) == []


async def test_outdated_dependencies_and_cache(tmp_path):
    write(tmp_path, {
        "package.json": json.dumps({"dependencies": {"react": "^17.0.2", "local": "file:../x"},
                                    "devDependencies": {"@types/node": "~18.0.0", "vite": "^6.0.0"}}),
        "requirements.txt": "django==3.2\n",
    })
    latest = {"react": "19.1.0", "@types/node": "24.0.0", "vite": "6.3.0", "django": "5.2"}
    calls = []

    def handler(request):
        calls.append(str(request.url))
        path = request.url.path
        if "pypi" in request.url.host:
            name = path.split("/")[2]
            return httpx.Response(200, json={"info": {"version": latest[name]}})
        name = path.split("/latest")[0].lstrip("/").replace("%2F", "/").replace("%2f", "/")
        return httpx.Response(200, json={"version": latest[name]})

    cache = MemoryCache()
    async with mock_client(handler) as http:
        found = {f["key"]: f for f in await outdated(tmp_path, http, cache)}
        n = len(calls)
        await outdated(tmp_path, http, cache)
    assert len(calls) == n == 4, "second run should be served from the cache; file: deps aren't looked up"
    npm = found["outdated:npm"]
    assert npm["severity"] == "medium" and "@types/node" in npm["detail"] and "react" in npm["detail"]
    assert "vite" not in npm["detail"]
    assert found["outdated:PyPI"]["severity"] == "medium"


async def test_registry_errors_are_not_cached(tmp_path):
    write(tmp_path, {"requirements.txt": "django==3.2\n"})
    cache = MemoryCache()
    async with mock_client(lambda r: httpx.Response(500)) as http:
        assert await outdated(tmp_path, http, cache) == []
    assert await cache.get("registry:PyPI:django") is None


def test_version_helpers(tmp_path):
    assert major("^18.2.0") == 18 and major("v2") == 2 and major("latest") is None
    assert _is_prerelease("19.0.0-rc.1") and _is_prerelease("1.0b2") and not _is_prerelease("2.1.0")
    write(tmp_path, {"package.json": json.dumps({"dependencies": {"a": "git+https://x", "b": "^1.2.3"}})})
    assert npm_direct(tmp_path) == {"b": "1.2.3"}


async def test_run_checks_offline_sorts_worst_first(tmp_path):
    files = write(tmp_path, {"app.py": f'T = "{FAKE_GH}"\n'})
    found = await run_checks(tmp_path, files, None)
    assert found[0]["severity"] == "critical"
    assert keys(found) == keys(local_checks(tmp_path, files))
