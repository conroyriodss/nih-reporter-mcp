# NIH RePORTER MCP Server — Evaluation

**Project:** NIH RePORTER MCP Server  
**Team:** Rich Conroy, NIH/OD/ODSS  
**Hackathon:** GSA MCP Server and AI Agent Government Hackathon  
**Submission freeze:** `v0.14.9`  
**Evaluation revision:** October 22, 2026  
**Repository:** https://github.com/conroyriodss/nih-reporter-mcp  
**Run history:** [RUN_MANIFEST.md](demonstration_fixture/RUN_MANIFEST.md) and [EVAL_VERDICTS.md](demonstration_fixture/EVAL_VERDICTS.md)

> **What this submission demonstrates:** a funding total can be traced to a defined query, explicit record-counting rules, and an inspectable set of source records. The supplied CRISPR sickle cell fixture reconciles to **$19,790,134**. This verifies that snapshot's arithmetic; it does not establish complete NIH investment in a topic, causal research impact, or correctness of every tool answer.

> **Demo access:** The public repository and frozen fixtures are the primary reproducible artifacts. The hosted Databricks “Ask” experience additionally requires workspace access and a functioning, authorized model endpoint; its current deployment status was not verified for this revision. Historical notebook outputs demonstrate their recorded runs, not execution of subsequently edited cells.

> **Required sections:** Testing methodology is section 3 (with the reproduction procedure in section 6). Performance metrics are section 3.5. Security considerations are section 9. Lessons learned and recommendations are section 10.

> **What v0.14.9 changes:** the hosted Ask loop now carries four interpretation boundaries itself: excluded orphan subprojects, incomplete retrieval, keyword-versus-RCDC scope, and unsupported questions. The rules are in the system message the model receives, and a check on the final answer adds any boundary the model left out, or withholds an answer to an unsupported question (section 3.6). The server instructions, tool descriptions and prompts no longer promise an exact or congressionally mandated total, and `/debug` no longer returns token details. Aggregation logic, upstream requests and tool outputs are unchanged.

## 1. Evidence standard and review scope

This revision reconciles the supplied documentation and fixture files with directly inspected source files at `v0.14.9`. It retains historical results with their actual run identities instead of relabeling earlier executions as runs at the submission tag.

### 1.1 Four evidence tiers

| Tier | Meaning in this document |
|---|---|
| **Verified** | Independently recomputed from the supplied artifacts, or confirmed by direct inspection of the cited source. Each claim states whether the method was artifact reconciliation, schema validation, or source inspection. Source inspection does not establish a passing execution. |
| **Repository-reported** | A result documented in the repository, with a stated method or run reference, whose underlying execution was not independently replayed for this revision. |
| **Team-reported** | A statement without accessible supporting execution evidence sufficient for the stronger tiers. |
| **Planned** | A proposed feature, measurement, or test; no completed result is claimed. |

Execution status is separate: **PASS**, **FAIL**, **NOT RUN**, or **BLOCKED**. “Re-verified” in a historical run log describes that run; it is not a fifth evidence tier. Collecting a test, importing a module, or receiving a response without an exception does not verify the substantive result.

### 1.2 What was checked for this revision

- **Verified — artifact reconciliation:** SHA-256 checks of both raw snapshots; independent decimal sums; row-by-row ledger decisions and amounts; the primary fixture's stored total, counts, query criteria, and complete contributing-ID list.
- **Verified — schema validation:** the supplied `tool_output.json`'s `summary` and `provenance` validate against the `v0.14.9` `FundingSummary` and `Provenance` classes, loaded in isolation with Pydantic 2.14.0. This is not a server or transport execution.
- **Verified — source inspection:** aggregation, evidence export, Pydantic models, input/cache handling, server startup and diagnostic routes, the CI workflow, and the cited test implementations.
- **NOT RUN for this revision:** the project's CI suite, live MCP/API suites, Databricks model evaluations, deployed app, and GitHub Actions execution. Their historical pass figures remain repository-reported.

The verified fixture checks apply to the **supplied artifact bytes**. They do not certify that an independently downloaded release asset contains identical bytes. Tag identity, release contents, and successful runtime inventory remain checks for the evaluator.

### 1.3 Claim register

| Claim | Result retained | Evidence and scope |
|---|---|---|
| Submission inventory | **14 tools, 9 prompts, 3 resources** | Repository-reported freeze inventory. Source inspection confirms that `/version` reads the live registries; the runtime inventory recipe below verifies the actual counts. |
| Model-free CI | **167 passed + 2 xfailed** | Repository-reported at `v0.14.9`. The exact CI selectors and two Python versions are verified in the workflow. Not independently rerun here. |
| Ask-loop boundaries | **4 boundaries carried by the agent loop; 12 model-free tests** | Repository-reported: `tests/test_agent_boundaries.py` drives the real Ask loop with a scripted model that omits every caveat (section 3.6). It shows the loop's check works on those cases, not that a live model's answers are correct. |
| Standalone smoke | **17/17 passed** | Repository-reported at `v0.14.0`. The 17 cases are t1–t8 and t10–t18; t9 is excluded. |
| Live correctness | **8 tests; reported 8/8 passed** | Eight test functions verified in source; historical passing execution is repository-reported. They do not provide eight independent dollar-level reconciliations. |
| Frozen primary total | **$19,790,134; 38 raw / 37 contributing / 1 excluded subproject** | Verified by offline reconciliation of the supplied snapshot, ledger, and stored output. |
| True parent/child double-counting fixture | **$10,260,946 all_records / $5,130,473 whole_award** | Verified offline for `U19AG068753`, FY2024: one parent and seven children, with the parent present. |
| First-tool selection | **22/24 = 91.7%, rounded to 92%** | Repository-reported, eight questions across three models; run at `v0.13.0` on October 20. Not a full-answer accuracy score. |
| Argument validity | **24/24** | Repository-reported for that model run. Raw arguments and validation traces are needed for independent confirmation. |
| Repeated tool selection | **3/3 questions stable across five repeats each** | Repository-reported for GPT-5-5. A small observed consistency result, not a general determinism guarantee. |
| Historical live basis differences | **CRISPR 10.1%; Alzheimer's 16.5%** | Inputs are repository-reported; percentages are reproducible arithmetic on those inputs. These are not new live measurements. |

## 2. Funding correctness: demonstrated result and boundaries

### 2.1 Exact cohort definition

The primary fixture uses the following RePORTER criteria:

```json
{
  "advanced_text_search": {
    "operator": "and",
    "search_field": "all",
    "search_text": "CRISPR sickle cell"
  },
  "fiscal_years": [2024]
}
```

Source: [query.json](demonstration_fixture/query.json). The raw snapshot records its request payload and upstream metadata.

**Text-search comparisons must preserve `operator="and"` and `search_field="all"`.** A different phrase, operator, field, agency scope, fiscal-year filter, or funding basis defines a different result. A numerical difference is not evidence of a server error until those criteria agree.

### 2.2 Whole-award algorithm

Verified by inspection of [utils.py](https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.9/src/nih_reporter_mcp/utils.py), `aggregate_funding`:

