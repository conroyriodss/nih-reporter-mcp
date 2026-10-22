# Architecture

## System Overview

```mermaid
graph TB
    subgraph Clients["MCP Clients"]
        NB["Databricks Notebook<br/>(OpenAI SDK + fastmcp)"]
        EXT["Any MCP-compatible<br/>AI agent"]
    end

    subgraph Server["NIH RePORTER MCP Server (FastMCP + Starlette)"]
        direction TB

        subgraph Tools["14 Tools"]
            direction LR
            T1["search_funded_projects"]
            T2["summarize_funding_by_topic"]
            T3["funding_trend_by_year"]
            T4["organization_funding_profile"]
            T5["get_project_by_id"]
            T6["check_investigator_portfolio"]
            T7["get_project_publications"]
            T8["get_publication_details"]
            T9["check_investigator_overlap"]
            T10["funded_projects_by_study_section"]
            T11["search_recent_awards"]
            T12["export_evidence_bundle"]
            T13["explain_health_topic"]
            T14["clinical_trials_lookup"]
        end

        subgraph Prompts["9 Prompts (3 audiences)"]
            direction LR
            P1["Program Officer<br/>(portfolio_review,<br/>overlap_screening,<br/>study_section_analysis)"]
            P2["Citizen Scientist<br/>(funding_overview,<br/>health_topic_explainer,<br/>spending_comparison)"]
            P3["PI/PD<br/>(landscape_analysis,<br/>peer_benchmarking,<br/>trend_analysis)"]
        end

        subgraph Resources["3 Resources + 2 Routes"]
            R1["spending_categories<br/>(RCDC list)"]
            R2["server_info<br/>(version, capabilities)"]
            R3["response_guidelines"]
            RT1["GET /health"]
            RT2["GET /version"]
        end

        subgraph Core["Core Layer"]
            direction LR
            AGG["aggregate_funding()<br/>whole_award / all_records<br/>dedup · subproject exclusion<br/>null-amount tracking"]
            PAG["paginate_all()<br/>distinct-ID completeness<br/>10K retrieval cap"]
            CACHE["Response Cache<br/>15-min TTL<br/>basis-keyed (no collision)"]
        end

        subgraph Provenance["Provenance Layer"]
            direction LR
            PROV["Provenance metadata<br/>query_criteria · source_record_ids<br/>records_aggregated · id_conflicts<br/>subproject_excluded_count<br/>records_with_missing_amount"]
            REPRO["Reproduction note<br/>5-step numbered procedure"]
        end
    end

    subgraph Upstream["Upstream APIs"]
        API1["NIH RePORTER v2<br/>api.reporter.nih.gov<br/>(projects/search)"]
        API2["NCBI E-utilities<br/>eutils.ncbi.nlm.nih.gov<br/>(esummary, elink)"]
        API3["MedlinePlus<br/>wsearch.nlm.nih.gov<br/>(health topics)"]
    end

    subgraph Eval["Evaluation & Verification"]
        direction LR
        UT["38 unit tests<br/>+ 2 xfailed"]
        SM["17 smoke tests<br/>(live API)"]
        CT["5 correctness tests<br/>(ground truth)"]
        FX["Frozen fixture<br/>decision_ledger.csv<br/>SHA-256 tamper check<br/>3-way dollar match"]
    end

    NB -->|"SSE / MCP protocol"| Server
    EXT -->|"SSE / MCP protocol"| Server

    Tools --> AGG
    Tools --> PAG
    AGG --> CACHE
    PAG --> CACHE
    AGG --> PROV

    CACHE -->|"rate-limited<br/>1.0s / 0.34s / 0.5s"| API1
    CACHE -->|"rate-limited"| API2
    CACHE -->|"rate-limited"| API3

    Eval -.->|"verifies"| Provenance
    FX -.->|"proves"| AGG
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **whole_award as default basis** | Prevents double-counting when a multi-project grant’s parent and subprojects are both retrieved (U19AG068753 fixture). For CRISPR FY2023, all_records exceeds whole_award by 10.1%: a basis difference, not all duplication (166 orphan subprojects) |
| **Provenance on every dollar figure** | Every total carries the exact query, contributing appl_ids, and a reproduction procedure |
| **Basis-keyed cache** | 15-minute TTL; whole_award and all_records are cached independently (no collision, proven by t18) |
| **Rate limiting per upstream** | RePORTER 1.0s, E-utilities 0.34s, MedlinePlus 0.5s — respects API terms of service |
| **10,000-record retrieval cap** | Paginator fetches up to 20 pages × 500; `complete=False` flagged honestly when cap is hit |
| **Audience-tailored prompts** | Same data, different framing: program officer (oversight), citizen scientist (accessibility), PI/PD (benchmarking) |
| **Frozen demonstration fixture** | SHA-256-hashed raw data + decision ledger + independent hand calculation — proves correctness is not aspirational |
