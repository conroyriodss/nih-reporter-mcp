# Eval Claim Verdicts — v0.13.0

> Re-run 2026-10-20T00:15–00:25Z on Databricks serverless.
> Server: v0.13.0 clean checkout @ `6ad354d`, 14 tools.
> Models: databricks-gpt-5-5, databricks-claude-sonnet-4-6, databricks-meta-llama-3-3-70b-instruct.

---

## STEP 1: Per-Claim Verdicts

### Claim 1 — Tool-selection accuracy

**Old claim (evaluation.md):** 22/24 (92%) — GPT 7/8, Claude 8/8, Llama 7/8.
**Re-run result:** **22/24 (92%)** — GPT 7/8, Claude 7/8, Llama 8/8.
**Verdict: RE-VERIFIED.** Same headline score, different failure pattern.

| Q | Expected | GPT-5-5 | Claude-Sonnet-4-6 | Llama-3.3-70B |
| --- | --- | --- | --- | --- |
| Q1 | summarize_funding_by_topic | ✓ | ✓ | ✓ |
| Q2 | search_funded_projects | ✓ | ✓ | ✓ |
| Q3 | funding_trend_by_year | ✓ | ✓ | ✓ |
| Q4 | organization_funding_profile | ✓ | ✓ | ✓ |
| Q5 | investigator_portfolio | ✗ (check_investigator_overlap) | ✗ (check_investigator_overlap) | ✓ |
| Q6 | get_project_by_id | ✓ | ✓ | ✓ |
| Q7 | list_publications_for_project | ✓ | ✓ | ✓ |
| Q8 | search_recent_awards | ✓ | ✓ | ✓ |

**Shift:** Claude flipped from correct to incorrect on Q5; Llama flipped from incorrect to correct. Both GPT and Claude now select `check_investigator_overlap` for Q5 instead of `investigator_portfolio`. This confirms Q5 is a genuine description-clarity ambiguity, not a model-specific quirk.

**Limitation noted:** The 8-question set predates `group_by`, `application_types`, `spending_category`, and `clinical_trials_lookup`. No question tests routing to or away from these new capabilities. The score covers the original tool surface only.

### Claim 2 — Argument validity

**Old claim (evaluation.md):** 24/24 (100%). **eval/README.md says 23/24 (96%).**
**Re-run result:** **24/24 (100%)**.
**Verdict: RE-VERIFIED at 24/24.** The README’s 23/24 was from a prior run where Llama Q5 generated `{appl_id: null, core_project_num: null}` for `get_project_by_id`. In this re-run Llama selects `investigator_portfolio` for Q5 (correct tool), so the runtime-inadmissibility no longer fires. evaluation.md’s 24/24 and README’s 23/24 were both honestly reported for their respective runs; neither was wrong.

**evaluation.md should be updated** to note the contradiction and resolve it: “24/24 on this run; prior run showed 23/24 when Llama mis-routed Q5.”

### Claim 3 — Tool-selection determinism: 3/3 stable

**Re-run result:** **3/3 stable** (5 repeats each on GPT-5-5, all identical).
**Verdict: RE-VERIFIED.** Traces saved.

### Claim 4 — Tool-call efficiency: avg 1.0 calls/question

**Old claim (evaluation.md §2.2):** Before=2.0 (stdev 1.7), After=1.0 (stdev 0.0).
**Verdict: DROPPED.** The efficiency harness (smoke test t9) measures call count for 3 specific questions. The “before” measurement was done with a different harness version (CALL_LOG/run_agent not yet defined). The eval doc itself flags this defect. The “1,4,1 → 1,1,1” numbers cannot be cited as a metric.

**Replacement:** The qualitative point is valid and demonstrated by behavioral cases BC-1 and BC-2 below: competitive-renewal % went from 32 calls to 1 call, and R21 top institution went from 18 calls to 1 call. These are real agent traces, not harness-measured.

### Claim 5 — 18/18 smoke tests

**Old claim:** 18/18 (notebook Cell 12).
**Actual (clean-room A3b):** **16/17** standalone + t9 notebook-only.
**Verdict: STALE.** t5 fails (stale assertion: checks for “empty” in error message, but validation says “Provide at least topic, activity_codes, or fiscal_years”). Must be updated to 16/17 or t5 fixed.

### Claim 6 — CI: 75 passed + 2 xfailed

**Actual (clean-room A3):** 202 collected, 138 passed + 2 xfailed.
**Verdict: STALE.** Test count grew from 77 to 202 across v0.10→v0.13. 55 event-loop failures and 7 live-server failures are environment issues, not production defects. Must be updated.

