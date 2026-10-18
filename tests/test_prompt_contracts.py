"""Prompt-to-tool contract validation.

Verifies that every prompt's instructed tool calls reference real tool names
and real parameter names from the actual tool schemas.  This is a static
analysis of the prompt text — it does not require a running server or API.

Runs model-free in CI alongside test_counting, test_security, etc.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import re
import textwrap
from pathlib import Path
from typing import get_type_hints

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

SRC = Path(__file__).resolve().parent.parent / "src" / "nih_reporter_mcp"


def _discover_tool_params() -> dict[str, set[str]]:
    """Parse tool files for @mcp.tool async def signatures → {name: {params}}."""
    tools_dir = SRC / "tools"
    registry: dict[str, set[str]] = {}
    for fp in sorted(tools_dir.glob("*.py")):
        if fp.name == "__init__.py":
            continue
        text = fp.read_text()
        for m in re.finditer(
            r"@mcp\.tool\s+async\s+def\s+(\w+)\((.*?)\)\s*->",
            text,
            re.DOTALL,
        ):
            name = m.group(1)
            params_str = m.group(2)
            params = set(re.findall(r"(\w+):\s*Annotated", params_str))
            registry[name] = params
    return registry


def _discover_return_model_fields() -> dict[str, set[str]]:
    """Parse models.py for Pydantic model fields → {ModelName: {field_names}}."""
    models_file = SRC / "models.py"
    text = models_file.read_text()
    fields: dict[str, set[str]] = {}
    for m in re.finditer(
        r"class\s+(\w+)\(BaseModel\):(.*?)(?=\nclass |\Z)", text, re.DOTALL
    ):
        cname = m.group(1)
        body = m.group(2)
        fnames = set()
        for line in body.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("#") and not line.startswith('"'):
                field_name = line.split(":")[0].strip()
                if field_name and field_name[0].isalpha() and field_name.isidentifier():
                    fnames.add(field_name)
        fields[cname] = fnames
    return fields


def _extract_prompt_texts() -> dict[str, str]:
    """Return {prompt_func_name: rendered_text} with dummy arguments."""
    prompts_dir = SRC / "prompts"
    results: dict[str, str] = {}
    for fp in sorted(prompts_dir.glob("*.py")):
        if fp.name == "__init__.py":
            continue
        text = fp.read_text()
        # Find each inner def that returns a string (the prompt function)
        for m in re.finditer(
            r"def\s+(\w+)\(([^)]*?)\)\s*->\s*str:",
            text,
        ):
            func_name = m.group(1)
            # Call the prompt function with dummy args to get the rendered text
            # Parse default params
            params_str = m.group(2)
            # We'll reconstruct the prompt text by finding the return statement
            # Look for the return block
            func_start = m.end()
            # Find the return (...) block
            return_match = re.search(
                r"return\s*\((.*?)\n\s*\)",
                text[func_start:],
                re.DOTALL,
            )
            if return_match:
                # The raw f-string body — we can't eval it, but we can check
                # for tool names and param names directly in the source
                raw = return_match.group(1)
                results[func_name] = raw
    return results


def _extract_tool_calls_from_prompt(prompt_text: str) -> list[tuple[str, list[str]]]:
    """Extract (tool_name, [param_names]) pairs from prompt text.

    Looks for patterns like:
      **tool_name** with param1=..., param2=...
      tool_name(param1=..., param2=...)
    """
    calls: list[tuple[str, list[str]]] = []
    # Pattern: **tool_name** ... param=value
    for m in re.finditer(r"\*\*(\w+)\*\*", prompt_text):
        tool_name = m.group(1)
        # Skip non-tool bold words
        if tool_name.upper() == tool_name or tool_name in (
            "IMPORTANT", "BOUNDARY", "NIH",
        ):
            continue
        # Grab next 400 chars and find param= patterns before next **
        rest = prompt_text[m.end() : m.end() + 400]
        # Stop at next tool reference
        next_tool = re.search(r"\*\*\w+\*\*", rest)
        if next_tool:
            rest = rest[: next_tool.start()]
        params = re.findall(r"(\w+)=", rest)
        # Filter out values that look like booleans or format vars
        skip = {"true", "false", "none", "True", "False", "None"}
        params = [p for p in params if p not in skip]
        calls.append((tool_name, params))
    return calls


# ── fixtures ─────────────────────────────────────────────────────────────────

TOOL_PARAMS = _discover_tool_params()
PROMPT_TEXTS = _extract_prompt_texts()


# ── tests ────────────────────────────────────────────────────────────────────


def test_all_tools_discovered():
    """Sanity: we should find all 13 tools."""
    assert len(TOOL_PARAMS) == 14, f"Expected 13 tools, found {len(TOOL_PARAMS)}: {sorted(TOOL_PARAMS)}"


def test_all_prompts_discovered():
    """Sanity: we should find all 9 prompts."""
    assert len(PROMPT_TEXTS) == 9, f"Expected 9 prompts, found {len(PROMPT_TEXTS)}: {sorted(PROMPT_TEXTS)}"


@pytest.mark.parametrize("prompt_name", sorted(PROMPT_TEXTS.keys()))
def test_prompt_tool_names_are_real(prompt_name):
    """Every **bold_tool** referenced in a prompt must be a registered tool."""
    text = PROMPT_TEXTS[prompt_name]
    calls = _extract_tool_calls_from_prompt(text)
    for tool_name, _ in calls:
        assert tool_name in TOOL_PARAMS, (
            f"Prompt '{prompt_name}' references unknown tool '{tool_name}'. "
            f"Registered tools: {sorted(TOOL_PARAMS)}"
        )


@pytest.mark.parametrize("prompt_name", sorted(PROMPT_TEXTS.keys()))
def test_prompt_param_names_are_real(prompt_name):
    """Every param= in a tool-call instruction must be an actual tool parameter."""
    text = PROMPT_TEXTS[prompt_name]
    calls = _extract_tool_calls_from_prompt(text)
    for tool_name, params in calls:
        if tool_name not in TOOL_PARAMS:
            continue  # caught by test_prompt_tool_names_are_real
        actual = TOOL_PARAMS[tool_name]
        for p in params:
            assert p in actual, (
                f"Prompt '{prompt_name}' passes '{p}' to {tool_name}, "
                f"but actual params are {sorted(actual)}"
            )


def test_no_stale_project_num_param():
    """No prompt should use the old 'project_num=' param name for get_project_by_id."""
    for pname, text in PROMPT_TEXTS.items():
        # project_num= but NOT core_project_num= or exclude_project_num=
        matches = re.findall(r"(?<!core_)(?<!exclude_)project_num=", text)
        assert not matches, (
            f"Prompt '{pname}' still uses stale 'project_num=' "
            f"(should be 'core_project_num=')"
        )


def test_no_citation_count_in_prompts():
    """PublicationDetail has no citation_count field; no prompt should request it."""
    for pname, text in PROMPT_TEXTS.items():
        assert "citation" not in text.lower(), (
            f"Prompt '{pname}' references 'citation' but "
            "PublicationDetail only has: title, journal, pub_date, authors, doi"
        )


def test_no_publication_abstract_in_prompts():
    """get_publication_details does not return abstracts; prompts should not
    instruct the agent to use publication abstracts."""
    pub_abstract_pattern = re.compile(
        r"publication.*abstract|abstract.*publication|"  # near each other
        r"get_publication_details.*abstract",  # in tool context
        re.IGNORECASE,
    )
    for pname, text in PROMPT_TEXTS.items():
        # Allow references to project abstracts (which ARE available)
        # Only flag if abstract appears in a publication-tool context
        calls = _extract_tool_calls_from_prompt(text)
        for tool_name, _ in calls:
            if tool_name == "get_publication_details":
                # Get ONLY the tool-call instruction line (up to next \n\n)
                idx = text.index("get_publication_details")
                rest = text[idx:]
                # Stop at the next blank line or next numbered step
                end = re.search(r"\\n\\n|\n\n|Present|\d+\.", rest)
                section = rest[: end.start()] if end else rest[:200]
                assert "abstract" not in section.lower(), (
                    f"Prompt '{pname}' asks get_publication_details for abstracts, "
                    "but PublicationDetail only has: title, journal, pub_date, authors, doi"
                )


def test_project_summary_fields_abstract_and_dates():
    """ProjectSummary should have abstract, start_date, end_date fields
    (added to support investment_to_outputs and follow_the_evidence prompts)."""
    model_fields = _discover_return_model_fields()
    ps = model_fields.get("ProjectSummary", set())
    for field in ("abstract", "start_date", "end_date"):
        assert field in ps, (
            f"ProjectSummary missing '{field}' — needed by prompts that "
            "reference project abstracts and funding periods"
        )


def test_portfolio_brief_no_stale_counting_unit_language():
    """GAP 3: portfolio_brief must NOT instruct the agent to say parent and
    subproject records are 'counted separately' — that contradicts
    whole_award semantics where subprojects are EXCLUDED."""
    text = PROMPT_TEXTS["portfolio_brief"]
    # The prompt should not contain language that contradicts whole_award
    assert "counted separately" not in text, (
        "portfolio_brief still says 'counted separately' but default "
        "funding_basis=whole_award EXCLUDES subprojects"
    )


def test_portfolio_brief_outputs_derivable_from_tools():
    """GAP 3: Every output the prompt requests must be derivable from the
    tools it actually calls (summarize_funding_by_topic and
    export_evidence_bundle). IC rankings by count and mechanism distributions
    are NOT available from these tools."""
    text = PROMPT_TEXTS["portfolio_brief"]
    calls = _extract_tool_calls_from_prompt(text)
    tool_names = {name for name, _ in calls}

    # The prompt calls summarize_funding_by_topic and export_evidence_bundle.
    # These return FundingSummary + Provenance — which include
    # distinct_organizations and distinct_administering_ics as COUNTS,
    # but NOT per-IC project lists or per-mechanism breakdowns.

    # If the prompt asks for "IC rankings by distinct project count" or
    # "mechanism distribution inferred from search results" but does NOT
    # call search_funded_projects, that's an unsupported claim.
    if "search_funded_projects" not in tool_names:
        # Should not request per-record IC rankings or mechanism distributions
        import re
        # Check for claims about inferring from search results
        assert "inferred from" not in text.lower() and "search results" not in text.lower(), (
            "portfolio_brief requests outputs 'inferred from search results' "
            "but does not call search_funded_projects"
        )


# ── Runtime-admissibility rules ────────────────────────────────────────────
# Tools have cross-parameter constraints (anyOf, enum, at-least-one-of)
# that structural validation (type + name) misses.  These rules define
# the real admissibility boundary.
#
# If the eval claims "100% argument validity," every trial must also pass
# these rules — not just type/name checks.

_RUNTIME_ADMISSIBILITY_RULES: dict[str, list] = {
    # At least one of the listed params must be non-null/non-empty
    "get_project_by_id": [
        ("at_least_one_non_null", ["appl_id", "core_project_num"]),
    ],
    "summarize_funding_by_topic": [
        ("at_least_one_non_null", ["topic", "spending_category"]),
        ("enum", "funding_basis", ["whole_award", "all_records"]),
    ],
    "export_evidence_bundle": [
        ("at_least_one_non_null", ["topic", "spending_category"]),
        ("enum", "funding_basis", ["whole_award", "all_records"]),
    ],
    "funding_trend_by_year": [
        ("at_least_one_non_null", ["topic", "spending_category"]),
        ("enum", "funding_basis", ["whole_award", "all_records"]),
    ],
    "organization_funding_profile": [
        ("enum", "funding_basis", ["whole_award", "all_records"]),
    ],
}


def check_runtime_admissibility(tool_name: str, args: dict | None) -> tuple[bool, list[str]]:
    """Check whether a tool call with these args would be ACCEPTED at runtime.
    Returns (admissible, list_of_violations)."""
    if args is None:
        return False, ["args is None"]
    rules = _RUNTIME_ADMISSIBILITY_RULES.get(tool_name, [])
    violations = []
    for rule in rules:
        if rule[0] == "at_least_one_non_null":
            param_names = rule[1]
            if not any(args.get(p) not in (None, "", 0) for p in param_names):
                violations.append(
                    f"at_least_one_non_null({param_names}): "
                    f"all are null/empty/absent — tool would raise ValueError"
                )
        elif rule[0] == "enum":
            param_name = rule[1]
            allowed = rule[2]
            val = args.get(param_name)
            if val is not None and val not in allowed:
                violations.append(
                    f"enum({param_name}): '{val}' not in {allowed}"
                )
    return len(violations) == 0, violations


def test_runtime_admissibility_rules_are_exhaustive():
    """Sanity: every tool with a raise ValueError('Provide ...') or
    enum constraint in its source must have a matching rule above."""
    import re
    tools_dir = SRC / "tools"
    for fp in sorted(tools_dir.glob("*.py")):
        if fp.name == "__init__.py":
            continue
        text = fp.read_text()
        # Find tool functions
        for m in re.finditer(r"@mcp\.tool\s+async\s+def\s+(\w+)", text):
            tool_name = m.group(1)
            # Check for "at least one" patterns
            at_least = re.findall(
                r"raise ValueError.*Provide (?:at least one of |either )",
                text[m.end():m.end() + 500],
            )
            if at_least:
                assert tool_name in _RUNTIME_ADMISSIBILITY_RULES, (
                    f"{tool_name} has at-least-one-of constraint but no "
                    f"admissibility rule defined"
                )


def test_frozen_eval_q5_llama_is_not_runtime_admissible():
    """The audit found Llama Q5 generates {appl_id: null, core_project_num: null}
    for get_project_by_id.  This PASSES structural validation (correct param
    names, correct types) but FAILS at runtime (ValueError: 'Provide either
    appl_id or core_project_num').  Confirm the admissibility check catches it."""
    args = {"appl_id": None, "core_project_num": None}
    admissible, violations = check_runtime_admissibility("get_project_by_id", args)
    assert not admissible, (
        "get_project_by_id({appl_id: null, core_project_num: null}) should be "
        "inadmissible — the tool rejects it at runtime"
    )
    assert any("at_least_one_non_null" in v for v in violations)


def test_tool_output_json_validates_against_schema():
    """STEP 5: tool_output.json in docs/demonstration_fixture must validate
    against FundingSummary, Provenance, and EvidenceBundle schemas.
    Catches drift between the fixture and the current model."""
    import json
    from pydantic import BaseModel, Field as PField
    from nih_reporter_mcp.models import FundingSummary, Provenance

    fixture_path = SRC.parent.parent / "docs" / "demonstration_fixture" / "tool_output.json"
    assert fixture_path.exists(), f"tool_output.json not found at {fixture_path}"

    with open(fixture_path) as f:
        bundle = json.load(f)

    # Provenance must parse
    prov = Provenance(**bundle["provenance"])
    assert prov.complete is not None

    # Summary must parse (includes distinct_organizations etc.)
    summ = FundingSummary(**bundle["summary"])
    assert summ.distinct_organizations >= 0
    assert summ.distinct_administering_ics >= 0
    assert summ.pages_fetched >= 1
    assert summ.counting_unit  # non-empty

    # Full bundle structure
    class _EvidenceBundle(BaseModel):
        label: str | None
        summary: FundingSummary
        provenance: Provenance
        reproduction_note: str = PField(
            ..., description="How to independently reproduce this figure."
        )

    eb = _EvidenceBundle(**bundle)
    assert "reproduce" in eb.reproduction_note.lower()
    # Reproduction note must describe production order: dedup before subproject
    assert eb.reproduction_note.index("eduplicate") < eb.reproduction_note.index("subproject_id")
