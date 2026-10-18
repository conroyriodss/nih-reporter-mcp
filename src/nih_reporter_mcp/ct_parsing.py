"""Clinical trials parsing helpers — no fastmcp dependency.

Separated from tools/clinical_trials.py so unit tests can import
these without requiring fastmcp to be installed.
"""

from __future__ import annotations

from nih_reporter_mcp.models import (
    EVIDENCE_CLASS_SOURCE_ASSERTED,
    LinkedGrant,
    LinkedTrial,
    TrialDatePair,
)


def extract_grants(study: dict) -> list[LinkedGrant]:
    """Extract all grant IDs from a CT.gov v2 study record."""
    grants: list[LinkedGrant] = []
    id_mod = study.get("protocolSection", {}).get("identificationModule", {})

    # 1. orgStudyIdInfo (sometimes has the NIH grant as the primary ID)
    org_id = id_mod.get("orgStudyIdInfo") or {}
    if org_id.get("id") and org_id.get("type"):
        grants.append(LinkedGrant(
            grant_id=org_id["id"],
            id_type=org_id["type"],
            id_source="orgStudyIdInfo",
            is_nih=org_id["type"] == "NIH",
            domain=org_id.get("domain"),
            reporter_link=org_id.get("link"),
        ))

    # 2. secondaryIdInfos (the primary source for typed grant IDs)
    for sid in id_mod.get("secondaryIdInfos") or []:
        if not sid.get("id"):
            continue
        sid_type = sid.get("type", "UNKNOWN")
        grants.append(LinkedGrant(
            grant_id=sid["id"],
            id_type=sid_type,
            id_source="secondaryIdInfos",
            is_nih=sid_type == "NIH",
            domain=sid.get("domain"),
            reporter_link=sid.get("link"),
        ))

    return grants


def parse_date_pair(
    module: dict, start_key: str, completion_key: str,
) -> tuple[TrialDatePair, TrialDatePair]:
    """Parse estimated/actual date pairs from CT.gov statusModule."""
    def _extract(struct: dict | None) -> tuple[str | None, str | None]:
        if not struct:
            return None, None
        date_val = struct.get("date")
        date_type = struct.get("type")
        if date_type == "ACTUAL":
            return None, date_val
        else:
            return date_val, None

    start_est, start_act = _extract(module.get(start_key))
    comp_est, comp_act = _extract(module.get(completion_key))

    return (
        TrialDatePair(estimated=start_est, actual=start_act),
        TrialDatePair(estimated=comp_est, actual=comp_act),
    )


def parse_trial(study: dict, evidence_class: str) -> LinkedTrial:
    """Parse a CT.gov v2 study into a LinkedTrial."""
    proto = study.get("protocolSection", {})
    id_mod = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    design_mod = proto.get("designModule", {})
    sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
    enrollment_mod = design_mod.get("enrollmentInfo", {})

    nct_id = id_mod.get("nctId", "UNKNOWN")
    grants = extract_grants(study)
    nih_ids = [g.grant_id for g in grants if g.is_nih]

    lead = sponsor_mod.get("leadSponsor", {})
    collabs = sponsor_mod.get("collaborators") or []
    nih_collabs = [c["name"] for c in collabs if c.get("class") == "NIH"]

    start_date, completion_date = parse_date_pair(
        status_mod, "startDateStruct", "completionDateStruct",
    )

    return LinkedTrial(
        nct_id=nct_id,
        brief_title=id_mod.get("briefTitle"),
        overall_status=status_mod.get("overallStatus"),
        study_type=design_mod.get("studyType"),
        phases=design_mod.get("phases") or [],
        lead_sponsor=lead.get("name"),
        lead_sponsor_class=lead.get("class"),
        nih_collaborators=nih_collabs,
        start_date=start_date,
        completion_date=completion_date,
        enrollment=enrollment_mod.get("count"),
        enrollment_type=enrollment_mod.get("type"),
        linked_grants=grants,
        nih_grant_ids=nih_ids,
        evidence_class=evidence_class,
        clinicaltrials_url=f"https://clinicaltrials.gov/study/{nct_id}",
    )
