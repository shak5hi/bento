# src/ai/

**Owner: Lavanya**

This folder contains the AI layer: prompt construction and Claude Haiku calls.

## Files

| File | Purpose |
|------|---------|
| `promptTemplate.js` | Builds the prompt string from project name, scores, and snapshot signals. Edit this to tune Pickle's tone and focus. |
| `generateInsight.js` | Calls Claude Haiku, checks for duplicate today's insight, and caches the result in `ai_insights`. |

## Critical rule: NO live AI calls

**`generateInsight` is called by the scheduler, not by any API route.**

The flow is:
```
cron (daily 2am UTC)
  → generateInsight(projectId)
    → buildInsightPrompt(...)
    → Claude Haiku API
    → INSERT into ai_insights
```

API routes read the cached insight from `ai_insights` — they never call this function directly.
This keeps AI costs near zero (1 call/project/day).

## Model choice

We use `claude-haiku-4-5` — Anthropic's cheapest and fastest model.
Max tokens is capped at 150 (1-2 sentences).

## Tuning Pickle's output

Edit `promptTemplate.js`. The prompt tells Claude to:
- Name the biggest risk/opportunity
- Suggest one actionable next step
- Write in plain prose (no bullet points, no score repetition)

## Cost estimate

100 projects × 1 call/day × ~300 tokens = ~30,000 tokens/day ≈ **$0.002/day** with Haiku.
