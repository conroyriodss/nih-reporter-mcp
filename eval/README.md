# Evaluation

The hackathon template intentionally ships no eval harness, leaving it to each team to demonstrate server quality through testing. This is ours.

## What's tested, and why each category matters

**Functional smoke tests** (`eval/smoke_tests.py` standalone or Cell 12 of the companion notebook) — 9 assertions against a live server instance, split into two kinds, deliberately distinguished:

- *Hard invariants*: behaviors that should never change regardless of live data drift (the 10,000-record ceiling triggers `complete=False`, not silent truncation; a SQL-injection-style input produces a clean error, not a leaked traceback; two tools querying the same criteria agree on totals).
- *Drift-tolerant assertions*: live NIH data changes as new awards post, so exact-equality checks against specific dollar figures would eventually fail for reasons unrelated to a real regression. These use a percentage tolerance band instead (see `within_tolerance()` helper).

**Tool-selection accuracy** — a battery of 8 natural-language questions, each with one clearly-expected tool, run against a live Databricks-hosted LLM with all 8 tools available via function-calling. Scores whether the model picks the correct tool, independent of whether its final written answer is well-phrased. Result as of last run: 100% (8/8).

**Tool-call efficiency regression guard** — a specific, previously-observed failure mode (an LLM agent re-querying near-identical phrasings believing minor rewording changes results) is now a permanent assertion: the same question run 3 times must average ≤1.5 tool calls. See `docs/findings.md` #8 for the full before/after measurement that motivated this.

**Adversarial / edge cases** — qualitative transcripts (not pass/fail assertions) covering: ambiguous tool selection, LLM-generated over-wide ranges, institution-name ambiguity resolved autonomously by the agent, a nonexistent spending category, and informally-phrased queries. Reviewed manually; see `docs/findings.md` for specific outcomes worth noting.

## Running the suite

**Standalone** (t1–t8, no LLM required):

```bash
uv run python main.py &
sleep 5
uv run python eval/smoke_tests.py
```

**Full suite including t9** (requires Databricks Foundation Model API access): use the companion Databricks notebook (`notebook-merged`). Cells 1–10 copy the project source, start the MCP server, and confirm registration. Cell 12 executes all 9 assertions including the LLM agent-efficiency regression guard.

For the LLM-driven tool-selection and efficiency tests, see `notebook-merged` sections 10–13 — these run interactively since they need Databricks model endpoints.

## Known gaps in current coverage

- No automated test exercises `get_publication_details` against a PMID known to be withdrawn or embargoed (manually verified the `not_found` path works, not yet scripted).
- Tool-selection accuracy (100%) was measured on 8 questions chosen to map cleanly to one tool each; genuinely ambiguous questions (where two tools could reasonably apply) are covered qualitatively in the adversarial transcripts but not scored numerically.
- All live-data assertions depend on NIH RePORTER's API being reachable and consistent at test time; no mock/fixture-based fallback exists if the upstream API is down during CI.
