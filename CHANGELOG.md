# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-15

### Added
- Initial release: 8 tools, 3 prompts, 2 resources, custom HTTP routes.
- Template-compliant project layout (`src/nih_reporter_mcp/`).
- `get_publication_details` tool: resolves PubMed IDs into full citations
  via NCBI E-utilities esummary endpoint.
- SSRF hardening on all outbound HTTP clients (`follow_redirects=False`,
  `trust_env=False`, 10 MB response-size cap).
- Input-size guards: fiscal_years capped at 20, agencies/org_names at 20.
- Stub files for Tier 2 roadmap items: `clinical_trials_lookup.py`,
  `usaspending_comparison.py` (not registered; documented placeholders).
- Custom HTTP routes: `/health` (liveness probe) and `/version` (capability report).
- MCP prompts: `funding_overview`, `institution_report`, `compare_rcdc_vs_freetext`.
- MCP resources: `nih-reporter://spending-categories`, `nih-reporter://server-info`.
- `deploy/databricks/app.yaml` for Databricks Apps deployment.
- 9-assertion smoke test suite in the companion notebook.

### Fixed

#### `funding_trend_by_year` silently ignored `spending_category` parameter
- **Date**: 2026-10-14
- **Symptom**: Asking for year-over-year trends using an official RCDC
  spending category (e.g. "Cancer") returned all-zero funding amounts.
  The LLM would fall back to a topic-string workaround, which matched a
  much larger (and differently scoped) set of projects.
- **Root cause**: The `funding_trend_by_year` tool signature only accepted
  `topic` (required, positional). There was no `spending_category` parameter,
  so RCDC category IDs could not be passed to the upstream criteria builder.
  The LLM was forced to embed the category name as free text, which hit a
  completely different API code path.
- **Fix**: Added optional `spending_category` parameter (name or numeric ID)
  alongside optional `topic`; made `start_year` and `end_year` the required
  positional args. Added validation requiring at least one of
  `topic`/`spending_category`.
- **Regression test**: Smoke test t8 — calls `funding_trend_by_year` with
  `spending_category="Cancer"` and asserts every year has nonzero
  `project_count` and `total_award_amount_usd`.

#### 403 error leaked raw httpx traceback to the LLM
- **Date**: 2026-10-14
- **Symptom**: When a user's search text resembled SQL injection (e.g.
  `cancer" OR "1"="1`), RePORTER returned HTTP 403. The server re-raised
  this as a raw `httpx.HTTPStatusError` whose traceback included internal
  module paths and stack frames, leaking implementation details to the LLM.
- **Root cause**: The 403 status code was not handled explicitly; it fell
  through to the generic `resp.raise_for_status()` path, which raised an
  httpx exception with the full response body and stack.
- **Fix**: Added explicit 403 handling in `post_json` that raises a clean
  `ValueError` with a user-facing message ("RePORTER blocked this request
  (403), likely because the search text resembled a malicious pattern").
  No internal paths or stack frames are exposed.
- **Regression test**: Smoke test t6 — sends SQL-injection-style text,
  asserts the error message contains "403" and does NOT contain "httpx".
