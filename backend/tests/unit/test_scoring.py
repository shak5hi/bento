import math

import pytest

from bento_core.scoring import code_score, health_score, status_for


@pytest.mark.parametrize(
    ("total", "status"),
    [(None, "unknown"), (100, "healthy"), (80, "healthy"), (79, "degraded"), (50, "degraded"), (49, "critical"), (0, "critical")],
)
def test_status_thresholds(total, status):
    assert status_for(total) == status


def test_code_score_starts_full_and_decays():
    assert code_score([]) == 20.0
    one_critical = code_score(["critical"])
    assert one_critical == pytest.approx(20 * math.exp(-8 / 25))
    assert code_score(["low"]) > code_score(["medium"]) > code_score(["high"]) > one_critical


def test_code_score_never_reaches_zero():
    assert 0 < code_score(["critical"] * 50) < 0.01


def test_unknown_severity_is_ignored():
    assert code_score(["bogus"]) == 20.0


def test_nothing_measured_yet_has_no_score():
    assert health_score(0, 0, 0, None, [], code_known=False) is None


def test_code_only_project_is_scaled_to_100():
    s = health_score(0, 0, 0, None, [], code_known=True)
    assert (s.total, s.basis, s.uptime) == (100, "code", None)


def test_perfect_project():
    s = health_score(total=30, responded=30, failed=0, p95_ms=120, severities=[])
    assert (s.total, s.uptime, s.latency, s.errors, s.code, s.basis) == (100, 40, 20, 20, 20, "full")


def test_uptime_below_95_percent_scores_zero():
    s = health_score(total=100, responded=90, failed=0, p95_ms=100, severities=[])
    assert s.uptime == 0
    assert s.total == 60


def test_slow_and_failing_endpoint():
    s = health_score(total=20, responded=20, failed=1, p95_ms=2000, severities=["high"])
    assert s.latency == 0  # p95 at or above 2 s
    assert s.errors == pytest.approx(10)  # 5% errors: half marks (10% or more scores zero)
    assert s.status in ("degraded", "critical")


def test_no_responses_counts_as_all_errors():
    s = health_score(total=5, responded=0, failed=0, p95_ms=None, severities=[])
    assert (s.uptime, s.errors, s.latency) == (0, 0, 0)