1. Deduplicate non-null `appl_id` values in retrieval order. The first occurrence wins; later occurrences with conflicting amount, fiscal year, or subproject ID are flagged.
2. For `whole_award`, exclude every remaining record whose `subproject_id` is **non-null**. This is not an activity-code-prefix rule.
3. Track parent presence by **core project number and fiscal year**. A parent from another fiscal year does not resolve an excluded child's orphan status.
4. Exclude null `award_amount` values from the dollar sum and report their count. A null amount is not a zero; an actual zero remains a valid value.
5. Sum the remaining amounts. Preserve distinct application IDs even when they share a core project number.

`all_records` still deduplicates application IDs and excludes null amounts, but retains subprojects. It is a comparison basis, not the preferred investment total.

The unit is **contributing application records**, not unique long-running grant families. Separate years, continuations, and supplements must not be collapsed solely because their core project number matches. Conversely, a project-period duration must not be multiplied by an annual award amount to invent lifetime funding.

**Unresolved edge cases remain visible:** first-wins conflicts need review; missing IDs cannot be deduplicated by ID; and missing core identifiers can prevent orphan detection. These are reasons to inspect provenance rather than promise universal correctness.

### 2.3 Independently reconciled primary fixture

| Check | Verified result |
|---|---|
| Raw retrieval timestamp | October 15, 2026, 20:31:43 UTC |
| Stored tool-output timestamp | October 18, 2026, 19:07:59 UTC |
| Raw rows / contributing rows | 38 / 37 |
| Excluded subprojects | 1 |
| Duplicate application IDs / missing contributing amounts | 0 / 0 |
| Whole-award sum | **$19,790,134.00** |
| Distinct core project numbers among contributors | 35 |
| Contributing IDs in stored provenance | All 37; no 500-ID truncation |
| Raw SHA-256 | `ff178702ec35720c88b7f85900db60d6fc9380e000fbf9aaacda20617a7f789d` |

The excluded record is `appl_id=10992993`, subproject `9946` of core project `P50HD096723` (FY2024), amount **$472,999**. It is an **orphan**: the keyword matched this child but not its parent. The parent P50 is a male-infertility genetics center whose own abstract does not match “CRISPR sickle cell”; only this subproject (“Project III”, sickle-cell iPSC work) matched. The cohort therefore contains **one orphan subproject, not the center**: RePORTER lists five FY2024 subprojects for the center totaling $1,711,713, and only this one ($472,999) is in the cohort. *(Team-reported: confirmed against the RePORTER record for 2P50HD096723-06. The frozen snapshot stores five fields per record and retains no titles or abstracts.)*

This exclusion is **not double-counting removal**. Excluding an orphan removes real topical investment, so whole_award can **understate** a keyword cohort's investment. This example verifies a correctly disclosed exclusion; **it does not demonstrate that the excluded amount was duplicated elsewhere in this cohort**. The double-counting proof is the separate U19AG068753 fixture in section 2.4.

The stored response correctly has `complete=true` and an orphan warning in `note`. These statements are compatible: all matching records were retrieved, but the cohort does not contain every award-family amount relevant to the topic.

The raw projection supports the funding reconciliation. It does **not** contain organization or administering-IC fields, so it cannot independently substantiate the stored `distinct_organizations=29` or `distinct_administering_ics=10`. Inspection of `evidence_bundle.py` also shows those two counts are calculated over retrieved records, including records excluded from the dollar sum.

The manifest reports a live comparison on October 19 at `v0.13.0`. That is historical, repository-reported evidence; the October 15 snapshot is not relabeled as a live retrieval at `v0.14.9`.

### 2.4 Separate double-counting proof

The [U19AG068753 FY2024 fixture](demonstration_fixture_double_counting/README.md) contains one parent and seven subprojects:

| Quantity | Verified amount |
|---|---:|
| Parent amount | $5,130,473 |
| Sum of child amounts | $5,130,473 |
| All-record sum | $10,260,946 |
| Whole-award sum | $5,130,473 |

There are no orphan children in this fixture. It directly demonstrates the parent-plus-children double-counting mechanism. It does not establish that every excluded subproject in every keyword cohort is already represented by a parent in that cohort.

### 2.5 What “inspectable” means at this release

[Evidence export](https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.9/src/nih_reporter_mcp/tools/evidence_bundle.py) returns an `EvidenceBundle` with `label`, `summary`, `provenance`, and `reproduction_note`. The model definitions are in [models.py](https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.9/src/nih_reporter_mcp/models.py).

**source_record_ids lists up to 500 of N contributing IDs (capped for payload size); records_aggregated gives the true count.**

Consequences:

- The small frozen fixture has a complete contributing-ID list. A larger bundle is **not** a complete record-level export.
- Query criteria plus a live re-fetch are not an immutable historical snapshot. RePORTER data can change.
- The export records criteria but not the entire request payload, page responses, or retrieval ordering. The implementation sorts by award amount descending; ordering can matter when conflicting duplicates use first-wins resolution.
- `retrieved_at` is assigned when the bundle is constructed. The shared HTTP client may return cached data, so this timestamp is not reliable evidence of a fresh upstream fetch.
- Missing application IDs can contribute an amount without appearing in `source_record_ids`. Do not infer complete ID coverage merely because the 500-ID cap was not reached.
- `AggResult.is_exact` is internal. The public `FundingSummary` exposes `complete`, counts, provenance, and `note`; it has no `is_exact` field.
- The production “Total is exact” note is bounded by the selected query and implemented diagnostics. It is not a claim of comprehensive topic funding or causal attribution.

For full historical reconstruction, preserve raw pages, exact request payloads and ordering, the full decision ledger, source identity, and hashes. That is achieved for the supplied small fixtures, not automatically for every exported bundle.

### 2.6 Retrieval completeness is not funding completeness

Use this boundary with any consequential funding answer:

> “This total sums the non-null amounts on the retrieved application records under the stated filters and counting basis. Retrieval completeness means the matching records were fetched; it does not establish complete NIH investment in the topic. Keyword coverage, excluded orphan subprojects, missing amounts, conflicting records, agency scope, and source updates can limit interpretation.”

RCDC-filtered results and free-text results define different cohorts. An aggregation over RePORTER's RCDC-tagged projects is not automatically identical to NIH's separately published official RCDC spending total. Multi-category totals also cannot simply be added without checking overlap.

## 3. Testing methodology: test evidence and what the tests actually establish

Testing is layered. Each claim is checked by the least expensive method that can establish it, and each layer reports its own result rather than feeding a combined score:

