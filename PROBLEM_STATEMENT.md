# Problem Statement

## The core problem: funding claims you cannot inspect

Federal research agencies — NIH, CDC, FDA, AHRQ, and ACF — collectively
award tens of billions of dollars annually. The public data exists in NIH
RePORTER, but turning raw project records into a defensible funding figure
is surprisingly hard. Multi-project grants (U19, P01) list both a parent
award and constituent subprojects, each carrying a dollar amount; when both
are retrieved, naively summing all records double-counts the parent. For
CRISPR gene editing research in FY 2023, summing all records instead of whole
awards gives a total 10.1% — $84.6 million) higher. That is an all_records vs
whole_award basis difference, not all duplication: many excluded subprojects
have no parent in the cohort. Null award amounts, page-boundary duplicates, and a
10,000-record retrieval cap add further distortion. Worse, NIH's official
RCDC spending categories and free-text search return dramatically different
totals for the same topic (4.5× for "long COVID"), with no explanation
surfaced to the user.

Today, when an AI agent reports a funding figure, the user must trust the
number. There is no way to see which records were included, which were
excluded, or why.

## What this server does

NIH RePORTER MCP exposes 14 goal-oriented tools over four upstream APIs
(RePORTER, NCBI E-utilities, MedlinePlus, ClinicalTrials.gov) through the Model Context
Protocol. Every dollar figure carries machine-readable provenance: the
exact query, every contributing record's appl_id, subproject exclusion
counts, deduplication flags, and a numbered reproduction procedure that
independently reproduces the total. A frozen demonstration fixture proves
the arithmetic matches to the dollar.

The server serves three audiences through 9 audience-tailored prompts:
a program officer screening investigator portfolios for overlap,
a citizen scientist exploring what NIH funds in plain language, and
a PI/PD benchmarking their grant against peer awards. The oversight
mission (are dollars counted correctly?) and the service-delivery
mission (can non-experts access this data?) share a single
requirement: every claim must be inspectable.
