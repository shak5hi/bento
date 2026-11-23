"""Report-card scoring (bento_core.scoring)."""

import pytest

from bento_core.scoring import (
    basics_card, category, change_reason, grade_for, overall, score_project, security_card, status_for, upkeep_card,
    website_card,
)


def f(key, severity="low", title=None, effort=None, meta=None):
    return {"key": key, "severity": severity, "title": title or key, "effort_minutes": effort, "meta": meta}


GOOD_SITE = {"total": 2000, "ok": 2000, "p95": 180.0}
ALL_BASICS = []  # no basics findings = every checklist item done


@pytest.mark.parametrize(("score", "grade"), [(100, "A"), (90, "A"), (89, "B"), (80, "B"), (65, "C"), (64, "D"), (50, "D"), (49, "F"), (0, "F"), (None, None)])
def test_grades(score, grade):
    assert grade_for(score) == grade


@pytest.mark.parametrize(("total", "status"), [(None, "unknown"), (95, "healthy"), (80, "healthy"), (79, "degraded"), (50, "degraded"), (49, "critical")])
def test_status_matches_grades(total, status):
    assert status_for(total) == status


@pytest.mark.parametrize(
    ("key", "cat"),
    [("secret:github-token:a.py", "security"), ("secrets-env-file", "security"), ("vuln:npm:lodash", "security"),
     ("docker:secret-env:Dockerfile", "security"), ("outdated:npm", "upkeep"), ("no-tests", "basics"),
     ("docker:runs-as-root:Dockerfile", "basics")],
)
def test_categories(key, cat):
    assert category(key) == cat


# ---------- security: the worst problem decides ----------

@pytest.mark.parametrize(("worst", "score"), [(None, 100), ("low", 85), ("medium", 70), ("high", 50), ("critical", 20)])
def test_security_is_set_by_the_worst_problem(worst, score):
    findings = [f("vuln:npm:a", "low")] + ([f("secret:x:y", worst)] if worst else [])
    if worst is None:
        findings = []
    assert security_card(findings, scanned=True)["score"] == score


def test_one_leaked_key_is_an_f_however_clean_the_rest():
    card = security_card([f("secret:private-key:server.key", "critical", "Private key committed")], scanned=True)
    assert card["grade"] == "F" and "Private key committed" in card["summary"]


def test_unscanned_project_is_not_checked_rather_than_perfect():
    assert security_card([], scanned=False)["state"] == "not_checked"
    assert security_card([], scanned=False)["score"] is None


# ---------- code basics: a checklist ----------

def test_basics_checklist():
    card = basics_card([f("no-tests"), f("no-ci")], scanned=True)
    assert card["score"] == 40 and card["summary"].startswith("2 of 4 basics")
    assert [i["done"] for i in card["items"][:4]] == [True, False, False, True]


def test_dockerfile_habits_cost_at_most_15():
    habits = [f(f"docker:no-healthcheck:{i}/Dockerfile") for i in range(5)]
    assert basics_card(habits, scanned=True)["score"] == 85


# ---------- upkeep: share of libraries up to date ----------

def test_upkeep_from_scan_facts():
    card = upkeep_card([f("outdated:npm", meta={"behind": 4})], {"deps_checked": {"npm": 40}})
    assert card["score"] == 90 and "36 of 40" in card["summary"]


def test_upkeep_all_up_to_date():
    assert upkeep_card([], {"deps_checked": {"npm": 12, "PyPI": 3}})["score"] == 100


def test_upkeep_not_checked_without_dependencies():
    assert upkeep_card([], {"deps_checked": {}})["state"] == "not_checked"
    assert upkeep_card([], None)["score"] is None


def test_upkeep_for_old_findings_without_facts():
    card = upkeep_card([f("outdated:npm", title="17 npm packages are a major version or more behind")], None)
    assert card["score"] == 20  # 17 of an estimated 20: floor


# ---------- website: 7-day uptime target + speed ----------

def test_no_endpoint_means_not_monitored():
    assert website_card(None, endpoints=0)["state"] == "not_monitored"


def test_too_little_data_is_measuring():
    assert website_card({"total": 10, "ok": 10, "p95": 100}, endpoints=1)["state"] == "measuring"


@pytest.mark.parametrize(
    ("ok", "p95", "score"),
    [(1000, 300, 100),  # 100% up, fast
     (996, 300, 91),    # 99.6%: 85 for uptime
     (992, 300, 82),    # 99.2%: 70
     (960, 300, 70),    # 96%: 50
     (900, 300, 52),    # 90%: 20
     (1000, 1500, 88),  # slow-ish: 70 for speed
     (1000, 5000, 68)],
)
def test_website_score(ok, p95, score):
    assert website_card({"total": 1000, "ok": ok, "p95": p95}, endpoints=1)["score"] == score