- **Offline arithmetic reconciliation** (sections 2.3, 2.4 and 6.3): frozen raw records, a SHA-256 check, an independent Decimal sum and a row-by-row decision ledger. No network access or running server is needed.
- **Model-free CI** (section 3.1): the selected pytest suites on Python 3.11 and 3.12, including mocked upstream failures. No live API or model endpoint is called.
- **Agent-boundary contract** (section 3.6): the real Ask loop with a scripted model and the real MCP server on frozen or synthetic records. It checks the answer the user sees, not the model's choice of tool.
- **Live checks** (sections 3.2 and 3.3): the standalone smoke suite and eight correctness tests against the public upstream APIs. Their results depend on upstream data at run time.
- **Agent evaluation** (sections 3.4 and 3.5): model endpoints choose tools and arguments. These runs are gated separately and never counted in CI totals.
- **Release identity** (section 6.1 and the notebook's identity cell): the evaluated commit must be the one the tag resolves to, and its parent must match RUN_MANIFEST section 1.

Each result carries an evidence tier from section 1.1 and a separate execution status. A test that is collected, imported, or run without an exception is not counted as verifying its substantive claim.

### 3.1 Model-free CI

**Repository-reported result at `v0.14.9`: 167 passed + 2 xfailed.**

The [CI workflow](https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.9/.github/workflows/ci.yml) selects the following suites on **Python 3.11 and 3.12**:

| Selector | Reported result | Scope |
|---|---:|---|
| `tests/test_counting.py` | 67 passed + 2 xfailed | Aggregation, counting, query/pagination and faceting-related checks; strength varies by test. |
| `tests/test_security.py` | 24 passed | Input and outbound-client validation checks. |
| `tests/test_prompt_contracts.py` | 29 passed | Prompt references and parameter contracts. |
| `tests/test_clinical_trials.py` | 23 passed | ClinicalTrials.gov parsing, evidence-class and boundary behavior. |
| `tests/test_version_contract.py` | 1 passed | `/version` counts equal the actual nonempty MCP registries. |
| `tests/test_agent_boundaries.py` | 12 passed | The Ask loop's final answer carries the four interpretation boundaries (section 3.6). |
| `tests/test_robustness.py::TestPartC_MockedUpstreamFailures` | 11 passed | Mocked upstream errors and response handling. |
| **Total** | **167 passed + 2 xfailed** | Part C is included once. |

The version-contract test is necessary to reconcile the total: omitting it yields 166 passes. It checks registry equality, not a hardcoded release inventory; use the release-inventory check in section 6 for 14/9/3.

The two expected failures in [test_counting.py](https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.9/tests/test_counting.py) identify **IC-level attribution not yet implemented** and **publication-to-funding-year joining not supported**. They are not both established upstream-service defects.

**Test count is not coverage quality.** In that same file, `TestExcludeSubprojectsFaceting.test_r_series_not_affected` and `test_p_series_significantly_affected` contain `pass` without assertions. Other checks assert locally written constants or reimplement a calculation instead of invoking production behavior, including parts of the year-clamp and P41 examples. Their passing status is not independent verification of the claimed API behavior. Strengthening these checks is planned; this document does not subtract them from the actual reported pytest total.

A blanket `pytest tests/` invocation is **not** the offline CI command: it also selects live-server-dependent tests. Historical full-suite failures must not be hidden by substituting the selected-CI result.

### 3.2 Standalone live smoke

**Repository-reported: 17/17 at `v0.14.0`.** Source: [smoke_tests.py](https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.9/eval/smoke_tests.py) and the run history.

The standalone suite contains **t1–t8 and t10–t18**. The former t9 efficiency metric is excluded, not a missing eighteenth pass.

| Cases | What the assertions establish—and do not establish |
|---|---|
| t1 | Asserts the CRISPR FY2023 matching count and retrieval completeness. It prints the dollar amount; it does not assert that amount equals $836,981,580. |
| t2–t4 | Exercise the retrieval ceiling, an exact-name organization query/count, and a category-versus-text comparison. They do not independently reconcile every result or prove a specific printed category total. |
| t5–t6 | Check invalid-input and upstream rejection handling. t6's expected 403 depends on upstream behavior; it is not proof of general injection resistance. |
| t7–t8 | Check basis/count relationships and returned year totals. The trend check does not establish that the requested year set is complete. |
| t10–t13 | Check overlap response structure, an exclusion effect, section-count bounds, and recent-result limits/URLs. These are not complete portfolio or workload audits; t13 does not assert date ordering. |
| t14–t15 | Check provenance and evidence-bundle structure. Nonempty IDs and a reproduction note do not establish full replay. |
| t16–t17 | Check MedlinePlus match/no-match handling. |
| t18 | Checks repeated whole-award equality and a difference between bases. Printed timing is not a controlled latency benchmark or instrumented proof of a cache hit. |

### 3.3 Eight live-correctness tests

Source: [test_correctness.py](https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.9/tests/test_correctness.py). Use **pytest on the file**: its standalone `main()` runner invokes only six tests.

| Test purpose | Actual method and limit |
|---|---|
| Ground-truth exact match | Compares the live small-cohort response with frozen count, total, and exclusion expectations. Future source drift can break the comparison without changing the frozen arithmetic. |
| Double-counting arithmetic | Compares parent-only arithmetic with the aggregation result on a bounded raw response; checks that including children raises the sum. It is not a general fully paginated independent oracle. |
| Provenance replay | Re-fetches IDs for the small evidence bundle and independently sums them. Does not test reconstructing a capped >500-ID export. |
| Missing-amount honesty | If the live cohort has no missing amounts, the function warns and returns; pytest can report PASS without exercising the target condition. Record this as condition-not-observed, not demonstrated missing-data coverage. |
| Funding-basis consistency | Calls one funding tool with two bases and checks their relationship. This is not an independent reconciliation across multiple tools. |
| Overlap completeness flag | Checks field types and count relationships. Does not establish that every relevant investigator award exists in the result. |
| CRISPR FY2023 regression | Allows approximately ±3% dollar drift and a broad basis-difference interval. Does not prove the current figure to the dollar or exactly 10.1%. |
| Alzheimer's FY2023 regression | Allows approximately ±3% dollar drift and a broad basis-difference interval. Does not prove the current figure to the dollar or exactly 16.5%. |

Historical execution of all eight is repository-reported. The two frozen offline reconciliations in section 2 provide a different, narrower kind of evidence.

### 3.4 Multi-model agent evaluation

**Repository-reported run:** October 20, 2026, 00:15–00:25 UTC; server **v0.13.0**. [EVAL_VERDICTS.md](demonstration_fixture/EVAL_VERDICTS.md), STEP 1–3, identifies:

| Endpoint/model label | First-tool selection |
|---|---:|
| GPT-5-5 | 7/8 |
| Claude Sonnet 4-6 | 7/8 |
| Llama 3.3 70B Instruct | 8/8 |
| **Total** | **22/24 (91.7%; rounded 92%)** |

In this rerun, GPT and Claude selected `check_investigator_overlap` rather than `investigator_portfolio` for Q5. Earlier runs had a different per-model failure pattern; they must not be merged.

The displayed question matrix implies **7/8 unanimously correct**, while the supplied evaluation prose said **6/8**. This revision does not promote either to a separately verified headline: the matrix arithmetic is clear, but the run should be reconciled against raw traces before publishing another unanimity score.

The reported **24/24 argument-validity** result is distinct from correct tool selection and correct final answers. State the validator used, semantic constraints checked, and whether calls were actually executed when publishing its traces. The reported **3/3 stable** result means three questions repeated five times on GPT-5-5; it does not guarantee determinism on other prompts, settings, or endpoint revisions.

The eight-question set predates coverage of `group_by`, application-type filtering, spending-category routing, and `clinical_trials_lookup`. It does not validate the complete v0.14.9 tool surface, end-to-end scientific interpretation, or reliable abstention.

### 3.5 Performance metrics and behavioral cases

Historical examples support useful workflows but are not a controlled benchmark:

- **BC-1/BC-2:** one-call renewal and institution answers were reported on GPT-5-5 at v0.13.0. Earlier 32-call and 18-call behavior was reported, but the available documentation does not establish a matched experimental protocol that isolates a single docstring change.
- **BC-3/BC-4/BC-5:** duration abstention, P41 record-grain handling, and HuBMAP keyword-scope handling were rerun using Claude Sonnet 4-5 at v0.14.0. These are separate runs, not the GPT cases or the three-model selection experiment.
- The old mean-tool-call efficiency metric was withdrawn because of harness-order, zero-call scoring, and truncation problems. It is not included in the pass totals.
- No controlled p50/p95 latency, concurrency, rate-limit, or cold-versus-warm benchmark is verified here. Historical timing observations are not retained as a “>100×” performance claim.

**Measured figures available at this release.** Each row carries its evidence tier. None of them is a controlled benchmark.

| Metric | Value | Tier and method |
|---|---|---|
| Model-free CI | 167 passed + 2 xfailed of 215 collected, on Python 3.11 and 3.12 | Repository-reported: the selected suites in section 3.1. |
| First-tool selection | 22/24 = 91.7% across three models | Repository-reported at `v0.13.0` (claim register, section 1.3). It scores the first tool chosen, not the final answer. |
| Tool calls per answer in the deployed Ask demo | Largest-award question: 1 call. FY2020 R01 competing-renewal count: 1 call produced the count, and the agent then made an unrequested second call for a dollar figure, so that answer took 2 calls. | Team-reported: Ask-page tool traces on the deployed app, October 22, 2026. One observation per question. |
| Per-call latency shown in those traces | 0.03 s for each `search_funded_projects` call; 2.6 s for the `summarize_funding_by_topic` call | Team-reported, same traces. Cache state was not recorded, so these values do not distinguish cache hits from upstream requests. |
| Response cache | 900-second TTL, in-process, keyed by URL and canonical request payload | Verified: source inspection of `utils.py` (section 5.1). |
| Upstream response-size guard | 10 MiB for RePORTER; 5 MiB for ClinicalTrials.gov and MedlinePlus | Verified: source inspection. Oversized responses are rejected before JSON parsing. |
| Courtesy rate limits | Minimum interval between requests: 1.0 s RePORTER, 0.34 s E-utilities, 0.5 s MedlinePlus and ClinicalTrials.gov | Verified: source inspection. These intervals cap throughput by design; throughput itself was not measured. |

**Planned:** publish matched agent traces and a benchmark protocol with fixed questions, scoring rules, endpoint identifiers, decoding settings, cache state, request counts, and failures.

### 3.6 Agent-boundary contract (new in v0.14.9)

Before v0.14.9 the hosted Ask loop sent the model a one-line system message. The boundaries in section 5.2 lived in this document, the prompts and the tool notes, and nothing required the loop to carry them into an answer. `tests/test_agent_boundaries.py` closes that gap and is part of the CI selection.

Each test runs the real `_run_agent` loop end to end. A scripted model stands in for the endpoint and deliberately leaves out every caveat. The real MCP server runs in-process, with RePORTER replaced at the raw-fetch boundary by the frozen CRISPR fixture or by synthetic records, so no network is used. The test then checks the answer the user would see.

| Case | Input | The final answer must |
|---|---|---|
| Rules reach the model | any question | have a system message that states all four boundaries |
| Orphan exclusion | frozen CRISPR fixture through `summarize_funding_by_topic` | keep $19,790,134 and state that 1 excluded subproject's parent was absent, so award-family investment may be missing |
| Incomplete retrieval | 14,000 synthetic matches | state that only 10,000 of 14,000 records were aggregated and that the figure is a lower bound |
| Keyword scope | topic query on a complete cohort | state that it is a keyword cohort, not an RCDC spending-category total, and add no other caveat |
| Unsupported questions | duration ranking, trainee outcomes, federal spending share | withhold the model's fabricated answer and say the question is not supported |
| Controls | a clean answer, the two benchmark questions, an answer that already states its caveats | be returned byte-for-byte unchanged |

The tests were written before the v0.14.9 fix: run against the earlier v0.14.8 Ask loop, 8 of the 12 failed (the system-message test, the three caveat cases, the three unsupported questions and the boundary report) and the 4 controls passed; with the fix all 12 pass.

The fix has two layers. The rules are in the system message on every request, and `agent_boundaries.enforce` checks the final answer against the question and the full tool results the loop received. A missing caveat is appended under a plain "Scope and limits" note built from the tool output. An unsupported question gets a decline instead of the model's draft, which is kept in the response as `withheld_draft`. The response also lists which boundaries fired and whether the check added them.

**Limits.** Unsupported questions are recognized by question patterns for the three documented classes, so a differently worded question can reach the model unguarded, and the system message is then the only defence. The caveat checks look for wording, not meaning. How a particular live model behaves on these cases is a deployed-app observation; it is recorded after deployment in the release notes, because a commit cannot contain results produced after it.

## 4. Historical live figures

The following inputs are **repository-reported**, chiefly from RUN_MANIFEST A5 on October 19 at **v0.13.0**. They are not live results from this documentation revision. Preserve query arguments and timestamps when citing them.

| Query / measure | Reported result | Interpretation |
|---|---|---|
| `topic="CRISPR gene editing"`, FY2023 | all_records **$921,543,173**; whole_award **$836,981,580** | Basis difference **10.1%**, calculated as `(all_records − whole_award) / whole_award`. |
| `topic="Alzheimer's disease"`, FY2023 | all_records **$4,685,253,389**; whole_award **$4,020,899,771** | Basis difference **16.5%**, using the same denominator. This is the text query, not an official RCDC total. |
| R01 FY2020, `group_by="application_type"` | **1,089 / 29,560 = 3.68%** competitive renewals | Counts from the documented non-subproject faceting path, not from a capped sample of returned projects. |
| R01 FY2023, `application_types=[5]` | **21,150 matching records** | The manifest's facet cross-check is **21,146**, with four subproject records explaining the difference. Do not divide the raw-record numerator by an award-grain denominator and call it an exact award percentage. |
| P41 FY2015 / FY2025, application-type faceting | **13 / 77** and **1 / 31** competitive renewals | Preserve the same counting grain across years. Raw type-filtered record counts are different. |
| R21 FY2018, organization grouping | **Johns Hopkins, 96** | Reported highest bucket in that query; not a universally verified institutional ranking. |
| Award-amount sort, FY2020–FY2025 | **$448,283,318**, `OT2HL161847`, FY2021 | Largest returned award amount in that specified query. Not an all-time maximum, lifetime project cost, or outcome value. |
| Arthritis FY2023, RCDC ID 55 / free text | **$291,641,663 / $708,609,739** | Different cohort definitions. Neither figure validates the other. |

For CRISPR FY2023 the manifest reports 1,739 matches, 226 excluded subprojects, seven missing amounts, and 1,506 contributors. The smoke documentation also reports 166 orphan subprojects. Therefore **the entire 10.1% difference cannot be described as proven within-cohort duplicate dollars removed**. “All-record versus whole-award basis difference” is the defensible label. The explicit parent-present fixture in section 2.4 supplies the direct double-counting proof.

## 5. Reliability, limitations, and mission alignment

### 5.1 Implementation controls

Verified in [utils.py](https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.9/src/nih_reporter_mcp/utils.py):

- Outbound host allowlist: `api.reporter.nih.gov`, `eutils.ncbi.nlm.nih.gov`, `wsearch.nlm.nih.gov`, and `clinicaltrials.gov`.
- Topic/string length limit: **500 characters** in the relevant validator; fiscal-year array limit: **20**.
- Upstream response-size guard: **10 MiB**.
- HTTP-response cache: **900-second TTL**, keyed by URL and canonical request payload.
- Aggregation occurs after raw-response retrieval. The two funding bases can correctly reuse the **same cached raw response**; funding basis is not a required component of that raw-response cache key.

The existence of these controls is verified by inspection. Mocked error-path execution is repository-reported with CI; it is not a penetration test. This revision does not certify the absence of secrets across repository history or every web-app security boundary.

### 5.2 Known boundaries

| Area | Boundary to preserve in answers |
|---|---|
| Portfolio funding | State the query, fiscal years, agency scope, funding basis, and incomplete/missing/conflicting-record warnings. Do not substitute search matches for total research investment. |
| Investigator overlap / Other Support | Public funded-award matches are candidates for human review. They are not a complete Other Support disclosure, effort accounting, or a duplication/compliance determination. |
| Publications | A source-reported grant–paper association does not establish causal impact or identify the funding year that supported the work. Missing links do not establish absence of a relationship. |
| Clinical trials | A structured grant reference is an association. Do not allocate the full grant amount to each trial, equate a registered plan with results, or infer outcomes caused by that grant. |
| Study sections | `funded_projects_by_study_section` describes funded-project distributions. It does not measure total review workload, including unfunded applications. |
| Recent awards | Record-addition recency must not be presented as the award decision date unless the relevant date field supports it. |
| Geography | Recipient-institution location is not necessarily study location, participant location, or local benefit. |
| Unsupported questions | No workforce/career-outcome integration or duration-sort capability is demonstrated. The documented USAspending stub is not a functioning integration and is outside the 14-tool capability claim. |
| Topic/program membership | A keyword occurrence does not establish membership in a named program, even when every returned match was retrieved. |

From v0.14.9 the Ask loop carries four of these boundaries into every answer itself: orphan exclusion and incomplete retrieval under portfolio funding, keyword-versus-RCDC scope under topic/program membership, and unsupported questions (section 3.6). The others still depend on the model following the tool notes.

These limits support both missions: **oversight**, through reviewable portfolio and counting decisions, and **service delivery**, through accessible explanations that preserve uncertainty. Plain language must not remove evidence or imply stronger certainty.

### 5.3 Deployed app and notebook

The documentation describes a workspace-authenticated Databricks app. “Ask” adds model-serving authorization and deployment configuration to the MCP/API dependencies.

**Current status: not verified in this revision.** Do not publish “Ask works,” “always works,” or a specific fixed root cause without a timestamped deployment check. An authentication/configuration failure is still a user-visible failure of that demonstration surface.

Place the following sentence beside the Ask control and in the demo introduction:

> “The hosted Ask demo depends on Databricks workspace and model-endpoint permissions; if it is unavailable, use the public frozen fixtures and local MCP reproduction steps below to evaluate funding reconciliation—the agent experience must be evaluated separately.”

If the failure is currently confirmed, replace the conditional with a dated, explicit “Ask is temporarily unavailable” notice.

The notebook is credible as a primary **walkthrough and historical-output artifact** when it states its run date, source tag, model dependencies, and frozen/live boundaries. Edited cells with old outputs are not evidence of a fresh top-to-bottom run. Endpoint-dependent cells must be marked and independently skippable. A successful evidence endpoint or fixture reconciliation does not establish that Ask works.

## 6. Reproduction procedure

The following recipes target a new local **Bash + Python 3.12** environment. They are derived from the inspected source. The offline fixture-check script was executed against the supplied artifacts for this revision; the server, dependency-install, CI, and live-run recipes were not executed here.

### 6.1 Pin source and capture the resolved environment

`requirements.txt` contains **minimum version ranges**, not a dependency lock. [pyproject.toml](https://github.com/conroyriodss/nih-reporter-mcp/blob/v0.14.9/pyproject.toml) also reports distribution version `0.1.0`, while the source module version is `0.14.9`. Use the resolved Git commit and source module version for identity; do not treat package metadata alone as proof of the release.

This procedure pins source and records a fresh dependency resolution. It does **not** reproduce the historical dependency environment bit-for-bit.

```bash
set -eu
RUN_ROOT="$(mktemp -d)"
git clone --branch v0.14.9 --single-branch \
  https://github.com/conroyriodss/nih-reporter-mcp.git "$RUN_ROOT/repo"
cd "$RUN_ROOT/repo"
git checkout --detach v0.14.9

export EVIDENCE="$RUN_ROOT/evidence"
mkdir -p "$EVIDENCE"
git rev-parse HEAD > "$EVIDENCE/source-commit.txt"
git rev-parse 'v0.14.9^{commit}' > "$EVIDENCE/tag-commit.txt"
diff "$EVIDENCE/source-commit.txt" "$EVIDENCE/tag-commit.txt"
git status --porcelain > "$EVIDENCE/working-tree-before.txt"
test ! -s "$EVIDENCE/working-tree-before.txt"

python3.12 -m venv "$RUN_ROOT/venv"
source "$RUN_ROOT/venv/bin/activate"
python -m pip install --upgrade pip > "$EVIDENCE/pip-upgrade.txt" 2>&1
python -m pip install -r requirements.txt -e . pytest \
  > "$EVIDENCE/install.txt" 2>&1

export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1
python --version > "$EVIDENCE/python-version.txt" 2>&1
python -m pip --version > "$EVIDENCE/pip-version.txt"
python -m pip freeze --all > "$EVIDENCE/resolved-environment.txt"
date -u '+%Y-%m-%dT%H:%M:%SZ' > "$EVIDENCE/run-started-utc.txt"
python - <<'PY' > "$EVIDENCE/input-hashes.json"
import hashlib, json
from pathlib import Path
files = ["requirements.txt", "pyproject.toml", ".github/workflows/ci.yml"]
print(json.dumps({f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
                  for f in files}, indent=2))
PY
```

Check the resolved full commit against the release and manifest. This document uses tag names; record the actual full SHA in the new run evidence. A future failure after resolving newer dependencies must not be concealed by citing an earlier pass count.

### 6.2 Execute the exact model-free CI selection

```bash
set +e
python -m pytest \
  tests/test_counting.py \
  tests/test_security.py \
  tests/test_prompt_contracts.py \
  tests/test_clinical_trials.py \
  tests/test_version_contract.py \
  tests/test_agent_boundaries.py \
  tests/test_robustness.py::TestPartC_MockedUpstreamFailures \
  -v --tb=short -p no:cacheprovider \
  --junitxml="$EVIDENCE/ci.junit.xml" \
  > "$EVIDENCE/ci.stdout.txt" 2>&1
ci_status=$?
set -e
printf '%s\n' "$ci_status" > "$EVIDENCE/ci.exit-code.txt"
cat "$EVIDENCE/ci.stdout.txt"
```

**Expected output at v0.14.9:** 167 passed, 2 xfailed; exit status 0. Report the actual run, including failures, errors, skips, and unexpected passes. JUnit often represents expected failures as skipped test cases with a reason; retain the pytest output rather than counting every XML “skipped” as an ordinary skip. A collect-only count is not a pass count.

Run separately under Python 3.11 to reproduce that matrix leg. Do not infer both legs passed from one local execution.

### 6.3 Reconcile the frozen fixtures without network or server

Run from the repository root. This independent script uses the Python standard library, not `aggregate_funding`. It checks the supplied fixture shape explicitly; a changed fixture requires review, not automatic acceptance.

```bash
python - <<'PY' > "$EVIDENCE/frozen-reconciliation.json"
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path

root = Path("docs")
expected = {
    "demonstration_fixture": (38, 37, 1, Decimal("19790134")),
    "demonstration_fixture_double_counting": (8, 1, 7, Decimal("5130473")),
}
report = []
for name, (n_raw, n_in, n_excluded, expected_total) in expected.items():
    folder = root / name
    raw_path = folder / "raw_records.json"
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert digest == (folder / "raw_records.sha256").read_text().split()[0]
    document = json.loads(raw_path.read_text())
    records = document["results"]
    seen, contributing, excluded = {}, [], []
    all_records_total = Decimal("0")
    for record in records:
        appl_id = record["appl_id"]
        assert appl_id is not None, "Fixture needs an explicit missing-ID decision"
        if appl_id in seen:
            assert record == seen[appl_id], "Conflicting duplicate needs review"
            continue
        seen[appl_id] = record
        amount = record["award_amount"]
        assert amount is not None, "Fixture has changed: review missing amount"
        all_records_total += Decimal(str(amount))
        if record["subproject_id"] is not None:
            excluded.append(record)
        else:
            contributing.append(record)
    total = sum((Decimal(str(r["award_amount"])) for r in contributing), Decimal("0"))
    assert (len(records), len(contributing), len(excluded)) == (n_raw, n_in, n_excluded)
    assert len(seen) == len(records), "These snapshots are expected to have no duplicates"
    assert total == expected_total

    with (folder / "decision_ledger.csv").open(newline="") as stream:
        ledger = list(csv.DictReader(stream))
    assert len(ledger) == len(records)
    assert len({int(row["appl_id"]) for row in ledger}) == len(ledger)
    assert {int(row["appl_id"]) for row in ledger} == set(seen)
    included_ids = {r["appl_id"] for r in contributing}
    for row in ledger:
        appl_id = int(row["appl_id"])
        original = seen[appl_id]
        included = appl_id in included_ids
        assert row["decision"] == ("included" if included else "excluded")
        assert Decimal(row["award_amount"]) == Decimal(str(original["award_amount"]))
        assert row["core_project_num"] == (original["core_project_num"] or "")
        assert row["subproject_id"] == ("" if original["subproject_id"] is None else str(original["subproject_id"]))
        assert int(row["fiscal_year"]) == original["fiscal_year"]
        assert Decimal(row["amount_counted"]) == (Decimal(str(original["award_amount"])) if included else Decimal("0"))
    assert sum((Decimal(row["amount_counted"]) for row in ledger), Decimal("0")) == total

    parents = {(r["core_project_num"], r["fiscal_year"]) for r in contributing}
    orphan_ids = [r["appl_id"] for r in excluded
                  if (r["core_project_num"], r["fiscal_year"]) not in parents]
    if name == "demonstration_fixture":
        assert orphan_ids == [10992993]
        bundle = json.loads((folder / "tool_output.json").read_text())
        summary = bundle["summary"]
        assert Decimal(str(summary["total_award_amount_usd"])) == total
        assert summary["total_matching_projects"] == n_raw
        assert summary["projects_aggregated"] == n_in
        assert summary["complete"] is True
        assert summary["records_with_missing_amount"] == 0
        assert summary["deduped_count"] == 0
        assert summary["subproject_excluded_count"] == n_excluded
        assert summary["funding_basis"] == "whole_award"
        assert bundle["provenance"] == summary["provenance"]
        prov = bundle["provenance"]
        assert len(prov["source_record_ids"]) == n_in
        assert set(prov["source_record_ids"]) == included_ids
        assert prov["records_aggregated"] == n_in
        assert prov["query_criteria"] == document["request_payload"]["criteria"]
    else:
        assert not orphan_ids
        assert all_records_total == Decimal("10260946")
    report.append({
        "fixture": name, "status": "PASS", "raw_records": len(records),
        "contributors": len(contributing), "subprojects_excluded": len(excluded),
        "orphan_ids": orphan_ids, "whole_award_usd": str(total),
        "all_records_usd": str(all_records_total), "raw_sha256": digest,
    })
print(json.dumps(report, indent=2))
PY
cat "$EVIDENCE/frozen-reconciliation.json"
```

Expected results: two PASS records, primary whole-award sum **19790134**, parent-present whole-award sum **5130473**, and parent-present all-record sum **10260946**.

Validate the stored response against the installed release models separately:

```bash
python - <<'PY' > "$EVIDENCE/stored-schema-validation.txt"
import json
from pathlib import Path
from nih_reporter_mcp.tools.evidence_bundle import EvidenceBundle
from nih_reporter_mcp.models import FundingSummary
bundle = json.loads(Path("docs/demonstration_fixture/tool_output.json").read_text())
EvidenceBundle.model_validate(bundle)
FundingSummary.model_validate(bundle["summary"])
print("PASS: stored EvidenceBundle envelope and FundingSummary schema")
PY
```

Do not pass the entire envelope to `FundingSummary.model_validate`; its input is `bundle["summary"]`. Schema acceptance establishes shape/types, not factual correctness of every scalar.

### 6.4 Start the server and verify the actual inventory

Run in the same shell:

```bash
env -u DATABRICKS_APP_PORT PORT=8765 PYTHONPATH="$PWD/src" \
  python -m nih_reporter_mcp.app > "$EVIDENCE/server.stdout.txt" 2>&1 &
MCP_SERVER_PID=$!
trap 'kill "$MCP_SERVER_PID" 2>/dev/null || true' EXIT
export MCP_URL="http://127.0.0.1:8765/mcp"

python - <<'PY' > "$EVIDENCE/runtime-inventory.json"
import asyncio, json, time, urllib.request
from fastmcp import Client

for attempt in range(30):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/version", timeout=2) as r:
            version = json.load(r)
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)

async def main():
    async with Client("http://127.0.0.1:8765/mcp") as client:
        tools = await client.list_tools()
        prompts = await client.list_prompts()
        resources = await client.list_resources()
    actual = {"tools": len(tools), "prompts": len(prompts), "resources": len(resources)}
    assert actual == {"tools": 14, "prompts": 9, "resources": 3}, actual
    assert version["version"] == "0.14.9", version
    assert all(version[k] == value for k, value in actual.items()), version
    print(json.dumps({"version": version, "actual_counts": actual,
                      "tool_names": sorted(t.name for t in tools)}, indent=2))
asyncio.run(main())
PY
cat "$EVIDENCE/runtime-inventory.json"
```

`/health` is a process-level response, not a live upstream test. Matching `/version` and MCP registry counts validates inventory consistency, not tool semantics.

### 6.5 Run live suites and retain failures

These commands require internet access and the running server, but not a Databricks model endpoint:

```bash
set +e
python eval/smoke_tests.py --sequential \
  > "$EVIDENCE/smoke.stdout.txt" 2>&1
smoke_status=$?
python -m pytest tests/test_correctness.py -v --tb=short -p no:cacheprovider \
  --junitxml="$EVIDENCE/live-correctness.junit.xml" \
  > "$EVIDENCE/live-correctness.stdout.txt" 2>&1
correctness_status=$?
set -e
printf '%s\n' "$smoke_status" > "$EVIDENCE/smoke.exit-code.txt"
printf '%s\n' "$correctness_status" > "$EVIDENCE/live-correctness.exit-code.txt"
cat "$EVIDENCE/smoke.stdout.txt"
cat "$EVIDENCE/live-correctness.stdout.txt"
```

Historical targets are **17/17 smoke** and **8 live-correctness passes**, with the methodological limits in section 3. Inspect both the summary and exit code. Record whether the missing-amount target condition was actually observed.

Live API data, upstream error behavior, and cache state can change. A mismatch needs diagnosis: query drift, source-data drift, environment failure, test defect, or implementation defect. Preserve the original frozen files and create a new dated snapshot when needed.

The preceding smoke run warms the server cache. Label the subsequent correctness run accordingly; restart the process before a measurement requiring a cold cache. A new process starts with an empty in-process cache.

### 6.6 Agent runs: separately gated

The Databricks notebook's model-evaluation cells require authorized serving endpoints. They are **endpoint-dependent**, not part of the model-free CI or standalone smoke suite.

For a new reported score, publish:

1. Source SHA, actual tool schemas, notebook revision, endpoint/model identifiers, run timestamps, temperature and other decoding parameters, token/round limits, and truncation behavior.
2. Every question, expected acceptable tool/argument choices, and scoring rule set before execution.
3. All raw tool selections and arguments, validation outcomes, tool responses, and final answers, with credentials removed.
4. Separate scores for routing, argument validity, completed execution, correct interpretation, and required abstention.
5. Coverage for newer grouping, category, clinical-trial, record-grain, missing-data, and unsupported-capability cases.

Changing the question set creates a new evaluation. Do not reuse the historical 22/24 denominator for a different tool surface or expanded battery.

### 6.7 Publish the run evidence

Copy the evidence directory out of temporary storage and attach it to the release, or commit an appropriate evidence package. A path under `/tmp` or private session memory is not accessible evidence for a public evaluator.

Publish a manifest containing the resolved source SHA, source cleanliness, requirement-file hash **and resolved environment**, exact commands and exit codes, dates, cache state, suite selection, actual results, and a hash inventory of the shipped artifacts. Include model metadata only for runs actually performed. Keep independent suite totals separate; do not count robustness Part C again.

## 7. Outstanding evidence and documentation repairs

Updating this file does not repair the companion files listed below.

| Priority | Remaining issue | Required correction |
|---|---|---|
| Resolved in v0.14.5 | Manifest artifact hash mismatch | At v0.14.5, RUN_MANIFEST A4 recorded the then-shipped `demonstration_fixture/independent_total.md` (3,926 bytes, SHA-256 `edca15031e947a8dc8a0e7d111e506de7a3901392d5c2d9eaa25a741e44657dc`). The earlier row (3,971 bytes) predated the v0.14.2 edit that removed a commit SHA from that file. At v0.14.7 the file's verdict line was relabelled from "AT HEAD" to "at v0.13.0" (3,942 bytes); RUN_MANIFEST A4 records the current hash. |
| High | Dependency-lock claim | The inspected requirements file contains ranges. Correct the manifest's “pip-freeze / lock” description or publish a real pinned environment artifact. |
| High | Provenance freshness and replay | Export a true upstream retrieval timestamp/cache indicator, request ordering, and full record evidence where complete historical replay is claimed. Until then, retain section 2.5's limitations. |
| Resolved in v0.14.9 | Agent-facing certainty exceeded this document's boundary | Up to v0.14.8 the server instructions advertised an “exact total-investment figure” and “curated, congressionally-mandated totals,” and the Ask loop carried no boundary into its answers. v0.14.9 qualifies the instructions, tool descriptions and prompts with completeness and keyword-versus-RCDC scope, and the Ask loop now enforces four boundaries (section 3.6). |
| High | Run identity and accessible logs | Historical A1–A5 and STEP 1–3 runs belong to v0.13.0, not v0.14.9. Replace ambiguous “at HEAD” statements with run identities; publish JUnit/log/trace artifacts currently referenced only by ephemeral or private paths. |
| High | Model-result contradiction | Reconcile the unanimity figure with the per-question matrix and raw traces. Do not mix the earlier GPT/Llama Q5 misses with the later GPT/Claude misses. |
| Medium | Method-order drift | `ground_truth_methodology.md` and parts of the manifest describe subproject exclusion before deduplication. The production loop and stored reproduction note deduplicate first. Align procedural documentation. |
| Medium | Weak or vacuous assertions | Replace no-op/constant-only “regression” checks with calls to production behavior; make absent live preconditions explicit; test capped provenance, missing IDs, cached timestamps, and full payload replay. |
| Medium | Unsupported headline precision | Separate printed from asserted smoke values; retain tolerances on live regressions; avoid claims of dollar-level verification beyond actually reconciled fixtures. |
| Medium | Packaging identity | Align the distribution version with the release, or explicitly document the discrepancy. |
| Medium | Cross-document drift | Reconcile stale counts and claims in architecture/roadmap/demo materials, including the older architecture test counts and unsupported 100% routing/efficiency language. |
| Medium | Demo state | Publish a timestamped Ask status beside the control, mark endpoint-dependent notebook cells, and distinguish frozen outputs from newly executed cells. |

## 8. Judge-facing demonstration and evidence map

A short demonstration should show the evidence before the headline test counts:

1. **Define the cohort:** “CRISPR sickle cell,” FY2024, `and/all` text criteria, whole-award basis.
2. **Open the frozen evidence:** 38 raw rows, 37 contributing application records, one excluded orphan subproject, full contributing IDs and ledger.
3. **Reconcile:** independently sum **$19,790,134** and check the raw hash.
4. **Explain the limit:** complete retrieval does not mean complete topic funding. The keyword matched one subproject of P50HD096723 but not the parent center, so that child is excluded as an orphan; whole_award can understate topical investment here.
5. **Show a genuine double-counting case:** U19AG068753's parent plus children doubles the parent-present amount.
6. **Show validation scope:** selected model-free CI, live tests, and endpoint-dependent agent results are separate evidence streams.

| Judging area | Evidence to inspect | Claim boundary |
|---|---|---|
| Technical quality | Aggregation, models, evidence export, CI workflow and tests; both frozen fixtures | Demonstrated counting behavior and inspectability, not universal correctness or a verified performance benchmark. |
| Innovation | Goal-oriented evidence export and portfolio/explanation workflows using common source evidence | A useful workflow design; uniqueness against other MCP servers has not been benchmarked here. |
| Mission alignment | Reviewable investment analysis, plain-language explanation, explicit attribution and missing-data limits | Supports oversight and service delivery; does not replace policy, scientific, or compliance judgment. |
| Presentation | Cohort → evidence → independent sum → limits; visible deployment and endpoint dependencies | A reproducible artifact walkthrough is demonstrated separately from an available hosted agent experience. |

The strongest supported pitch is: **“An NIH funding answer you can inspect, reconcile, and interpret within explicit limits.”**

## 9. Security considerations

This section gathers the security controls from section 5.1 and [SECURITY.md](../SECURITY.md) in one place. Each item is either a verified control or a stated boundary; no new property is claimed here.

**Data and access model.**

- The server reads only public data. All four upstream services (NIH RePORTER, NCBI E-utilities, MedlinePlus Web Search and ClinicalTrials.gov) are public, unauthenticated, read-only APIs. The MCP server needs no upstream API key and stores no credentials.
- Source inspection found no storage of user questions or tool results in the MCP server. Investigator names in RePORTER are public federal award disclosures; no other personal data is processed. Platform logs of the hosted app are outside this review.
- The hosted Databricks app is available only to signed-in workspace users. Its Ask feature calls a model endpoint using the app's service principal, which adds workspace and model-endpoint permissions to the trust boundary (section 5.3).

**Outbound requests** (Verified: source inspection of `utils.py`, `utils_ctgov.py`, `tools/publication_details.py` and `tools/explain_health_topic.py`).

- Every client checks the target host against its own allowlist before any network call: `api.reporter.nih.gov`, `eutils.ncbi.nlm.nih.gov`, `wsearch.nlm.nih.gov` or `clinicaltrials.gov`. Base URLs are constants; user input never selects a host.
- Every client sets `follow_redirects=False` and `trust_env=False`, so neither a redirect nor an environment-variable proxy can send a request elsewhere.
- Each client has a timeout (30 s RePORTER, 20 s ClinicalTrials.gov, 15 s E-utilities and MedlinePlus), a response-size cap enforced before parsing, and a courtesy rate limiter (section 3.5).

**Input validation** (Verified: source inspection). Free-text parameters are capped at 500 characters, and list parameters such as `fiscal_years`, `activity_codes` and agency lists at 20 items. State codes must be two letters, spending categories resolve through a curated lookup, and `funding_basis` accepts only `whole_award` or `all_records`. Tool arguments are typed and checked against each tool's input schema before the tool runs. Rejections return an explicit error message.

**Tests** (Repository-reported, section 3.1). `tests/test_security.py` contains 24 tests covering the four host allowlists (allowed host, rejected host and missing host), the allowlist constants, and the string- and list-length guards. Smoke cases t5–t6 exercise invalid input and upstream rejection; t6 depends on upstream behavior (section 3.2).

**Boundaries.**

- These controls are verified by inspection and unit tests. They are not a penetration test, a dependency vulnerability audit, or a review of the Databricks platform.
- This revision does not certify the absence of secrets across repository history.
- The requirements file uses version ranges, so dependency versions are resolved at install time (section 7, dependency-lock claim).
- Unhandled web-app errors return JSON containing the exception message, truncated to 500 characters, rather than a stack trace.
- The web app's `/debug` diagnostic route returns configuration status to signed-in users. Up to v0.14.8 it also returned the length and first eight characters of the app's current access token; v0.14.9 removed both, and the route now reports only whether a token is present.

## 10. Lessons learned and recommendations

### 10.1 Lessons learned

**Funding arithmetic.**

- The counting rule belongs in the answer. In the U19AG068753 family (section 2.4), summing every record gives exactly twice the whole-award total, and without a stated basis both numbers look plausible.
- Excluding components is a different operation from removing double counting. An orphan subproject, where the keyword matched a child but not its parent, is real investment that whole_award drops; section 2.3 shows one such record. Answers should name orphan exclusions instead of presenting the total as complete.
- Complete retrieval is not complete topic funding (section 2.6). A keyword cohort can be fully retrieved and still miss related records or include unrelated ones.

**Claims against evidence.**

- A published figure needs its run identity beside it. Earlier documents presented historical runs as current; the evidence tiers in section 1.1 and the dated run records in RUN_MANIFEST replaced that practice.
- Test counts are not test strength. Some passing tests assert constants or contain no assertion (section 3.1), so a count shows what ran, not what was verified.
- A boundary written down is not a boundary enforced (fixed in v0.14.9). Up to v0.14.8 this document, the prompts and the tool notes stated the interpretation limits, but the Ask loop sent the model a one-line system message and returned whatever it wrote. The loop now carries the limits, backed by tests that fail when they are missing (section 3.6).
- Agent behavior needs traces, not summaries. In one deployed run the agent answered the requested count with one call and then made an unrequested second call (section 3.5); only the trace showed it.

**Release integrity.**

- A parser that reads prose breaks when the prose is edited. At `v0.14.6`, the notebook's identity check matched a sentence in RUN_MANIFEST and failed when a straight apostrophe became a typographic one. The replacement reads only the table row and SHA cell it needs, and stops with an error on any ambiguity.
- A release check must run the shipped code on its shipped path. The pre-tag sweep now runs the notebook's own parser against the committed manifest on the default path, and repeats the sweep from a fresh clone of the pushed tag.
- Internal consistency is not conformance to requirements. The `v0.14.5` rewrite kept every document consistent with the others while dropping three of this document's required section headings, and the required slide labels were never present. The sweep now also checks a fixed external checklist taken from the deliverables specification.

### 10.2 Recommendations

Section 7 is the prioritized list of repairs. These recommendations group it by goal instead of repeating it.

1. **Align agent-facing text with this document's boundary.** Done in v0.14.9 for the server instructions, tool descriptions, prompts and the Ask loop (section 3.6). Next, extend the boundary tests to more question wordings and score live models on them with the protocol in section 6.6.
2. **Publish reproducible evidence.** Release a locked environment, JUnit and trace artifacts, and the benchmark protocol planned in section 3.5, so that repository-reported results can become verified ones.
3. **Strengthen the tests that are counted.** Replace no-op and constant-only checks with calls to production behavior (section 7, Medium).
4. **Tighten the hosted app.** v0.14.9 removed the token details from `/debug`. Restrict the route further, and publish a dated Ask status beside the control (section 5.3).
5. **Keep companion documents current.** Align SECURITY.md with this section: it counts three upstream APIs where four are contacted, and describes dependencies as pinned where the requirements file uses ranges. Reconcile the architecture and roadmap counts as well (section 7, Medium).
