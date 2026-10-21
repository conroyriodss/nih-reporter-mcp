# NIH RePORTER MCP Server

[![CI](https://github.com/conroyriodss/nih-reporter-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/conroyriodss/nih-reporter-mcp/actions/workflows/ci.yml)

An MCP (Model Context Protocol) server that gives AI agents goal-oriented access to live NIH grant funding data via [NIH RePORTER](https://reporter.nih.gov/), the authoritative public record of NIH and other HHS-agency research funding (~$42B/year across NIH, CDC, FDA, and ACF).

Built for the [GSA MCP Server and AI Agent Government Hackathon](https://www.gsa.gov/artificial-intelligence/ai-community-of-practice/events-and-training/mcp-server-and-ai-agent-government-hackathon).

## Why this exists

Two distinct government use cases, one server:

- **Oversight**: "How much has NIH spent on X?" "Is funding for Y growing or shrinking?" "What's NIH's official spending category say vs. what a keyword search finds?" — answerable by program staff, Congress, or the public without manually querying raw APIs.
- **Service delivery / research discovery**: "What's funded in this area?" "What came out of this grant?" "What's this investigator's portfolio?" — answerable by researchers, clinicians, or journalists.

Rather than wrapping RePORTER's raw REST endpoints 1:1, every tool here is designed around a **user goal**, with validated inputs, structured outputs, and honest reporting of the API's real limitations (a 10,000-record hard ceiling, ambiguous organization name matching, free-text search vs. official categorization) — because those limitations produce wrong answers if hidden, and useful ones if surfaced.

## Tools

| Tool | Purpose |
|---|---|
| `search_funded_projects` | Find funded projects matching a topic, with filters (fiscal year, state, agency, active/inactive, `application_types`, `activity_codes`). Supports server-side `group_by` faceting (`application_type`, `organization`, `administering_ic`) for deduped award counts that bypass the 10,000-record pagination ceiling |
| `summarize_funding_by_topic` | Exact total NIH/HHS investment in a topic, via full pagination (not a 500-record estimate). Accepts either free-text or an official NIH spending category |
| `funding_trend_by_year` | Year-by-year funding trend for a topic or spending category |
| `organization_funding_profile` | Funding profile for a named institution, with exact-name matching by default to avoid silently combining similarly-named institutions |
| `investigator_portfolio` | Funded portfolio for a named researcher |
| `check_investigator_overlap` | Screens an investigator's publicly funded NIH awards for candidate overlap as input to Other Support review (pending, non-NIH, and unpublished support are not visible), with explicit project exclusion so the application under review is omitted |
| `funded_projects_by_study_section` | Distribution of funded projects across the peer-review study sections that evaluated them — shows funded outcomes only (unfunded/pending applications are not in RePORTER), useful for seeing which panels handle funded projects in a given research area |
| `search_recent_awards` | Most recently added award records sorted by date added to RePORTER — useful for program officers tracking what's newly funded. Honestly notes that database recency can lag actual award notice dates |
| `export_evidence_bundle` | Inspectable audit trail for any funding claim: returns the summary, full provenance (query criteria, source record IDs, timing), counting-unit disclaimer, and a reproduction note |
| `explain_health_topic` | Plain-language health-topic explanation from MedlinePlus (NIH/NLM consumer health service), in English or Spanish. Gives non-expert audiences authoritative background on a condition alongside funding data |
| `get_project_by_id` | Direct lookup by application ID or core project number |
| `list_publications_for_project` | PubMed IDs linked to a project |
| `get_publication_details` | Resolves PubMed IDs into full citations (title, journal, authors) via NCBI E-utilities — closes the gap left by RePORTER's publications endpoint, which returns bare IDs only |
| `clinical_trials_lookup` | Find clinical trials linked to an NIH grant or matching a condition via ClinicalTrials.gov v2. Each link carries an explicit evidence class (`source_asserted` vs `candidate`), NIH-vs-FDA disambiguation via the `type` field, and interventional/observational distinction. Never multiplies grant funding across linked trials |

## Prompts

Reusable prompt templates that compose the tools above into multi-step analyst workflows. One evidence base, two audiences:

### General / Analyst

| Prompt | Purpose |
|---|---|
| `funding_overview` | Total investment, top institutions, and top investigators for a topic — a complete funding snapshot in one pass |
| `institution_report` | Deep dive into a single institution's funded portfolio across a topic area |
| `compare_rcdc_vs_freetext` | Head-to-head comparison of an official NIH spending category total vs. a free-text keyword search — surfaces the documented divergence between the two methods |
| `research_landscape_summary` | Competitive landscape for a research idea: total investment, trend direction, most prominent funded groups, with an explicit NIH-only scope disclaimer |

### Program Officer

| Prompt | Purpose |
|---|---|
| `portfolio_brief` | Reproducible cohort brief with IC/mechanism breakdown, free-text vs RCDC framing, evidence bundle with source_record_ids, and explicit counting-unit caveat |
| `other_support_review` | Screen an investigator's publicly funded NIH awards for candidate overlap as input to Other Support review, with boundary statement that this is a public-record screening tool (pending, non-NIH, and unpublished support are not visible) |
| `investment_to_outputs` | Investment-to-outputs dossier: project details, linked publications, citation metadata. Labels grant-paper links as source_reported; does not attribute publications to specific funding years |

### Citizen Scientist

| Prompt | Purpose |
|---|---|
| `explain_funding_landscape` | Plain-language funding overview for non-experts: defines jargon, clarifies institutional geography, distinguishes planned from reported research, includes NIH-only scope disclaimer |
| `follow_the_evidence` | Lay-reader narrative of a funded project: what was the question, who studied it, what was published, in everyday language |

See [`docs/findings.md`](docs/findings.md) for documented data-quality discoveries made during development (several are directly relevant to anyone else building on this API) and [`docs/roadmap.md`](docs/roadmap.md) for planned future tools.

## Quickstart

```bash
git clone <this-repo>
cd nih-reporter-mcp
uv sync
uv run python main.py
```

Server starts on stdio by default (for local MCP client testing, e.g. Claude Desktop or MCP Inspector). Set `PORT` or `DATABRICKS_APP_PORT` to serve Streamable HTTP instead. For Databricks Apps deployment, see [`app.yaml`](app.yaml).

No API key or authentication is required for the underlying NIH RePORTER or NCBI E-utilities APIs.

## Evaluation

Three test tiers, each runnable independently:

**Model-free CI (GitHub Actions, every push/PR):** 155 pytest pass + 2 xfail across `test_counting` (67p + 2xf: synthetic aggregate_funding unit tests including pagination clamping, server-side faceting, PI group-by), `test_security` (24p: host-allowlist and input-size guards), `test_prompt_contracts` (29p: every prompt references only existing tools with correct parameter names), `test_clinical_trials` (23p: ClinicalTrials.gov v2 integration, evidence-class classification, NIH-vs-FDA disambiguation), `test_version_contract` (1p: `/version` counts equal the live `list_tools`/`list_prompts`/`list_resources` registries), and `test_robustness::TestPartC` (11p: mocked upstream failure handling: HTTP 500, 429 retry, timeout, oversized response, malformed JSON). No network, no server, no model access required.

**Live-server integration (local, requires running MCP server):** 17 standalone smoke tests (`eval/smoke_tests.py`) against live RePORTER data (not mocked), covering exact-total correctness, the 10,000-record retrieval cap, organization-name disambiguation, RCDC-category-vs-free-text divergence, input validation, injection-style input handling, investigator overlap/exclusion logic, funded-project study-section distribution, recent-awards sort validation, provenance/counting-unit transparency, evidence-bundle export inspection, whole_award vs all_records dedup verification, cache correctness, and MedlinePlus health-topic lookup. A single tool-description clarification dramatically reduced redundant agent calls (BC-1: 32→1 calls; BC-2: 18→1 calls; real traces at v0.14.0). 8 additional correctness tests (`tests/test_correctness.py`) prove funding arithmetic against independently-derived ground truth. 49 robustness tests = 11 mocked (Part C, counted within the 155 CI figure) + 38 server-dependent (Parts A/B/D/E: 32 stable + 6 pass-with-retry) in `tests/test_robustness.py`; the server-dependent set exercises live-server error handling, rate-limit recovery, and boundary conditions (the 6 retries are transient upstream timeouts).

**Multi-model agent eval (Databricks notebook only):** Tool-selection accuracy across 3 model families (GPT-5-5, Claude Sonnet 4-6, Llama 3.3 70B): 22/24 (92%). Determinism: 3/3 stable over 5 repeats. Argument validity: 24/24 (100%). See `notebook-merged` §14.

See [`eval/README.md`](eval/README.md) for how to run each tier and [`docs/findings.md`](docs/findings.md) for the full writeup of documented findings.

```bash
# Model-free CI tests (no server needed)
PYTHONPATH=src pytest tests/test_counting.py tests/test_security.py \
  tests/test_prompt_contracts.py tests/test_clinical_trials.py \
  tests/test_version_contract.py \
  tests/test_robustness.py::TestPartC_MockedUpstreamFailures -v
# All 155 tests pass (+ 2 xfail) in bare subprocess on Python 3.11/3.12 (no nest_asyncio needed).

# Live-server smoke tests
uv run python main.py &
sleep 5
uv run python eval/smoke_tests.py               # full parallel (~60-90s)
uv run python eval/smoke_tests.py --quick        # quick: 5 tests (~8s)
uv run python eval/smoke_tests.py --sequential   # full sequential (~100s)
```

The `--quick` flag runs only single-call tests (no full pagination) for fast iteration. The default full mode runs all 17 tests concurrently with per-test timeouts; `--sequential` runs them one at a time (useful for debugging or avoiding API rate-limit pressure). Test t9 (LLM agent-efficiency regression guard) runs only inside the companion Databricks notebook (`notebook-merged`), as it requires the Foundation Model API.

## Known limitations

- No query can return more than 10,000 matching records (an upstream RePORTER API ceiling); tools report this via a `complete` flag rather than silently truncating.
- Organization name matching is substring-based by default upstream; `organization_funding_profile` defaults to exact-name matching to avoid combining similarly-named institutions, with guidance to discover the correct exact name if needed.
- `summarize_funding_by_topic`'s curated spending-category lookup covers ~38 commonly-queried NIH RCDC categories out of ~300 total; others require the numeric category ID (see NIH RePORTER API Data Elements, Appendix I).
- `investigator_portfolio` matches on name text, not a stable person ID; common surnames require a first name to disambiguate.
- One tool is stubbed but not implemented: USAspending.gov cross-agency comparison. See [`docs/roadmap.md`](docs/roadmap.md). ClinicalTrials.gov cross-linking (`clinical_trials_lookup`) is now fully implemented and registered, with 23 offline tests.

## License

MIT. See [`SECURITY.md`](SECURITY.md) for the vulnerability disclosure policy.
