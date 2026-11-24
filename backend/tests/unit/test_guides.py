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