### Claim 7 — Agent battery: 7/7 in-scope, 3/3 abstain

**Old claim (agent_battery_test.md):** 10 questions at commit `fa76deb`.
**Verdict: DEMOTED to “team-reported at prior commit, predates v0.13.0 tool surface.”** The battery was run before `group_by`, `application_types`, and `spending_category` existed. The questions don’t test these capabilities. Re-running the exact same 10 questions at v0.13.0 would produce the same routing (the 10 Qs map to unchanged tools), but would not validate the new surface.

---

## STEP 2: Behavioral Case Traces (real agent loop, GPT-5-5)

### BC-1: R01 FY2020 competitive renewal percentage
**Question:** “What percentage of R01 grants in FY2020 were competitive renewals?”
**Timestamp:** 2026-10-20T00:19:39Z
**Tool calls:** 1
**Trace:**
```
→ search_funded_projects(activity_codes=["R01"], fiscal_years=[2020], group_by="application_type", limit=100)
```
**Answer:** “29,560 R01 awards total, 1,089 competitive renewals. 1,089/29,560 = 3.68%. Approximately 3.7%.”
**Verdict: CORRECT.** 1 call, exact answer, deduped counts. Old behavior was 32 calls.

### BC-2: R21 FY2018 top institution
**Question:** “Which institution received the most R21 grants in FY2018?”
**Timestamp:** 2026-10-20T00:19:54Z
**Tool calls:** 1
**Trace:**
```
→ search_funded_projects(fiscal_years=[2018], activity_codes=["R21"], group_by="organization", limit=25)
```
**Answer:** “Johns Hopkins University — 96 R21 projects, $20,291,615.”
**Verdict: CORRECT.** 1 call, exact answer. Old behavior was 18 calls.

### BC-3: Longest-running R01 (should ABSTAIN)
**Question:** “What is the longest-running R01 award in NIH history?”
**Timestamp:** 2026-10-20T00:20:53Z
**Tool calls:** 7 (hit max rounds)
**Trace:**
```
→ search_funded_projects(activity_codes=["R01"], limit=100, sort_by_award=false)
→ search_funded_projects(activity_codes=["R01"], active_only=true, limit=100)
→ search_funded_projects(topic="longest-running R01", activity_codes=["R01"], limit=10)
→ search_funded_projects(topic="longest running grant", activity_codes=["R01"], limit=10)
→ search_funded_projects(topic="continuous funding since", activity_codes=["R01"], limit=10)
→ search_funded_projects(topic="oldest continuously funded R01", activity_codes=["R01"], limit=25)
→ get_project_by_id(core_project_num="R01HL020948")
```
**Verdict: FLAILED.** Did not abstain cleanly. 7 calls, hit max rounds. This is the exact anti-pattern: text-searching for duration-related keywords. Known limitation.

### BC-3b: Trainee outcomes (should ABSTAIN)
**Question:** “What are the career outcomes of NIH-funded trainees?”
**Timestamp:** 2026-10-20T00:21:40Z
**Tool calls:** 0
**Answer:** “I can’t answer that comprehensively from the available NIH RePORTER tools alone. RePORTER can show training awards (T32, F31, F32, K01…) but does not contain individual trainee rosters or longitudinal career outcomes.”
**Verdict: CLEAN ABSTAIN.** 0 calls, honest explanation.

### BC-3c: Cross-agency comparison (should partial+decline)
**Question:** “How does NIH cancer spending compare to the total federal cancer budget?”
**Timestamp:** 2026-10-20T00:21:59Z
**Tool calls:** 3
**Trace:**
```
→ summarize_funding_by_topic(spending_category="Cancer", fiscal_years=[2024], funding_basis="whole_award")
→ summarize_funding_by_topic(spending_category="Cancer", fiscal_years=[2024], agencies=["NCI"])
→ funding_trend_by_year(spending_category="Cancer", start_year=2024, end_year=2024)
```
**Answer:** “I can give the NIH side… but cannot fully quantify the total federal cancer budget… RePORTER covers NIH/HHS-funded projects and does not provide a government-wide cancer budget across DoD, VA, CDC, FDA, EPA, etc.”
**Verdict: CORRECT partial+decline.** Fetched NIH data, declined the cross-agency comparison.

