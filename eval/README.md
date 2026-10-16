# Evaluation

The hackathon template intentionally ships no eval harness, leaving it to each team to demonstrate server quality through testing. This is ours.

## What's tested, and why each category matters

**Functional smoke tests** (`eval/smoke_tests.py` standalone or Cell 12 of the companion notebook) — 18 assertions against a live server instance. Three run modes:

- **Quick mode** (`--quick`, \~8s): 5 single-call tests (t3, t5, t6, t10, t13) — no full pagination. Intended for fast iteration during development.
- **Full parallel mode** (default, \~60–90s): all 17 standalone tests (t1–t8, t10–t18) run concurrently via `asyncio.gather`, with 90s per-test timeouts. Wall-clock time is bounded by the slowest concurrent test.
- **Full sequential mode** (`--sequential`, \~100s): same 17 tests run one at a time. Useful for debugging or avoiding API rate-limit pressure.

Tests are split into two kinds, deliberately distinguished:

- *Hard invariants*: behaviors that should never change regardless of live data drift (the 10,000-record retrieval cap triggers `complete=False`, not silent truncation; a SQL-injection-style input produces a clean error, not a leaked traceback; two tools querying the same criteria agree on totals).
- *Drift-tolerant assertions*: live NIH data changes as new awards post, so exact-equality checks against specific dollar figures would eventually fail for reasons unrelated to a real regression. These use structural checks instead (nonzero values, correct ordering, count reconciliation).

**Tool-selection accuracy** — a battery of 8 natural-language questions (`TOOL_SELECTION_CASES`), each with one clearly-expected tool, run against live Databricks-hosted LLMs with all 13 tools available via function-calling. Scores whether the model picks the correct first tool, independent of whether its final written answer is well-phrased.

**Multi-model eval (§14a–c, notebook-only):** The same 8 cases are run across 3 models from different families (GPT, Claude, Llama) to verify tool descriptions are agent-agnostic. This requires live Databricks serving endpoints and runs only in the notebook — it is not part of the pytest suite. See `docs/findings.md` #14 for results and analysis. As of 2026-10-16: 22/24 trials correct (92%), with 7/8 cases unanimous across all 3 models.

**Tool-selection determinism (§14d, notebook-only):** 3 representative questions each run 5 times on GPT-5-5. Measures whether tool SELECTION is stable across repeats (distinct from the call-count efficiency guard in §13). As of 2026-10-16: 3/3 stable, zero flickers. See `docs/findings.md` #15.

**Argument validity rate (§14e, notebook-only):** For each of the 8 cases × 3 models, validates that model-generated tool arguments conform to the tool’s input schema (correct param names, correct types, required params present). This is the named benchmark metric. As of 2026-10-16: 24/24 (100%) across all models. See `docs/findings.md` #16.

**Tool-call efficiency regression guard** — a specific, previously-observed failure mode (an LLM agent re-querying near-identical phrasings believing minor rewording changes results) is now a permanent assertion: the same question run 3 times must average ≤1.5 tool calls. See `docs/findings.md` #8 for the full before/after measurement that motivated this.

**Adversarial / edge cases** — qualitative transcripts (not pass/fail assertions) covering: ambiguous tool selection, LLM-generated over-wide ranges, institution-name ambiguity resolved autonomously by the agent, a nonexistent spending category, and informally-phrased queries. Reviewed manually; see `docs/findings.md` for specific outcomes worth noting.

## Running the suite

**Quick** (5 tests, ~15s, no LLM required):

```bash
uv run python main.py &
sleep 5
uv run python eval/smoke_tests.py --quick
```

**Full parallel** (17 tests, \~60–90s, no LLM required):

```bash
uv run python eval/smoke_tests.py
```

**Full sequential** (17 tests, \~100s, no LLM required):

```bash
uv run python eval/smoke_tests.py --sequential
```

**Full suite including t9** (requires Databricks Foundation Model API access): use the companion Databricks notebook (`notebook-merged`). Cells 1–10 copy the project source, start the MCP server, and confirm registration. Cell 12 executes all 18 assertions including the LLM agent-efficiency regression guard.

For the LLM-driven tool-selection and efficiency tests, see `notebook-merged` sections 10–13 — these run interactively since they need Databricks model endpoints.

## Correctness against independent ground truth

**Funding arithmetic tests** (`tests/test_correctness.py`, 6 tests) — proves the v0.8.0 counting fix produces correct funding totals by comparing tool output against independently-fetched, hand-computed reference values. Every assertion uses the `whole_award` basis (the corrected default), not the inflated `all_records` figures. Requires a running MCP server.

```bash
# Via pytest:
PYTHONPATH=src pytest tests/test_correctness.py -v

# Standalone:
MCP_URL=http://localhost:8000/mcp python tests/test_correctness.py
```

The six tests:

1. **Ground-truth exact match** — a small cohort ("CRISPR sickle cell" FY2024, 38 records) was independently fetched via direct API call, and the whole_award total hand-computed by applying the same rules the code enforces (exclude subprojects, dedupe appl_ids, exclude null amounts). The tool's output must match **to the dollar** ($19,790,134). Fixture data in `tests/fixtures/`.
2. **Double-counting proof** — U19AG068753 FY2024 (a confirmed multi-component grant) has 1 parent ($5.13M) + 7 subprojects (sum $5.13M). The test verifies `all_records` ($10.26M) > `whole_award` ($5.13M), and the delta **exactly** equals the summed subproject amounts — proving the fix removes real double-counted dollars.
3. **Provenance reproducibility** — calls `export_evidence_bundle`, takes its `source_record_ids`, re-fetches those records via direct API, applies whole_award rules independently, and confirms the re-computed total reproduces the tool's reported total exactly.
4. **Missing-amount honesty** — verifies that records with null `award_amount` are tracked (`records_with_missing_amount > 0`), excluded from the total (not zeroed to $0), and the result is not claimed as "exact".
5. **Cross-tool basis consistency** — for a subproject-bearing topic, `whole_award` is strictly less than `all_records` with nonzero `subproject_excluded_count`.
6. **Overlap completeness flag** — verifies `check_investigator_overlap` returns `complete` and `total_matching` fields, and that `complete=True` when all matching records are retrieved.

**Synthetic oracle tests** (`tests/test_counting.py`, 20 pass + 2 xfail) — unit tests against synthetic data with known oracle values, verifying `aggregate_funding()` directly without the MCP server. No network required.

**Before/after quantification** (see `docs/findings.md` #13):

| Topic (FY2023) | Naive sum | Corrected | Overstatement (delta/corrected) |
|---|---:|---:|---:|
| CRISPR gene editing | $921.5M | $837.0M | 10.1% |
| Alzheimer's disease | $4,685.2M | $4,020.8M | 16.5% |

## Known gaps in current coverage

- No automated test exercises `get_publication_details` against a PMID known to be withdrawn or embargoed (manually verified the `not_found` path works, not yet scripted).
- Tool-selection accuracy was measured on 8 questions chosen to map cleanly to one tool each; genuinely ambiguous questions (where two tools could reasonably apply) are covered qualitatively in the adversarial transcripts but not scored numerically. The multi-model eval (§14) surfaced one such ambiguity: Q5 ("What grants does Francis Collins currently hold?") — GPT-5-5 chose `check_investigator_overlap` instead of `investigator_portfolio`, exposing a description-clarity opportunity between two tools with overlapping input schemas.
- All live-data assertions depend on NIH RePORTER's API being reachable and consistent at test time; no mock/fixture-based fallback exists if the upstream API is down during CI.
