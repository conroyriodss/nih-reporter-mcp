"""Contract: the Ask agent's FINAL answer carries the interpretation boundaries.

The evaluation and slides state four boundaries: an excluded orphan subproject
means award-family investment may be missing; an incomplete retrieval is not a
complete total; a keyword cohort is not an official RCDC spending-category
total; and some questions (duration ranking, trainee/workforce outcomes,
government-wide spending shares) are unsupported and must be declined.

These tests drive the real Ask loop (``web_app._run_agent``) end to end with a
scripted model that deliberately OMITS every caveat, and the real MCP server
in-process with RePORTER replaced by frozen or synthetic records at the
raw-fetch boundary (no network). Each test then asserts the answer the user
would see still carries the boundary, with no human repairing it. A boundary
that lives only in docs or prompts the Ask loop never loads fails here.

Controls check that clean answers, including the two benchmark questions, are
returned byte-for-byte unchanged, and that an answer which already states a
caveat is not given a duplicate.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "docs/demonstration_fixture/raw_records.json").read_text())


# -- scripted model -----------------------------------------------------------
class ScriptedLLM:
    """Stands in for the OpenAI client. Each step is ('tool', name, args) or ('answer', text)."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = []  # messages sent on each completion request
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools=None, tool_choice=None, **kw):
        self.calls.append(json.loads(json.dumps(messages, default=str)))
        kind, *rest = self.steps.pop(0)
        if kind == "tool":
            name, args = rest
            tc = SimpleNamespace(id=f"call_{len(self.calls)}",
                                 function=SimpleNamespace(name=name, arguments=json.dumps(args)))
            msg = SimpleNamespace(content=None, tool_calls=[tc])
        else:
            msg = SimpleNamespace(content=rest[0], tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


# -- frozen / synthetic RePORTER at the raw-fetch boundary --------------------
def _records(n, *, fy=2023, amount=1000):
    return [{"appl_id": 90_000_000 + i, "subproject_id": None, "fiscal_year": fy,
             "award_amount": amount, "core_project_num": f"R01XX{i:06d}",
             "organization": {"org_name": f"Org {i % 7}"},
             "agency_ic_admin": {"abbreviation": "NIA"}} for i in range(n)]


def _replay(records, total=None):
    total = len(records) if total is None else total

    async def post_json(url, payload):
        off, lim = payload.get("offset", 0), payload.get("limit", 500)
        return {"meta": {"total": total, "offset": off, "limit": lim},
                "results": [dict(r) for r in records[off:off + lim]]}
    return post_json


@pytest.fixture(scope="module")
def web_app():
    # Import without any Databricks credentials: the SDK client must not authenticate here.
    mp = pytest.MonkeyPatch()
    for k in [k for k in __import__("os").environ if k.startswith("DATABRICKS_")]:
        mp.delenv(k, raising=False)
    mp.setenv("DATABRICKS_CONFIG_FILE", str(ROOT / "nonexistent.databrickscfg"))
    mp.setenv("NIH_MCP_CACHE_DISABLED", "1")
    mod = importlib.import_module("nih_reporter_mcp.web_app")
    yield mod
    mp.undo()


def ask(web_app, question, steps, records=None, total=None):
    """Run the real Ask loop with a scripted model and the real in-process MCP server."""
    import fastmcp
    import openai
    from nih_reporter_mcp.app import mcp

    llm = ScriptedLLM(steps)
    real_client = fastmcp.Client
    with patch.object(web_app, "_get_token", return_value="test-token"), \
         patch.object(web_app, "DB_HOST", "https://example.invalid"), \
         patch.object(openai, "OpenAI", lambda **kw: llm), \
         patch.object(fastmcp, "Client", lambda url: real_client(mcp)), \
         patch("nih_reporter_mcp.utils.post_json", new=_replay(records or [], total)):
        out = asyncio.run(web_app._run_agent(question, "scripted-model"))
    return out, llm


# -- 1. the rules are in the ACTUAL system message the model receives ---------
def test_system_message_carries_the_four_boundaries(web_app):
    _, llm = ask(web_app, "How much did NIH spend on R01s in FY2023?", [("answer", "ok")])
    system = next(m["content"] for m in llm.calls[0] if m["role"] == "system")
    assert re.search(r"subproject", system, re.I) and re.search(r"parent", system, re.I), system
    assert re.search(r"complete", system, re.I) and "10,000" in system, system
    assert re.search(r"keyword|text[- ]search", system, re.I) and re.search(r"RCDC|spending categor", system, re.I), system
    assert re.search(r"declin|unsupported|not supported", system, re.I), system


# -- 2. orphan exclusion survives (real tool on the frozen CRISPR fixture) -----
def test_orphan_exclusion_survives_the_agent(web_app):
    out, _ = ask(web_app, "How much did NIH spend on CRISPR sickle cell research in FY2024?",
                 [("tool", "summarize_funding_by_topic", {"topic": "CRISPR sickle cell", "fiscal_years": [2024]}),
                  ("answer", "NIH spent $19,790,134 on CRISPR sickle cell research in FY2024 across 37 projects.")],
                 records=FIXTURE["results"], total=FIXTURE["meta"]["total"])
    a = out["answer"]
    assert "$19,790,134" in a, "the model's figure must be kept, not replaced"
    assert re.search(r"\b1\b[^.]{0,40}subproject", a, re.I), a
    assert re.search(r"parent", a, re.I) and re.search(r"may be missing|not reflected|may not reflect", a, re.I), a


# -- 3. incomplete retrieval survives (real tool, 14,000 matches, 10,000 ceiling) --
def test_incomplete_retrieval_survives_the_agent(web_app):
    out, _ = ask(web_app, "What was total R01 funding in FY2023?",
                 [("tool", "summarize_funding_by_topic", {"activity_codes": ["R01"], "fiscal_years": [2023]}),
                  ("answer", "Total R01 funding in FY2023 was $10,000,000.")],
                 records=_records(14_000), total=14_000)
    a = out["answer"]
    assert "10,000" in a and "14,000" in a, a
    assert re.search(r"lower bound|not (a )?complete|incomplete", a, re.I), a


# -- 4. keyword cohort is not an RCDC total (real tool, complete cohort) -------
def test_keyword_scope_survives_the_agent(web_app):
    out, _ = ask(web_app, "How much did NIH spend on Alzheimer's disease in FY2023?",
                 [("tool", "summarize_funding_by_topic", {"topic": "Alzheimer's disease", "fiscal_years": [2023]}),
                  ("answer", "NIH spent $5,000 on Alzheimer's disease in FY2023.")],
                 records=_records(5), total=5)
    a = out["answer"]
    assert re.search(r"keyword|text[- ]search", a, re.I), a
    assert re.search(r"RCDC|spending[- ]categor", a, re.I) and re.search(r"\bnot\b", a, re.I), a
    # the cohort is complete with no subprojects: no other caveat should be invented
    assert not re.search(r"lower bound|subproject", a, re.I), a


# -- 5. unsupported questions are declined, not answered ----------------------
@pytest.mark.parametrize("question, fabricated", [
    ("Which R01 has run the longest?", "R01GM012345 is the longest-running R01, active since 1975."),
    ("What happened to NIH-funded trainees after their fellowships?", "Most NIH-funded trainees became professors."),
    ("What is NIH's share of all federal cancer spending?", "NIH accounts for 71% of all federal cancer spending."),
])
def test_unsupported_question_is_declined(web_app, question, fabricated):
    out, _ = ask(web_app, question, [("answer", fabricated)])
    a = out["answer"]
    assert fabricated not in a, "an unsupported claim must not reach the user"
    assert re.search(r"not supported|does not support|cannot answer", a, re.I), a


# -- controls -----------------------------------------------------------------
def test_clean_answer_is_unchanged(web_app):
    text = "Total R01 funding in FY2023 was $5,000 across 5 projects."
    out, _ = ask(web_app, "What was total R01 funding in FY2023?",
                 [("tool", "summarize_funding_by_topic", {"activity_codes": ["R01"], "fiscal_years": [2023]}),
                  ("answer", text)], records=_records(5), total=5)
    assert out["answer"] == text


@pytest.mark.parametrize("question, text", [
    ("What was the largest single NIH award in FY2020-2025?",
     "The largest NIH/HHS award record in FY2020–FY2025 was $448,283,318 (OT2HL161847, FY2021)."),
    ("How many R01 awards in FY2020 were competitive renewals?",
     "1,089 R01 awards in FY2020 were competitive renewals, out of 29,560."),
])
def test_benchmark_questions_are_not_altered(web_app, question, text):
    out, _ = ask(web_app, question, [("answer", text)])
    assert out["answer"] == text


def test_caveat_already_present_is_not_duplicated(web_app):
    text = ("NIH spent $19,790,134 in FY2024. One subproject was excluded because its parent award was not "
            "in the cohort, so associated award-family investment may be missing. This is a keyword "
            "(text-search) cohort, not an official RCDC spending-category total.")
    out, _ = ask(web_app, "How much did NIH spend on CRISPR sickle cell research in FY2024?",
                 [("tool", "summarize_funding_by_topic", {"topic": "CRISPR sickle cell", "fiscal_years": [2024]}),
                  ("answer", text)], records=FIXTURE["results"], total=FIXTURE["meta"]["total"])
    assert out["answer"] == text


def test_response_reports_which_boundaries_fired(web_app):
    out, _ = ask(web_app, "How much did NIH spend on CRISPR sickle cell research in FY2024?",
                 [("tool", "summarize_funding_by_topic", {"topic": "CRISPR sickle cell", "fiscal_years": [2024]}),
                  ("answer", "NIH spent $19,790,134.")],
                 records=FIXTURE["results"], total=FIXTURE["meta"]["total"])
    fired = {b["id"]: b["added_by_guard"] for b in out["boundaries"]}
    assert fired == {"orphan_exclusion": True, "keyword_scope": True}, out["boundaries"]