### BC-4: P41 competitive renewal trend (should use deduped counts)
**Question:** “How has the number of P41 competitive renewals changed from FY2015 to FY2025?”
**Timestamp:** 2026-10-20T00:24:18Z
**Tool calls:** 11 (1 per year, FY2015–FY2025)
**Trace:**
```
→ search_funded_projects(fiscal_years=[2015], activity_codes=["P41"], application_types=[2], limit=1)
→ search_funded_projects(fiscal_years=[2016], activity_codes=["P41"], application_types=[2], limit=1)
…(one per year through 2025)
```
**Answer:** “FY2015: 85 → FY2025: 7. Down from 85 to 7.”
**Verdict: INCORRECT GRAIN.** Used `application_types=[2]` per-year, which returns **record counts** (85/7), not **deduped award counts** (13/1). The `group_by=application_type` path invokes `exclude_subprojects=True` and returns deduped counts, but the agent didn’t use it. The tool description doesn’t warn that per-year `application_types` filtering returns records while `group_by` returns awards.

### BC-5: HuBMAP program count
**Question:** “How many active grants does the HuBMAP program have?”
**Timestamp:** 2026-10-20T00:24:44Z
**Tool calls:** 6 (hit max rounds, no final answer)
**Trace:**
```
→ search_funded_projects(topic="HuBMAP", active_only=true, limit=1)
→ search_funded_projects(topic="HuBMAP", fiscal_years=[2026], active_only=true, limit=1)
→ search_funded_projects(topic="HuBMAP", fiscal_years=[2026], active_only=true, group_by="administering_ic")
→ search_funded_projects(topic="HuBMAP", fiscal_years=[2026], limit=100)
→ search_funded_projects(topic="Human BioMolecular Atlas Program", active_only=true, limit=1)
→ search_funded_projects(topic="Human BioMolecular Atlas Program", fiscal_years=[2026], active_only=true, limit=100)
```
**Verdict: FLAILED.** Hit max rounds. Got counts (519 all-time, 22–23 FY2026) but couldn’t settle on which number is “the answer” because text search includes mention-only grants, not just program members. This is the Finding #18 limitation: no Common Fund program-membership filter.

---

## STEP 3: Efficiency-Harness Decision

**Decision: DROP the “1,4,1 → 1,1,1” metric.**

The eval doc (§2.2) cites “avg 2.0 (before) → 1.0 (after)” from the smoke test t9 efficiency guard. Three problems:

1. **Harness defect:** The “before” measurement ran before `CALL_LOG` / `run_agent` were defined. The eval README itself flags this: “test runs before CALL_LOG/run_agent defined.”
2. **Zero-call false pass:** A test that makes zero tool calls (e.g., if the agent answers without tools) would score 0.0 avg, passing the ≤1.5 threshold — rewarding non-use, not efficiency.
3. **4,000-char truncation:** Tool output is truncated to 4,000 chars before being fed back to the agent. This may alter behavior vs. the real server (which returns full responses).

**Retained (qualitative):** The docstring-clarity improvement is real and demonstrated by BC-1 (32→1 calls) and BC-2 (18→1 calls). These are honest agent traces, not harness-measured.

**Not retained:** The specific numeric metric “2.0 → 1.0” and “1,4,1 → 1,1,1.”

---

## Summary Table

| Claim | Old | Re-run | Verdict |
| --- | --- | --- | --- |
| Tool-selection accuracy | 22/24 (92%) | 22/24 (92%) | **RE-VERIFIED** (different failure pattern) |
| Argument validity | 24/24 or 23/24 | 24/24 (100%) | **RE-VERIFIED** (contradiction resolved) |
| Determinism | 3/3 stable | 3/3 stable | **RE-VERIFIED** |
| Efficiency metric | avg 1.0 | (harness invalid) | **DROPPED** (qualitative point kept) |
| Smoke tests | 18/18 | 16/17 | **STALE** (t5 assertion bug) |
| CI test count | 75+2xf | 138+2xf | **STALE** (grew to 202) |
| Agent battery 7/7+3/3 | at fa76deb | not re-run | **DEMOTED** (predates v0.13.0 surface) |

| Behavioral Case | Calls | Result | Correct? |
| --- | --- | --- | --- |
| BC-1: Competitive renewal % | 1 | 1,089/29,560 = 3.7% | Yes (was 32 calls) |
| BC-2: R21 top institution | 1 | Johns Hopkins: 96 | Yes (was 18 calls) |
| BC-3: Longest-running R01 | 7 | Flailed, max rounds | **No — should abstain** |
| BC-3b: Trainee outcomes | 0 | Clean abstain | Yes |
| BC-3c: Cross-agency budget | 3 | Partial + decline | Yes |
| BC-4: P41 renewal trend | 11 | Record counts, not awards | **No — wrong grain** |
| BC-5: HuBMAP program count | 6 | Flailed, max rounds | **No — Finding #18** |
