# Clean-Room Execution Manifest (SUPERSEDED, 2026-10-18)

> **Historical record only.** Superseded by [`docs/demonstration_fixture/RUN_MANIFEST.md`](demonstration_fixture/RUN_MANIFEST.md), the single manifest for the submission tag. Counts below (85 CI, 18 smoke) are as of 2026-10-18 and are not current.

Single-provenance execution record for the NIH RePORTER MCP server
submission notebook and test suite.

## Environment

| Property | Value |
|---|---|
| Commit | H2 in RUN_MANIFEST §11 (2026-10-18, pre-v0.13.0) |
| Commit message | fix: tighten smoke-test assertions to match their descriptions |
| Commit date | 2026-10-18 17:54:39 UTC |
| Python | 3.12.3 |
| Platform | Databricks serverless (linux) |
| fastmcp | 4.1.1 |
| httpx | 0.28.1 |
| pydantic | 2.13.3 |
| uvicorn | 0.48.0 |
| starlette | 1.9.0 |

## Commands and Results

### 1. Model-free CI suite (no server required)

```
PYTHONPATH=src pytest tests/test_counting.py tests/test_security.py \
  tests/test_prompt_contracts.py \
  tests/test_robustness.py::TestPartC_MockedUpstreamFailures \
  -v --tb=short
```

| Suite | Passed | xfailed | Failed |
|---|---|---|---|
| test_counting.py (25 tests) | 25 | 2 | 0 |
| test_security.py (21 tests) | 21 | 0 | 0 |
| test_prompt_contracts.py (28 tests) | 28 | 0 | 0 |
| test_robustness.py Part C (11 tests) | 11 | 0 | 0 |
| **Total** | **85** | **2** | **0** |

Timestamp: 2026-10-18T18:06:00Z

### 2. Server-required tests (test_correctness.py)

These 8 tests require a running MCP server (localhost or deployed app).
They are excluded from CI but included in the notebook smoke suite.

- `test_ground_truth_exact_match` — fixture match ($19,790,134)
- `test_double_counting_arithmetic` — production aggregate_funding on U19AG068753
- `test_provenance_reproducibility` — re-fetch + re-sum
- `test_missing_amount_honesty` — null amounts tracked
- `test_funding_basis_consistency` — whole_award < all_records
- `test_overlap_completeness_flag` — complete + total_matching present
- `test_crispr_fy2023_regression` — $836.9M +/-3% band
- `test_alzheimers_fy2023_regression` — $4,020.9M +/-3% band

### 3. Smoke tests (18 tests, notebook cell 11)

Run against live deployed app (`mcp-nih-reporter`).
Requires authenticated session (Databricks OIDC).
Verified tightened assertions via direct RePORTER API: 3/3 pass.

### 4. Notebook

The notebook (`notebooks/notebook-merged.ipynb`) has been stripped of all
prior outputs to eliminate mixed-provenance contamination.  Outputs must
be produced from a single top-to-bottom run of the pinned commit.

To produce a clean execution record:

```bash
# 1. Start the server
cd src && uvicorn nih_reporter_mcp.app:app --port 8000

# 2. In a separate terminal, run correctness tests
MCP_URL=http://localhost:8000/mcp PYTHONPATH=src pytest tests/test_correctness.py -v

# 3. Open the notebook in Jupyter / Databricks and run all cells top-to-bottom
#    from a restarted kernel.
```

## Model endpoint

| Property | Value |
|---|---|
| Eval endpoint | `databricks-gpt-5-5`, `databricks-claude-sonnet-4-6`, `databricks-meta-llama-3-3-70b-instruct` |
| Agent loop endpoint | `databricks-gpt-5-5` (via serving endpoint in app.yaml) |
| Cache state | Enabled (production default; rate limiter + response cache) |

## Eval metrics (from prior frozen run, commit H1 in RUN_MANIFEST §11, v0.10.2)

| Metric | Value |
|---|---|
| Tool-selection accuracy | 22/24 (92%) |
| Unanimous cases | 6/8 |
| Determinism | 3/3 (100%) |
| Argument validity (structural + runtime) | 23/24 (96%) |

## Artifacts

| File | Description |
|---|---|
| `notebooks/notebook-merged.ipynb` | Output-stripped notebook (run to populate) |
| `docs/demonstration_fixture/tool_output.json` | Schema-valid evidence bundle (regenerated 2026-10-18) |
| `tests/fixtures/crispr_sickle_cell_fy2024.json` | Frozen fixture (38 records, 2026-10-15) |
| `docs/run_manifest.md` | This file |

## Notes

- test_correctness.py and smoke tests require a running server;
  they fail with `ConnectError` in offline CI.  This is expected.
- test_robustness.py Parts A/B/D hit the live RePORTER API and are
  excluded from CI to avoid network-dependent flakiness.
- Part C mocked tests must run in isolation (not after test_correctness.py)
  to avoid event-loop contamination.
- The notebook's prior outputs (mixed 9-tool and 13-tool provenance)
  have been stripped.  Any execution record must come from a single run.
