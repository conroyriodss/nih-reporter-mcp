"""clinical_trials_lookup — find clinical trials linked to NIH grants.

Parsing helpers are in ct_parsing.py (no fastmcp dependency) for testability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from nih_reporter_mcp.config import PROJECTS_SEARCH
from nih_reporter_mcp.ct_parsing import extract_grants, parse_trial
from nih_reporter_mcp.models import (
    DOLLAR_ATTRIBUTION_NOTE,
    EVIDENCE_CLASS_CANDIDATE,
    EVIDENCE_CLASS_SOURCE_ASSERTED,
    GRANT_TRIAL_BOUNDARY_NOTE,
    ClinicalTrialsResult,
    LinkedTrial,
)
from nih_reporter_mcp.utils import post_json, validate_string_length
from nih_reporter_mcp.utils_ctgov import (
    search_studies_by_condition,
    search_studies_by_grant,
)


async def _resolve_grant_to_project_nums(core_project_num: str) -> list[str]:
    """Fetch all project_num variants from RePORTER for a core_project_num."""
    try:
        payload = {
            "criteria": {"project_nums": [core_project_num]},
            "include_fields": ["ProjectNum"],
            "offset": 0,
            "limit": 50,
        }
        data = await post_json(PROJECTS_SEARCH, payload)
        results = data.get("results") or []
        return list({r["project_num"] for r in results if r.get("project_num")})
    except Exception:
        return []


def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def clinical_trials_lookup(
        core_project_num: Annotated[str | None, Field(
            description=(
                "NIH core project number (e.g. 'R01HL147914'). "
                "Searches ClinicalTrials.gov for trials that cite this grant. "
                "Uses exact-match; falls back to full project_num variants "
                "from RePORTER if the core number yields no results."
            ),
        )] = None,
        condition: Annotated[str | None, Field(
            description=(
                "Disease or condition to search for linked trials "
                "(e.g. 'sickle cell disease'). Returns up to 20 trials. "
                "Results have evidence_class='candidate' (condition match, "
                "not structural grant assertion)."
            ),
        )] = None,
    ) -> ClinicalTrialsResult:
        """Find clinical trials linked to NIH grants or matching a condition.

        For grant lookups: returns trials whose registration record
        structurally declares the NIH grant (evidence_class='source_asserted').
        The type field reliably distinguishes NIH from FDA and other funders —
        an R01-shaped identifier is NOT automatically NIH.

        For condition lookups: returns matching trials with their grant
        linkages (evidence_class='candidate' since the link is inferred
        from a condition search, not a direct grant assertion).

        NEVER multiplies grant funding across linked trials. No dollar
        figures are attributed to trials.
        """
        if not core_project_num and not condition:
            raise ValueError(
                "Provide either core_project_num (grant lookup) "
                "or condition (condition search)."
            )
        if core_project_num and condition:
            raise ValueError(
                "Provide core_project_num OR condition, not both. "
                "Grant lookup and condition search have different "
                "evidence classes and should not be mixed."
            )

        ts = datetime.now(timezone.utc).isoformat()
        variants_tried: list[str] = []

        if core_project_num:
            core_project_num = validate_string_length(
                core_project_num, "core_project_num",
            )
            query_type = "grant"
            query_value = core_project_num

            # Phase 1: try core project number
            variants_tried.append(core_project_num)
            studies = await search_studies_by_grant(core_project_num)

            # Phase 2: fallback to full project_num variants from RePORTER
            if not studies:
                pnums = await _resolve_grant_to_project_nums(core_project_num)
                for pn in pnums:
                    if pn == core_project_num:
                        continue
                    variants_tried.append(pn)
                    studies = await search_studies_by_grant(pn)
                    if studies:
                        break

            evidence_class = EVIDENCE_CLASS_SOURCE_ASSERTED
        else:
            assert condition is not None
            condition = validate_string_length(condition, "condition")
            query_type = "condition"
            query_value = condition
            studies = await search_studies_by_condition(condition)
            evidence_class = EVIDENCE_CLASS_CANDIDATE

        # Parse results
        seen_ncts: set[str] = set()
        trials: list[LinkedTrial] = []
        relationships: set[tuple[str, str]] = set()

        for study in studies:
            trial = parse_trial(study, evidence_class)
            if trial.nct_id in seen_ncts:
                continue
            seen_ncts.add(trial.nct_id)
            trials.append(trial)
            for gid in trial.nih_grant_ids:
                relationships.add((gid, trial.nct_id))

        return ClinicalTrialsResult(
            query_type=query_type,
            query_value=query_value,
            grant_id_variants_tried=variants_tried,
            distinct_trials=len(seen_ncts),
            distinct_relationships=len(relationships),
            trials=trials,
            boundary_note=GRANT_TRIAL_BOUNDARY_NOTE,
            dollar_attribution_note=DOLLAR_ATTRIBUTION_NOTE,
            retrieved_at=ts,
        )
