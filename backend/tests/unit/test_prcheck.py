"""PR checks: head vs base comparison, the verdict, the GitHub summary, and the scanner job (GitHub faked)."""

import json

import pytest

from bento_core import github, prcheck
from helpers import load_service

FAKE_TOKEN = "ghp_" + "Ab3" * 12


def f(key, severity, title=None, detail=None):
    return {"key": key, "severity": severity, "title": title or key, "detail": detail, "effort_minutes": 10}


BASE = [f("no-tests", "medium", "No tests"), f("vuln:npm:lodash", "high", "lodash 4.17.15 has 2 known vulnerabilities")]


def test_compare_new_fixed_unchanged():
    head = [f("no-tests", "medium", "No tests"), f("secret:github-token:src/a.js", "critical", "GitHub token committed in src/a.js")]
    diff = prcheck.compare(BASE, head)
    assert [x["key"] for x in diff["new"]] == ["secret:github-token:src/a.js"]
    assert [x["key"] for x in diff["fixed"]] == ["vuln:npm:lodash"]
    assert [x["key"] for x in diff["unchanged"]] == ["no-tests"]


@pytest.mark.parametrize(
    ("new_severity", "outcome"), [("critical", "failure"), ("high", "failure"), ("medium", "success"), ("low", "success")],
)
def test_only_new_serious_problems_fail(new_severity, outcome):
    diff = prcheck.compare(BASE, BASE + [f("x", new_severity)])
    assert prcheck.conclusion(diff) == outcome


def test_existing_problems_never_fail_a_pr():
    assert prcheck.conclusion(prcheck.compare(BASE, BASE)) == "success"


def test_failure_report_lists_new_problems_and_warns_about_history():
    head = BASE + [f("secret:github-token:src/a.js", "critical", "GitHub token committed in src/a.js",
                     "Found on line 3 of src/a.js (value hidden).")]
    out = prcheck.report(prcheck.compare(BASE, head))
    assert out["title"] == "1 new serious problem"
    assert "❌" in out["summary"] and "**Critical**: GitHub token committed in src/a.js" in out["summary"]
    assert "rotate any secret" in out["summary"] and "value hidden" in out["summary"]
    assert "2 problems already on the base branch" in out["summary"]


def test_success_report_celebrates_fixes():
    out = prcheck.report(prcheck.compare(BASE, BASE[:1]))
    assert out["title"] == "No new problems, 1 fixed"
    assert "✅" in out["summary"] and "Fixed by this pull request" in out["summary"]


def test_minor_only_title():
    out = prcheck.report(prcheck.compare([], [f("no-readme", "low")]))
    assert out["title"] == "No new serious problems (1 minor)"


def test_long_lists_are_truncated():
    head = [f(f"k{i}", "low") for i in range(40)]
    assert "…and 15 more" in prcheck.report(prcheck.compare([], head))["summary"]


# ---------- the scanner's PR job ----------

class FakeRedis:
    def __init__(self):
        self.kv = {}

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, value, ex=None, nx=False):
        self.kv[key] = value
        return True


@pytest.fixture
def scanner(monkeypatch):
    mod = load_service("scanner")
    calls = {"created": [], "completed": [], "scanned": []}

    async def create(repo, inst, sha, name, http, details_url=None):
        calls["created"].append((repo, sha, name))
        return 77

    async def complete(repo, inst, check_id, conclusion, title, summary, http):
        calls["completed"].append({"id": check_id, "conclusion": conclusion, "title": title, "summary": summary})

    async def token(inst, http):
        return "installation-token-for-tests"

    monkeypatch.setattr(github, "create_check_run", create)
    monkeypatch.setattr(github, "complete_check_run", complete)
    monkeypatch.setattr(github, "installation_token", token)
    s = mod.Scanner(pg=None, r=FakeRedis(), http=None)
    commits = {"base1": BASE, "head1": BASE + [f("secret:aws-access-key:cfg.py", "critical", "AWS access key ID committed in cfg.py")]}

    async def scan_commit(url, sha, auth):
        calls["scanned"].append(sha)
        if sha == "broken":
            raise mod.ScanError("git fetch timed out")
        return commits[sha], {}

    monkeypatch.setattr(s, "scan_commit", scan_commit)
    return s, calls


JOB = {"kind": "pr", "repo": "acme/shop", "installation_id": 99, "head_sha": "head1", "base_sha": "base1", "pr_number": 5}


async def test_pr_job_fails_on_a_new_secret_and_caches_the_base(scanner):
    s, calls = scanner
    await s.run(JOB)
    assert calls["created"] == [("acme/shop", "head1", "Bento")]
    (done,) = calls["completed"]
    assert done["conclusion"] == "failure" and done["title"] == "1 new serious problem"
    assert FAKE_TOKEN not in done["summary"]
    await s.run({**JOB})
    assert calls["scanned"] == ["base1", "head1"], "second run served from the cache"
    assert json.loads(s.r.kv["prscan:https://github.com/acme/shop:base1"])[0]["key"] == "no-tests"


async def test_a_failed_scan_is_neutral_not_a_failure(scanner):
    s, calls = scanner
    await s.run({**JOB, "head_sha": "broken"})
    (done,) = calls["completed"]
    assert done["conclusion"] == "neutral" and "git fetch timed out" in done["summary"]


async def test_unexpected_errors_still_complete_the_check(scanner, monkeypatch):
    s, calls = scanner

    async def boom(url, sha, auth):
        raise KeyError("surprise")

    monkeypatch.setattr(s, "scan_commit", boom)
    await s.run(JOB)
    assert calls["completed"][0]["conclusion"] == "neutral"
