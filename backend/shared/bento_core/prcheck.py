"""PR checks: compare a pull request's head commit with its base and write the "Bento" check run.

The PR fails only if it *introduces* critical or high findings; problems that already existed on the
base branch are listed but never held against the PR. Findings never contain secret values (the
scanner masks them at the source), so the summary is safe to show on GitHub.
"""

from __future__ import annotations

SEVERITY_ORDER = ("critical", "high", "medium", "low")
BLOCKING = {"critical", "high"}
SEVERITY_LABEL = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}
CHECK_NAME = "Bento"
MAX_LISTED = 25  # GitHub caps the summary at 65k characters; keep it readable long before that


def compare(base: list[dict], head: list[dict]) -> dict:
    """Findings keyed by their stable key: what the PR adds, fixes, and leaves as it was."""
    before = {f["key"]: f for f in base}
    after = {f["key"]: f for f in head}
    by_severity = lambda f: (SEVERITY_ORDER.index(f["severity"]), f["title"])  # noqa: E731
    return {
        "new": sorted((f for k, f in after.items() if k not in before), key=by_severity),
        "fixed": sorted((f for k, f in before.items() if k not in after), key=by_severity),
        "unchanged": sorted((f for k, f in after.items() if k in before), key=by_severity),
    }


def conclusion(diff: dict) -> str:
    return "failure" if any(f["severity"] in BLOCKING for f in diff["new"]) else "success"


def _lines(findings: list[dict], with_detail: bool) -> list[str]:
    out = []
    for f in findings[:MAX_LISTED]:
        out.append(f"- **{SEVERITY_LABEL[f['severity']]}**: {f['title']}")
        if with_detail and f.get("detail"):
            out.append(f"  <br><sub>{f['detail']}</sub>")
    if len(findings) > MAX_LISTED:
        out.append(f"- …and {len(findings) - MAX_LISTED} more")
    return out


def report(diff: dict) -> dict:
    """Title + Markdown summary for the check run's output."""
    blocking = [f for f in diff["new"] if f["severity"] in BLOCKING]
    if blocking:
        title = f"{len(blocking)} new serious problem{'s' if len(blocking) > 1 else ''}"
    elif diff["new"]:
        title = f"No new serious problems ({len(diff['new'])} minor)"
    else:
        title = "No new problems" + (f", {len(diff['fixed'])} fixed" if diff["fixed"] else "")

    parts = []
    if blocking:
        parts.append(f"### ❌ This pull request adds {len(blocking)} critical or high problem{'s' if len(blocking) > 1 else ''}")
        parts.append("Fix these before merging. Secret values are never shown here; rotate any secret that was pushed, "
                     "even on a branch, because it is now in git history.")
    else:
        parts.append("### ✅ No new critical or high problems")
    if diff["new"]:
        parts += ["", "#### New in this pull request", *_lines(diff["new"], with_detail=True)]
    if diff["fixed"]:
        parts += ["", f"#### Fixed by this pull request 🎉", *_lines(diff["fixed"], with_detail=False)]
    if diff["unchanged"]:
        parts += ["", f"<details><summary>{len(diff['unchanged'])} problem{'s' if len(diff['unchanged']) > 1 else ''} "
                      "already on the base branch (not counted against this PR)</summary>", "",
                  *_lines(diff["unchanged"], with_detail=False), "", "</details>"]
    parts += ["", "<sub>Checked by Bento: repository code is read, never executed.</sub>"]
    return {"title": title, "summary": "\n".join(parts)}