def test_website_summary_is_readable():
    card = website_card({"total": 1000, "ok": 997, "p95": 1234}, endpoints=1)
    assert card["summary"] == "Up 99.7% · 1.2 s"


# ---------- overall ----------

def test_overall_is_a_weighted_average_of_measured_cards():
    cards = {"security": {"score": 100, "grade": "A"}, "website": {"score": None, "grade": None},
             "basics": {"score": 40, "grade": "F"}, "upkeep": {"score": None, "grade": None}}
    assert overall(cards)["total"] == round((100 * 35 + 40 * 20) / 55)  # website and upkeep left out


@pytest.mark.parametrize(("sec_grade", "cap"), [("F", 49), ("D", 69)])
def test_security_caps_the_overall(sec_grade, cap):
    score = {"F": 20, "D": 50}[sec_grade]
    cards = {"security": {"score": score, "grade": sec_grade}, "website": {"score": 100, "grade": "A"},
             "basics": {"score": 100, "grade": "A"}, "upkeep": {"score": 100, "grade": "A"}}
    result = overall(cards)
    assert result["total"] == cap and "Security" in result["capped"]


def test_nothing_measured_has_no_score():
    result = score_project([], None, endpoints=0, scanned=False, facts=None)
    assert result["total"] is None and result["grade"] is None


def test_nodegoat_like_project_is_no_longer_healthy():
    findings = [f("secret:private-key:artifacts/cert/server.key", "critical"), f("secret:generic-secret:config.js", "high"),
                f("outdated:npm", "medium", meta={"behind": 17}), f("docker:no-healthcheck:Dockerfile")]
    result = score_project(findings, GOOD_SITE, endpoints=1, scanned=True, facts={"deps_checked": {"npm": 30}})
    assert result["total"] <= 49 and result["grade"] == "F" and status_for(result["total"]) == "critical"


def test_clean_project_without_a_site():
    result = score_project([], None, endpoints=0, scanned=True, facts={"deps_checked": {"npm": 10}})
    assert result["total"] == 100 and result["basis"] == "code"
    assert result["cards"]["website"]["state"] == "not_monitored"
    assert result["next"]["key"] == "add-website"


# ---------- do this next ----------

def test_next_action_is_the_biggest_gain():
    findings = [f("no-readme", effort=20), f("secret:aws-access-key:a.py", "critical", "AWS key in a.py", effort=30),
                f("no-ci", effort=30)]
    result = score_project(findings, None, endpoints=0, scanned=True, facts=None)
    assert result["next"]["key"] == "secret:aws-access-key:a.py" and result["next"]["gain"] > 0
    after = score_project([x for x in findings if x["key"] != result["next"]["key"]], None, 0, True, None)
    assert after["total"] - result["total"] == result["next"]["gain"]


def test_next_action_prefers_the_quicker_fix_on_a_tie():
    findings = [f("docker:a:Dockerfile", effort=30), f("docker:b:Dockerfile", effort=5)]
    result = score_project(findings, GOOD_SITE, endpoints=1, scanned=True, facts=None)
    assert result["next"]["key"] == "docker:b:Dockerfile"


# ---------- why the score moved ----------

def test_change_reasons():
    before = {"findings": {"a": "Leaked key", "b": "No tests"}, "website": "B"}
    assert change_reason(None, before) == "First score"
    assert change_reason(before, {"findings": {"b": "No tests"}, "website": "B"}) == "Fixed: Leaked key"
    assert change_reason(before, {"findings": {"b": "No tests", "c": "No CI"}, "website": "C"}) == \
        "Fixed: Leaked key · New problem: No CI · Website grade B → C"
    assert change_reason(before, {"findings": {}, "website": "B"}) == "Fixed 2 problems"
    assert change_reason(before, dict(before)) == "Scoring updated"


def test_security_comes_first_while_it_caps_the_score():
    findings = [f("secret:private-key:a.key", "critical", "Private key in a.key", effort=30),
                f("secret:generic-secret:b.js", "high", "Password in b.js", effort=20),
                f("outdated:npm", "medium", meta={"behind": 5}), f("no-ci", effort=30)]
    result = score_project(findings, GOOD_SITE, endpoints=1, scanned=True, facts={"deps_checked": {"npm": 10}})
    nxt = result["next"]
    assert nxt["key"] == "secret:private-key:a.key"
    assert nxt["title"].startswith("Fix the 2 security problems") and nxt["gain"] > 0 and nxt["effortMinutes"] == 50
    fixed = [x for x in findings if not x["key"].startswith("secret:")]
    assert score_project(fixed, GOOD_SITE, 1, True, {"deps_checked": {"npm": 10}})["total"] - result["total"] == nxt["gain"]
