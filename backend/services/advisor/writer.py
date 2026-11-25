"""Pickle's writer: turns the rule-based plan into friendly, student-level explanations with a local model.

The rules have already decided *what* matters and in which order. The model is only asked *how to say
it*, and is given nothing but checked facts: the project's grade, its report cards and, for each of the
top problems, Bento's hand-written guide (bento_core.guides). Findings never contain secret values, so
neither does the prompt. Output is constrained to a JSON schema, checked, and thrown away in favour of
the rule-based text if it's missing, malformed, too long or the model is slow or down.
"""

from __future__ import annotations

import json
import logging

import httpx

log = logging.getLogger(__name__)

PROMPT_VERSION = "pickle-v2"  # bump to rewrite every saved plan
TIMEOUT_S = 600  # a small model on a laptop CPU can take minutes; this runs in the background and is cached
MAX_WHY, MAX_STEP, MAX_BRIEF = 320, 220, 360

SYSTEM = """You are Pickle, a friendly mentor inside Bento, an app that checks students' software projects.
You explain problems to a student developer in plain, warm, simple English.

Rules:
- Use ONLY the facts in the user's message. Never invent problems, files, numbers, tools or commands.
- The "plan" is already chosen and ordered. Return exactly one explanation per plan item, in the same order.
- For each item write "why": one or two short sentences on why it matters for THIS project.
- Then "steps": 2 to 4 short, concrete steps based on the guide's steps. Keep file and package names exactly as given.
- "brief": one or two sentences summarising where the project stands and what to do first. Encouraging, honest.
- No markdown, no emojis, no jargon without a short explanation."""

SCHEMA = {
    "type": "object",
    "properties": {
        "brief": {"type": "string"},
        "plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"why": {"type": "string"}, "steps": {"type": "array", "items": {"type": "string"}}},
                "required": ["why", "steps"],
            },
        },
    },
    "required": ["brief", "plan"],
}


def facts_for(project: str, score: dict | None, recs: list[dict], incidents: list[dict]) -> dict:
    """Everything the model may use, and nothing else."""
    cards = (score or {}).get("cards") or {}
    return {
        "project": project,
        "overall": {"score": (score or {}).get("total"), "grade": (score or {}).get("grade"),
                    "capped": (score or {}).get("capped")},
        "report_cards": {c["label"]: {"grade": c.get("grade"), "summary": c.get("summary")} for c in cards.values()},
        "live_incidents": [{"kind": i["kind"], "url": i["url"]} for i in incidents],
        "plan": [
            {"problem": r["title"], "severity": r["severity"], "minutes": r.get("effort_minutes"),
             **({"guide": {k: r["guide"][k] for k in ("what", "why", "steps")}} if r.get("guide") else {"detail": r.get("why")})}
            for r in recs
        ],
    }


def _clean(text, limit: int) -> str | None:
    if not isinstance(text, str):
        return None
    text = " ".join(text.split()).strip().strip('"')
    if not text or len(text) > limit:
        return None
    return text


def schema_for(n: int) -> dict:
    """The output schema with the plan pinned to exactly n items (small models otherwise stop after one)."""
    return {**SCHEMA, "properties": {**SCHEMA["properties"], "plan": {**SCHEMA["properties"]["plan"], "minItems": n, "maxItems": n}}}


def merge(recs: list[dict], output: dict) -> tuple[str, list[dict]] | None:
    """Use the model's brief and every well-formed explanation; an item it skipped or garbled keeps the
    rule-based text. None (all rules) only if the brief is unusable or no item is."""
    brief = _clean(output.get("brief"), MAX_BRIEF)
    plan = output.get("plan")
    if not brief or not isinstance(plan, list) or len(plan) > len(recs):
        return None
    merged, written = [], 0
    for i, rec in enumerate(recs):
        item = plan[i] if i < len(plan) and isinstance(plan[i], dict) else {}
        why = _clean(item.get("why"), MAX_WHY)
        steps = [s for s in (_clean(x, MAX_STEP) for x in (item.get("steps") or [])[:4]) if s]
        if why and steps:
            merged.append({**rec, "why": why, "steps": steps})
            written += 1
        else:
            merged.append(rec)
    return (brief, merged) if written else None


async def write(http: httpx.AsyncClient, base_url: str, model: str, facts: dict, recs: list[dict]) -> tuple[str, list[dict]] | None:
    """Ask the local model; None means "use the rule-based text" (and why is logged)."""
    if not base_url or not recs:
        return None
    try:
        res = await http.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "format": schema_for(len(recs)),
                "keep_alive": "30m",
                "options": {"temperature": 0.2, "num_predict": 700, "num_ctx": 4096},
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": json.dumps(facts, ensure_ascii=False)}],
            },
            timeout=TIMEOUT_S,
        )
        res.raise_for_status()
        output = json.loads(res.json()["message"]["content"])
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        log.info("Pickle's writer unavailable (%s); using rule-based text", type(exc).__name__)
        return None
    merged = merge(recs, output if isinstance(output, dict) else {})
    if merged is None:
        log.info("Pickle's writer returned unusable text; using rule-based text")
    return merged


async def ready(http: httpx.AsyncClient, base_url: str, model: str) -> bool:
    """True once Ollama is up and the model has finished downloading."""
    if not base_url:
        return False
    try:
        res = await http.get(f"{base_url}/api/tags", timeout=5)
        names = {m.get("name") for m in res.json().get("models", [])} if res.status_code == 200 else set()
    except (httpx.HTTPError, ValueError):
        return False
    return model in names or f"{model}:latest" in names
