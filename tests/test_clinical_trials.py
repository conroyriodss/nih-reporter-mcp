"""Tests for clinical_trials_lookup — correctness and robustness.

Correctness tests verify against frozen fixtures (known links, evidence class,
NIH-vs-FDA disambiguation). Robustness tests mock CT.gov responses.

Run: PYTHONPATH=src pytest tests/test_clinical_trials.py -v
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "nih_reporter_mcp"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "clinical_trials"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Fixture loading ──────────────────────────────────────────────────────────

def load_fixture(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


# ── Parse helper tests ───────────────────────────────────────────────────────


class TestGrantExtraction:
    """Verify _extract_grants parses both ID locations."""

    def test_secondary_id_nih(self):
        from nih_reporter_mcp.ct_parsing import extract_grants as _extract_grants
        study = {
            "protocolSection": {
                "identificationModule": {
                    "secondaryIdInfos": [
                        {"id": "R01HL147914", "type": "NIH",
                         "link": "https://reporter.nih.gov/quickSearch/R01HL147914"}
                    ]
                }
            }
        }
        grants = _extract_grants(study)
        assert len(grants) == 1
        assert grants[0].is_nih is True
        assert grants[0].id_source == "secondaryIdInfos"
        assert grants[0].id_type == "NIH"

    def test_org_study_id_nih(self):
        from nih_reporter_mcp.ct_parsing import extract_grants as _extract_grants
        study = {
            "protocolSection": {
                "identificationModule": {
                    "orgStudyIdInfo": {
                        "id": "1R01DK081406-01A1", "type": "NIH",
                        "link": "https://reporter.nih.gov/quickSearch/1R01DK081406-01A1"
                    }
                }
            }
        }
        grants = _extract_grants(study)
        assert len(grants) == 1
        assert grants[0].is_nih is True
        assert grants[0].id_source == "orgStudyIdInfo"

    def test_fda_other_grant_not_nih(self):
        """The attribution trap: FDA contract must NOT be classified as NIH."""
        from nih_reporter_mcp.ct_parsing import extract_grants as _extract_grants
        study = {
            "protocolSection": {
                "identificationModule": {
                    "secondaryIdInfos": [
                        {"id": "75F40122C00181", "type": "OTHER_GRANT",
                         "domain": "Food and Drug Administration"}
                    ]
                }
            }
        }
        grants = _extract_grants(study)
        assert len(grants) == 1
        assert grants[0].is_nih is False
        assert grants[0].id_type == "OTHER_GRANT"
        assert grants[0].domain == "Food and Drug Administration"

    def test_mixed_nih_and_fda(self):
        """Study with both NIH and FDA grants: only NIH is_nih=True."""
        from nih_reporter_mcp.ct_parsing import extract_grants as _extract_grants
        study = {
            "protocolSection": {
                "identificationModule": {
                    "secondaryIdInfos": [
                        {"id": "R01HL147914", "type": "NIH"},
                        {"id": "75F40122C00181", "type": "OTHER_GRANT",
                         "domain": "Food and Drug Administration"},
                    ]
                }
            }
        }
        grants = _extract_grants(study)
        nih = [g for g in grants if g.is_nih]
        non_nih = [g for g in grants if not g.is_nih]
        assert len(nih) == 1
        assert nih[0].grant_id == "R01HL147914"
        assert len(non_nih) == 1
        assert non_nih[0].grant_id == "75F40122C00181"

    def test_no_type_field_not_classified_as_nih(self):
        """ID without a type field is NOT classified as NIH."""
        from nih_reporter_mcp.ct_parsing import extract_grants as _extract_grants
        study = {
            "protocolSection": {
                "identificationModule": {
                    "orgStudyIdInfo": {"id": "STUDY21070047"},
                    "secondaryIdInfos": [
                        {"id": "1 R01 DK081406-01A1 - NIH"}  # no type field
                    ]
                }
            }
        }
        grants = _extract_grants(study)
        # orgStudyIdInfo has no type → not included
        # secondaryId has no type → not included
        assert all(not g.is_nih for g in grants)

    def test_empty_study_no_crash(self):
        from nih_reporter_mcp.ct_parsing import extract_grants as _extract_grants
        grants = _extract_grants({})
        assert grants == []
        grants = _extract_grants({"protocolSection": {}})
        assert grants == []


class TestTrialParsing:
    """Verify _parse_trial extracts study_type and date pairs."""

    def test_observational_study_type(self):
        from nih_reporter_mcp.ct_parsing import parse_trial as _parse_trial
        study = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT01005173", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "UNKNOWN"},
                "designModule": {"studyType": "OBSERVATIONAL"},
                "sponsorCollaboratorsModule": {},
            }
        }
        trial = _parse_trial(study, "source_asserted")
        assert trial.study_type == "OBSERVATIONAL"
        assert trial.nct_id == "NCT01005173"

    def test_interventional_study_type(self):
        from nih_reporter_mcp.ct_parsing import parse_trial as _parse_trial
        study = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT04057716"},
                "statusModule": {
                    "overallStatus": "COMPLETED",
                    "startDateStruct": {"date": "2019-08-15", "type": "ACTUAL"},
                    "completionDateStruct": {"date": "2026-04-30", "type": "ESTIMATED"},
                },
                "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE3"]},
                "sponsorCollaboratorsModule": {
                    "leadSponsor": {"name": "Univ Pittsburgh", "class": "OTHER"},
                    "collaborators": [
                        {"name": "National Heart, Lung, and Blood Institute (NHLBI)", "class": "NIH"},
                    ],
                },
            }
        }
        trial = _parse_trial(study, "source_asserted")
        assert trial.study_type == "INTERVENTIONAL"
        assert trial.phases == ["PHASE3"]
        assert trial.start_date.actual == "2019-08-15"
        assert trial.start_date.estimated is None
        assert trial.completion_date.estimated == "2026-04-30"
        assert trial.completion_date.actual is None
        assert "NHLBI" in trial.nih_collaborators[0]

    def test_evidence_class_propagated(self):
        from nih_reporter_mcp.ct_parsing import parse_trial as _parse_trial
        study = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001"},
                "statusModule": {},
                "designModule": {},
                "sponsorCollaboratorsModule": {},
            }
        }
        trial = _parse_trial(study, "candidate")
        assert trial.evidence_class == "candidate"


class TestFixtureConsistency:
    """Verify frozen fixtures are internally consistent."""

    @pytest.mark.parametrize("fixture_file", [
        "nct04057716_r01hl147914.json",
        "nct01005173_r01dk081406_observational.json",
        "nct00209235_r21hd078864.json",
    ])
    def test_nih_fixture_has_required_fields(self, fixture_file):
        fix = load_fixture(fixture_file)
        assert fix["expected_type"] == "NIH"
        assert fix["expected_evidence_class"] == "source_asserted"
        assert fix["nct_id"].startswith("NCT")
        assert "verified_json_slice" in fix

    def test_fda_fixture_is_not_nih(self):
        fix = load_fixture("nct07178743_fda_attribution_trap.json")
        assert fix["expected_type"] == "OTHER_GRANT"
        assert fix["expected_is_nih"] is False
        assert "Drug Administration" in fix["expected_domain"]


class TestInputValidation:
    """Robustness: input validation guards (no fastmcp needed)."""

    def test_oversized_grant_id_raises(self):
        from nih_reporter_mcp.utils import validate_string_length
        with pytest.raises(ValueError, match="too long"):
            validate_string_length("X" * 600, "core_project_num")

    def test_oversized_condition_raises(self):
        from nih_reporter_mcp.utils import validate_string_length
        with pytest.raises(ValueError, match="too long"):
            validate_string_length("X" * 600, "condition")

    def test_empty_grant_stripped(self):
        from nih_reporter_mcp.utils import validate_string_length
        result = validate_string_length("  R01HL147914  ", "core_project_num")
        assert result == "R01HL147914"
class TestCTGovClientRobustness:
    """Mocked CT.gov client: malformed responses, errors, timeouts."""

    def test_404_returns_empty(self):
        from nih_reporter_mcp.utils_ctgov import ctgov_get, clear_ctgov_cache
        clear_ctgov_cache()

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("nih_reporter_mcp.utils_ctgov.httpx.AsyncClient", return_value=mock_client):
            result = run(ctgov_get(
                "https://clinicaltrials.gov/api/v2/studies/NCT99999999"
            ))
        assert result == {"studies": [], "totalCount": 0, "nextPageToken": None}

    def test_timeout_raises_runtime_error(self):
        import httpx as _httpx
        from nih_reporter_mcp.utils_ctgov import ctgov_get, clear_ctgov_cache
        clear_ctgov_cache()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("nih_reporter_mcp.utils_ctgov.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="timed out"):
                run(ctgov_get(
                    "https://clinicaltrials.gov/api/v2/studies/NCT04057716"
                ))

    def test_oversized_response_rejected(self):
        from nih_reporter_mcp.utils_ctgov import ctgov_get, clear_ctgov_cache
        clear_ctgov_cache()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"x" * (6 * 1024 * 1024)  # 6 MB > 5 MB cap
        mock_resp.json.return_value = {}
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("nih_reporter_mcp.utils_ctgov.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="too large"):
                run(ctgov_get(
                    "https://clinicaltrials.gov/api/v2/studies/NCT04057716"
                ))

    def test_400_raises_value_error(self):
        from nih_reporter_mcp.utils_ctgov import ctgov_get, clear_ctgov_cache
        clear_ctgov_cache()

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("nih_reporter_mcp.utils_ctgov.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="400"):
                run(ctgov_get(
                    "https://clinicaltrials.gov/api/v2/studies/bad"
                ))

    def test_wrong_host_rejected(self):
        from nih_reporter_mcp.utils_ctgov import ctgov_get
        with pytest.raises(ValueError, match="not in allowed set"):
            run(ctgov_get("https://evil.example.com/api/v2/studies"))


class TestCountingDiscipline:
    """Verify distinct_trials and distinct_relationships are correct."""

    def test_dedup_nct_ids(self):
        from nih_reporter_mcp.ct_parsing import parse_trial as _parse_trial
        from nih_reporter_mcp.models import ClinicalTrialsResult

        # Simulate two studies with the same NCT ID
        study = {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT04057716",
                    "secondaryIdInfos": [
                        {"id": "R01HL147914", "type": "NIH"},
                        {"id": "R01HL999999", "type": "NIH"},
                    ],
                },
                "statusModule": {},
                "designModule": {},
                "sponsorCollaboratorsModule": {},
            }
        }
        trial = _parse_trial(study, "source_asserted")
        assert trial.nct_id == "NCT04057716"
        assert len(trial.nih_grant_ids) == 2
        # Two grant↔trial relationships for one trial
        rels = {(gid, trial.nct_id) for gid in trial.nih_grant_ids}
        assert len(rels) == 2

    def test_no_dollar_fields_on_trials(self):
        """LinkedTrial must NOT have any dollar/amount/funding fields."""
        from nih_reporter_mcp.models import LinkedTrial
        field_names = set(LinkedTrial.model_fields.keys())
        dollar_keywords = {"amount", "funding", "dollar", "cost", "budget"}
        leaks = {f for f in field_names if any(k in f.lower() for k in dollar_keywords)}
        assert leaks == set(), f"LinkedTrial has dollar-related fields: {leaks}"
