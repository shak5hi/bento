"""Engineering Health Score (0-100).

Uptime 40 + Latency 20 + Errors 20 + Code 20, over the last 30 minutes of probes.
Code starts at 20 and loses points per open finding by severity.
A project with no monitored endpoints is scored on code alone (basis = "code").
"""

from dataclasses import dataclass

FINDING_PENALTY = {"critical": 8.0, "high": 4.0, "medium": 1.5, "low": 0.5}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class Score:
    total: int
    uptime: float | None
    latency: float | None
    errors: float | None
    code: float
    basis: str  # "full" | "code"

    @property
    def status(self) -> str:
        return status_for(self.total)


def status_for(total: int | None) -> str:
    if total is None:
        return "unknown"
    if total >= 80:
        return "healthy"
    if total >= 50:
        return "degraded"
    return "critical"


def code_score(severities: list[str]) -> float:
    return max(0.0, 20.0 - sum(FINDING_PENALTY.get(s, 0.0) for s in severities))


def health_score(total: int, responded: int, failed: int, p95_ms: float | None, severities: list[str]) -> Score:
    code = code_score(severities)
    if total == 0:
        return Score(total=round(code * 5), uptime=None, latency=None, errors=None, code=code, basis="code")

    uptime_ratio = responded / total
    error_ratio = failed / responded if responded else 1.0
    p95 = p95_ms if p95_ms is not None else 2000.0

    u = 40 * _clamp((uptime_ratio - 0.95) / 0.05)
    l = 20 * _clamp(1 - (p95 - 300) / 1700)
    e = 20 * _clamp(1 - error_ratio / 0.10)
    return Score(total=round(u + l + e + code), uptime=u, latency=l, errors=e, code=code, basis="full")
