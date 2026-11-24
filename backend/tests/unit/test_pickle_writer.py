"""Pickle's writer: grounded prompt, schema-constrained output, and falling back to rules on anything odd."""

import json

import httpx
import pytest

from helpers import load_service

writer = load_service("advisor", "writer")

RECS = [
    {"key": "secret:aws-access-key:cfg.py", "title": "AWS access key ID committed in cfg.py", "severity": "critical",
     "why": "rule why", "steps": ["rule step"], "effort_minutes": 30,
     "guide": {"what": "A real AWS access key is written directly in cfg.py.", "why": "Treat it as leaked.",
               "steps": ["Deactivate the key.", "Read it from an environment variable."], "learn": "https://x"}},
    {"key": "no-ci", "title": "No CI pipeline", "severity": "low", "why": "rule why 2", "steps": [], "effort_minutes": 30},
]
GOOD = {"brief": "Shop has one urgent problem: a leaked AWS key. Fix that first, then add CI.",
        "plan": [{"why": "Anyone can use your key.", "steps": ["Deactivate the key in AWS.", "Use an environment variable."]},
                 {"why": "CI catches broken builds.", "steps": ["Add a GitHub Actions workflow."]}]}


def ollama(reply, seen=None, status=200):
    def handler(request):
        if seen is not None:
            seen.append(json.loads(request.content))
        if isinstance(reply, Exception):
            raise reply
        return httpx.Response(status, json={"message": {"content": reply if isinstance(reply, str) else json.dumps(reply)}})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_facts_contain_only_checked_information():
    score = {"total": 49, "grade": "F", "capped": "Capped at 49",
             "cards": {"security": {"label": "Security", "grade": "F", "summary": "1 problem", "items": [{"x": 1}]}}}
    facts = writer.facts_for("Shop", score, RECS, [])
    assert facts["overall"] == {"score": 49, "grade": "F", "capped": "Capped at 49"}
    assert facts["report_cards"] == {"Security": {"grade": "F", "summary": "1 problem"}}
    assert facts["plan"][0]["guide"]["steps"] == ["Deactivate the key.", "Read it from an environment variable."]
    assert "learn" not in facts["plan"][0]["guide"] and facts["plan"][1]["detail"] == "rule why 2"


async def test_good_output_is_merged_in_plan_order():
    seen = []
    async with ollama(GOOD, seen) as http:
        brief, recs = await writer.write(http, "http://ollama", "qwen2.5:1.5b", writer.facts_for("Shop", None, RECS, []), RECS)
    assert brief.startswith("Shop has one urgent problem")
    assert [r["title"] for r in recs] == [r["title"] for r in RECS]  # titles, order and severity stay the rules'
    assert recs[0]["why"] == "Anyone can use your key." and recs[0]["severity"] == "critical"
    body = seen[0]
    assert body["model"] == "qwen2.5:1.5b" and body["stream"] is False
    assert body["format"]["properties"]["plan"]["minItems"] == body["format"]["properties"]["plan"]["maxItems"] == 2
    assert body["messages"][0]["role"] == "system" and "ONLY the facts" in body["messages"][0]["content"]


@pytest.mark.parametrize(
    "reply",
    [
        {"brief": "", "plan": GOOD["plan"]},                             # empty brief
        {"brief": "ok", "plan": GOOD["plan"] + GOOD["plan"]},          # more items than asked
        {"brief": "ok", "plan": [{"why": "x", "steps": []}, {"why": "", "steps": ["a"]}]},  # nothing usable
        {"brief": "x" * 1000, "plan": GOOD["plan"]},                     # rambling
        {"plan": GOOD["plan"]},                                          # missing field
        "not json at all",
        ["a", "list"],
    ],
)
async def test_unusable_output_falls_back_to_rules(reply):
    async with ollama(reply) as http:
        assert await writer.write(http, "http://ollama", "m", {}, RECS) is None


@pytest.mark.parametrize("reply", [httpx.ConnectError("down"), httpx.ReadTimeout("slow")])
async def test_model_down_or_slow_falls_back(reply):
    async with ollama(reply) as http:
        assert await writer.write(http, "http://ollama", "m", {}, RECS) is None


async def test_server_error_falls_back():
    async with ollama(GOOD, status=500) as http:
        assert await writer.write(http, "http://ollama", "m", {}, RECS) is None


async def test_disabled_or_nothing_to_explain():
    async with ollama(GOOD) as http:
        assert await writer.write(http, "", "m", {}, RECS) is None
        assert await writer.write(http, "http://ollama", "m", {}, []) is None


def test_whitespace_is_tidied_and_steps_capped():
    out = writer.merge(RECS[:1], {"brief": "  Fix   it. ", "plan": [{"why": " Because\n it matters ", "steps": [f"s{i}" for i in range(9)]}]})
    brief, recs = out
    assert brief == "Fix it." and recs[0]["why"] == "Because it matters" and len(recs[0]["steps"]) == 4


async def test_ready_when_model_is_downloaded():
    def handler(request):
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:1.5b"}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert await writer.ready(http, "http://ollama", "qwen2.5:1.5b")
        assert not await writer.ready(http, "http://ollama", "llama3.2:3b")
        assert not await writer.ready(http, "", "qwen2.5:1.5b")


async def test_partial_output_keeps_the_good_parts():
    async with ollama({"brief": "Fix the key first.", "plan": GOOD["plan"][:1]}) as http:
        brief, recs = await writer.write(http, "http://ollama", "m", {}, RECS)
    assert brief == "Fix the key first."
    assert recs[0]["why"] == "Anyone can use your key."          # written by the model
    assert recs[1]["why"] == "rule why 2" and recs[1]["steps"] == []  # skipped: rule-based text kept
