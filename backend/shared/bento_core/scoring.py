"""Bento's health score: four report cards and one overall grade.

    Security     the worst problem sets the grade (one leaked key = F)          weight 35
    Website      uptime against a 99.5% target + speed, over the last 7 days    weight 30
    Code basics  a checklist: README, tests, CI, lockfile, Dockerfile habits     weight 20
    Upkeep       share of libraries no more than a major version behind          weight 15

Overall = weighted average of the cards that were actually measured (an unmeasured card says so and
is left out, it never counts as perfect). Two caps keep it honest: Security F caps the overall at 49,
Security D at 69. Grades: A 90+, B 80+, C 65+, D 50+, F below 50.

Everything here is a pure function of raw facts (open findings, probe stats, scan facts), so the
thresholds can be retuned and every score recomputed. Bump FORMULA when they change.
"""

from __future__ import annotations

import re

FORMULA = "cards-v1"

WEIGHTS = {"security": 35, "website": 30, "basics": 20, "upkeep": 15}
LABELS = {"security": "Security", "website": "Website", "basics": "Code basics", "upkeep": "Upkeep"}
GRADES = ((90, "A"), (80, "B"), (65, "C"), (50, "D"), (0, "F"))
SEVERITY_ORDER = ("critical", "high", "medium", "low")

# Security: the worst open problem decides
SECURITY_BY_WORST = {None: 100, "low": 85, "medium": 70, "high": 50, "critical": 20}
CAPS = {"F": 49, "D": 69}

# Code basics checklist (points out of 100); Dockerfile habits cost 5 each, at most 15
CHECKLIST = (
    ("no-readme", "README", 20),
    ("no-tests", "Automated tests", 30),
    ("no-ci", "CI pipeline", 30),
    ("no-lockfile", "Locked dependencies", 20),
)
DOCKER_HABIT_COST, DOCKER_HABIT_MAX = 5, 15

# Website
MIN_PROBES = 30  # below this the card says "Measuring…"
UPTIME_BANDS = ((99.9, 100), (99.5, 85), (99.0, 70), (95.0, 50))
SPEED_BANDS = ((500, 100), (1000, 85), (2000, 70), (4000, 50))  # p95 ms, upper bounds
UPTIME_SHARE = 0.6

UPKEEP_FLOOR = 20


def grade_for(score: int | None) -> str | None:
    if score is None:
        return None
    return next(g for threshold, g in GRADES if score >= threshold)


def status_for(total: int | None) -> str:
    """healthy = A/B, degraded = C/D, critical = F."""
    if total is None:
        return "unknown"
    if total >= 80:
        return "healthy"
    if total >= 50:
        return "degraded"
    return "critical"


def category(key: str) -> str:
    if key.startswith(("secret:", "secrets-env-file", "vuln:", "docker:secret-env:")):
        return "security"
    if key.startswith("outdated:"):
        return "upkeep"
    return "basics"


def _card(key: str, score: int | None, state: str, summary: str, items: list[dict]) -> dict:
    return {
        "key": key,
        "label": LABELS[key],
        "score": score,
        "grade": grade_for(score),
        "state": state,  # measured | not_monitored | measuring | not_checked
        "summary": summary,
        "items": items,
    }


# ---------- the four cards ----------

def security_card(findings: list[dict], scanned: bool) -> dict:
    if not scanned:
        return _card("security", None, "not_checked", "Connect a repository to check for leaked secrets", [])
    issues = sorted(
        (f for f in findings if category(f["key"]) == "security"),
        key=lambda f: SEVERITY_ORDER.index(f["severity"]),
    )
    worst = issues[0]["severity"] if issues else None
    score = SECURITY_BY_WORST[worst]
    if not issues:
        summary = "No leaked secrets or vulnerable libraries"
    else:
        summary = f"{len(issues)} security problem{'s' if len(issues) > 1 else ''}, worst: {issues[0]['title']}"
    items = [{"label": f["title"], "severity": f["severity"], "key": f["key"]} for f in issues]
    return _card("security", score, "measured", summary, items)


