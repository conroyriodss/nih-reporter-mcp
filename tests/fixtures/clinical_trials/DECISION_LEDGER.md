# Clinical Trials Linkage — Decision Ledger

Verified 2026-10-18 via live ClinicalTrials.gov v2 API probes.

## Verified field paths

| Data | JSON path |
|---|---|
| NCT ID | `protocolSection.identificationModule.nctId` |
| Grant IDs (primary) | `protocolSection.identificationModule.secondaryIdInfos[]` |
| Grant IDs (alt) | `protocolSection.identificationModule.orgStudyIdInfo` |
| Type discriminator | `.type` on either ID object (`NIH`, `OTHER_GRANT`, `OTHER`, `REGISTRY`, `EUDRACT_NUMBER`) |
| Funder domain | `.domain` (present on `OTHER_GRANT` and `OTHER`) |
| RePORTER link | `.link` (present only on `type=="NIH"`) |
| Study type | `protocolSection.designModule.studyType` (`INTERVENTIONAL` / `OBSERVATIONAL`) |
| Start date | `protocolSection.statusModule.startDateStruct.{date,type}` |
| Completion date | `protocolSection.statusModule.completionDateStruct.{date,type}` |
| Enrollment | `protocolSection.designModule.enrollmentInfo.{count,type}` |
| Sponsor | `protocolSection.sponsorCollaboratorsModule.leadSponsor.{name,class}` |
| NIH collaborators | `protocolSection.sponsorCollaboratorsModule.collaborators[]` where `class=="NIH"` |

## NIH vs FDA disambiguation

The `type` field on `secondaryIdInfos` / `orgStudyIdInfo` is the sole reliable
discriminator. An R01-shaped identifier (e.g. from FDA) will have
`type="OTHER_GRANT"`, not `type="NIH"`. Verified on:

- NCT04057716: R01HL147914 → `type="NIH"` ✓
- NCT07178743: 75F40122C00181 → `type="OTHER_GRANT"`, domain="FDA" ✓
- NCT04449510: 5U54HL147127-09 → `type="NIH"` (NIH grant on FDA-collaborator study) ✓

**Rule: filter on `type == "NIH"` — necessary and sufficient.**

## Reverse lookup (grant → trials)

- RePORTER v2 has NO clinical trial linkage fields (confirmed: 45 fields, none CT-related).
- No `/v2/clinical_studies/search` or `/v2/projects/linked` endpoints exist.
- ClinicalTrials.gov `query.id` is the only live API path. It does **exact match**.
- Core project number may fail (R01DK081406 → 0 results); full project_num works
  (1R01DK081406-01A1 → 1 result). Tool implements fallback via RePORTER project_num variants.

## Counting discipline

- `distinct_trials`: count of unique NCT IDs
- `distinct_relationships`: count of unique (grant_id, nct_id) pairs
- Dollar figures are NEVER attributed to trials (would double-count)

## Both ID locations must be checked

NCT01005173 puts its NIH grant in `orgStudyIdInfo`, not `secondaryIdInfos`.
The parser unions both.
