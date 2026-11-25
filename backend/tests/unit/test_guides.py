"""Every kind of finding the scanner can report has a plain-language guide."""

import pytest

from bento_core.guides import guide_for
from bento_core.scanning.secretscan import TOKEN_RULES

SCANNER_KEYS = (
    [f"secret:{rule}:src/config.js" for rule, *_ in TOKEN_RULES]
    + ["secret:generic-secret:src/config.js", "secrets-env-file", "vuln:npm:lodash", "vuln:PyPI:requests",
       "outdated:npm", "outdated:PyPI", "no-tests", "no-ci", "no-readme", "no-lockfile"]
    + [f"docker:{c}:api/Dockerfile" for c in ("secret-env", "unpinned-base", "runs-as-root", "add-instead-of-copy", "no-healthcheck")]
)


@pytest.mark.parametrize("key", SCANNER_KEYS)
def test_every_finding_has_a_complete_guide(key):
    g = guide_for(key)
    assert g is not None, key
    assert g["what"] and g["why"] and g["steps"] and g["learn"].startswith("https://")
    text = " ".join([g["what"], g["why"], *g["steps"]])
    assert "{" not in text, f"unfilled placeholder in {key}: {text}"


def test_file_and_package_are_filled_in():
    assert "src/config.js" in guide_for("secret:aws-access-key:src/config.js")["what"]
    assert "lodash" in guide_for("vuln:npm:lodash")["what"]
    assert "api/Dockerfile" in guide_for("docker:runs-as-root:api/Dockerfile")["what"]
    assert "npm install @babel/core@latest" in guide_for("vuln:npm:@babel/core")["steps"][0]
    assert "pip install" in guide_for("vuln:PyPI:requests")["steps"][1]
    assert "npm" not in " ".join(guide_for("vuln:PyPI:requests")["steps"])


def test_unknown_keys_have_no_guide():
    assert guide_for("something-new") is None


# ---------- plain words ----------

from bento_core.guides import plain, plain_incident  # noqa: E402


@pytest.mark.parametrize("key", SCANNER_KEYS)
def test_every_finding_has_plain_words(key):
    title, line = plain(key, "Scanner title", "Scanner detail")
    assert title != "Scanner title" and line, key
    jargon = ("GHSA", "advisor", "vulnerabilit", "p95", "endpoint", "root in", "HEALTHCHECK", "lockfile")
    assert not any(j.lower() in (title + line).lower() for j in jargon), (key, title, line)


def test_plain_words_fill_in_the_details():
    assert plain("secret:github-token:src/a.js", "t")[1].startswith("In src/a.js.")
    assert plain("vuln:npm:browserslist", "t")[0] == "A library you use has known security holes: browserslist"
    assert "only used while developing" in plain("vuln:npm:vite", "t", None, {"dev": True})[1]
    assert plain("outdated:npm", "38 npm packages are a major version or more behind")[0] == "38 of your libraries are very out of date"
    assert plain("outdated:npm", "x", None, {"behind": 5})[0] == "5 of your libraries are very out of date"
    one = plain("outdated:PyPI", "1 PyPI package is a major version or more behind")
    assert one == ("1 of your libraries is very out of date", "It's a whole version or more behind, so it has stopped getting fixes. Update it.")
    assert "api/Dockerfile" in plain("docker:runs-as-root:api/Dockerfile", "t")[1]


def test_unknown_findings_keep_their_own_words():
    assert plain("something-new", "Original title", "Original detail") == ("Original title", "Original detail")


def test_plain_incidents():
    assert plain_incident("errors", "https://shop.example.com/api", 0.6, 0.0) == (
        "Your site is failing for visitors", "shop.example.com: 60% of Bento's checks are failing right now.")
    assert plain_incident("latency", "https://shop.example.com", 1240, 410)[1] == "shop.example.com is taking 1.2 s instead of about 410 ms."