def basics_card(findings: list[dict], scanned: bool) -> dict:
    if not scanned:
        return _card("basics", None, "not_checked", "Connect a repository to check the basics", [])
    open_keys = {f["key"] for f in findings}
    items, lost = [], 0
    for key, label, points in CHECKLIST:
        missing = key in open_keys
        lost += points if missing else 0
        items.append({"label": label, "done": not missing, "points": points, "key": key})
    habits = [f for f in findings if f["key"].startswith("docker:") and category(f["key"]) == "basics"]
    habit_cost = min(DOCKER_HABIT_MAX, DOCKER_HABIT_COST * len(habits))
    for f in habits:
        items.append({"label": f["title"], "done": False, "points": DOCKER_HABIT_COST, "key": f["key"]})
    done = sum(1 for i in items[: len(CHECKLIST)] if i["done"])
    summary = f"{done} of {len(CHECKLIST)} basics in place"
    if habits:
        summary += f", {len(habits)} Dockerfile habit{'s' if len(habits) > 1 else ''} to fix"
    return _card("basics", max(0, 100 - lost - habit_cost), "measured", summary, items)


def _behind(f: dict) -> int:
    meta = f.get("meta") or {}
    if isinstance(meta.get("behind"), int):
        return meta["behind"]
    m = re.match(r"(\d+)", f.get("title") or "")  # findings saved before meta existed
    return int(m.group(1)) if m else 1


def upkeep_card(findings: list[dict], facts: dict | None) -> dict:
    checked = sum((facts or {}).get("deps_checked", {}).values())
    outdated = [f for f in findings if category(f["key"]) == "upkeep"]
    behind = sum(_behind(f) for f in outdated)
    if not checked:
        if not outdated:
            return _card("upkeep", None, "not_checked", "No npm or PyPI dependencies found to check", [])
        checked = max(behind, 20)  # facts not recorded yet (scanned before this version): estimate
    behind = min(behind, checked)
    score = max(UPKEEP_FLOOR, round(100 * (checked - behind) / checked))
    summary = (
        f"All {checked} libraries are up to date" if not behind
        else f"{checked - behind} of {checked} libraries up to date, {behind} a major version behind"
    )
    items = [{"label": f["title"], "severity": f["severity"], "key": f["key"]} for f in outdated]
    return _card("upkeep", score, "measured", summary, items)


def _band(value: float, bands, higher_is_better: bool) -> int:
    for limit, points in bands:
        if (value >= limit) if higher_is_better else (value < limit):
            return points
    return 20


def website_card(probes: dict | None, endpoints: int) -> dict:
    """probes: {"total", "ok", "p95"} over the last 7 days."""
    if not endpoints:
        return _card("website", None, "not_monitored", "Add your site's URL to track uptime and speed", [])
    if not probes or probes["total"] < MIN_PROBES:
        return _card("website", None, "measuring", "Measuring… the first grade appears after about 30 checks", [])
    uptime = 100 * probes["ok"] / probes["total"]
    p95 = probes["p95"]
    up_points = _band(uptime, UPTIME_BANDS, True)
    speed_points = _band(p95, SPEED_BANDS, False) if p95 is not None else 20
    score = round(UPTIME_SHARE * up_points + (1 - UPTIME_SHARE) * speed_points)
    shown = "100" if uptime >= 99.995 else f"{uptime:.2f}".rstrip("0").rstrip(".")
    speed = f"{p95 / 1000:.1f} s" if p95 is not None and p95 >= 1000 else (f"{round(p95)} ms" if p95 is not None else "no responses")
    items = [
        {"label": f"Up {shown}% of the last 7 days (target 99.5%)", "points": up_points},
        {"label": f"95% of responses within {speed}", "points": speed_points},
    ]
    return _card("website", score, "measured", f"Up {shown}% · {speed}", items)


# ---------- overall ----------

def overall(cards: dict[str, dict]) -> dict:
    measured = {k: c for k, c in cards.items() if c["score"] is not None}
    if not measured:
        return {"total": None, "grade": None, "capped": None}
    weight = sum(WEIGHTS[k] for k in measured)
    total = round(sum(c["score"] * WEIGHTS[k] for k, c in measured.items()) / weight)
    capped = None
    sec = cards.get("security", {}).get("grade")
    if sec in CAPS and total > CAPS[sec]:
        total, capped = CAPS[sec], f"Capped at {CAPS[sec]} until the Security grade is above {sec}"
    return {"total": total, "grade": grade_for(total), "capped": capped}


def score_project(findings: list[dict], probes: dict | None, endpoints: int, scanned: bool, facts: dict | None) -> dict:
    cards = {
        "security": security_card(findings, scanned),
        "website": website_card(probes, endpoints),
        "basics": basics_card(findings, scanned),
        "upkeep": upkeep_card(findings, facts),
    }
    result = overall(cards)
    return {**result, "cards": cards, "next": next_action(findings, probes, endpoints, scanned, facts, result["total"]),
            "basis": "full" if cards["website"]["score"] is not None else "code", "formula": FORMULA}


def next_action(findings, probes, endpoints, scanned, facts, total) -> dict | None:
    """The single fix that raises the overall score most (ties: the quicker fix).

    While Security caps the score, security comes first: fixing one of several serious problems may not
    lift the cap on its own, but nothing else matters as much, so the advice is to fix that group.
    """
    security = sorted((f for f in findings if category(f["key"]) == "security"),
                      key=lambda f: SEVERITY_ORDER.index(f["severity"]))
    if security and security_card(findings, scanned)["grade"] in CAPS:
        rest = [g for g in findings if category(g["key"]) != "security"]
        cards = {
            "security": security_card(rest, scanned), "website": website_card(probes, endpoints),
            "basics": basics_card(rest, scanned), "upkeep": upkeep_card(rest, facts),
        }
        gain = (overall(cards)["total"] or 0) - (total or 0)
        first = security[0]
        if len(security) == 1:
            title = first["title"]
        else:
            title = f"Fix the {len(security)} security problems, starting with: {first['title']}"
        return {"key": first["key"], "title": title, "gain": gain if gain > 0 else None,
                "effortMinutes": sum(f.get("effort_minutes") or 20 for f in security)}
    best = None
    for f in findings:
        rest = [g for g in findings if g is not f]
        cards = {
            "security": security_card(rest, scanned), "website": website_card(probes, endpoints),
            "basics": basics_card(rest, scanned), "upkeep": upkeep_card(rest, facts),
        }
        gain = (overall(cards)["total"] or 0) - (total or 0)
        if gain <= 0:
            continue
        candidate = (gain, -(f.get("effort_minutes") or 60))
        if best is None or candidate > best[0]:
            best = (candidate, {"key": f["key"], "title": f["title"], "gain": gain, "effortMinutes": f.get("effort_minutes")})
    if best:
        return best[1]
    if not endpoints:
        return {"key": "add-website", "title": "Add your site's URL so Bento can grade uptime and speed", "gain": None,
                "effortMinutes": 2}
    return None


def change_reason(before: dict | None, after: dict) -> str:
    """Why the score moved, from two input snapshots: {"findings": {key: title}, "website": grade}."""
    if not before:
        return "First score"
    old, new = before.get("findings", {}), after.get("findings", {})
    fixed = [old[k] for k in old if k not in new]
    added = [new[k] for k in new if k not in old]
    parts = []
    if len(fixed) == 1:
        parts.append(f"Fixed: {fixed[0]}")
    elif fixed:
        parts.append(f"Fixed {len(fixed)} problems")
    if len(added) == 1:
        parts.append(f"New problem: {added[0]}")
    elif added:
        parts.append(f"{len(added)} new problems")
    if before.get("website") != after.get("website"):
        a, b = before.get("website"), after.get("website")
        parts.append(f"Website grade {a} → {b}" if a and b else ("Website now graded" if b else "Website no longer graded"))
    return " · ".join(parts) or "Scoring updated"
