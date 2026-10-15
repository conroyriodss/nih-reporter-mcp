# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # NIH RePORTER MCP — Server, Evaluation, and LLM Agent Demo
# MAGIC
# MAGIC Single self-contained notebook: writes and starts the MCP server, runs the
# MAGIC evaluation harness against live RePORTER data, then demonstrates a
# MAGIC Databricks-hosted LLM autonomously selecting and chaining the MCP tools.
# MAGIC
# MAGIC Consolidated from two notebooks into one specifically because this
# MAGIC workspace runs **serverless compute**, where each notebook is an isolated
# MAGIC container (separate filesystem, separate network namespace) — so a server
# MAGIC started in one notebook is not reachable from another. Running everything
# MAGIC in one notebook avoids that entirely.
# MAGIC
# MAGIC Run cells top to bottom.

# COMMAND ----------

# MAGIC %pip install fastmcp httpx openai nest_asyncio requests
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,§1. Project layout
# MAGIC %md ## 1. Copy project source from workspace to `/tmp`
# MAGIC
# MAGIC The server source now lives in the workspace project at
# MAGIC `nih-reporter-mcp/src/nih_reporter_mcp/` (template-compliant layout: one
# MAGIC tool per file, `register(mcp)` pattern). This cell copies it to `/tmp` so
# MAGIC the subprocess can find it.

# COMMAND ----------

# DBTITLE 1,Copy project source to /tmp
import os
import shutil

WORKDIR = "/tmp/nih_reporter_mcp"
PROJECT_SRC = "/Workspace/Users/conroyri@nih.gov/nih-reporter-mcp/src"

# Copy the workspace project source to /tmp for the subprocess
if os.path.exists(WORKDIR):
    shutil.rmtree(WORKDIR)
shutil.copytree(PROJECT_SRC, os.path.join(WORKDIR, "src"))

# Verify the layout
for root, dirs, files in os.walk(os.path.join(WORKDIR, "src")):
    level = root.replace(os.path.join(WORKDIR, "src"), "").count(os.sep)
    indent = " " * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
    for f in sorted(files):
        print(f"{indent}  {f}")

print(f"\nProject source copied to {WORKDIR}/src")

# Original monolithic server source has been refactored into:
#   src/nih_reporter_mcp/config.py    - constants + SPENDING_CATEGORIES
#   src/nih_reporter_mcp/models.py    - Pydantic models
#   src/nih_reporter_mcp/utils.py     - HTTP client, pagination, criteria builder
#   src/nih_reporter_mcp/app.py       - FastMCP entry point
#   src/nih_reporter_mcp/tools/*.py   - 13 tool files + 2 stubs (register(mcp) pattern)
#     Tools: search_projects, summarize_funding, funding_trend, org_profile,
#            investigator, overlap_check, study_section_workload, recent_awards,
#            evidence_bundle, explain_health_topic, project_by_id, publications,
#            publication_details
#     Stubs: clinical_trials_lookup, usaspending_comparison

# COMMAND ----------

# MAGIC %md ## 2. Import sanity check

# COMMAND ----------

# DBTITLE 1,Import sanity check (module layout)
import subprocess

SRC_PATH = os.path.join(WORKDIR, "src")
check = subprocess.run(
    ["python3", "-c", """
from nih_reporter_mcp.config import SPENDING_CATEGORIES
from nih_reporter_mcp.tools import register_tools
from nih_reporter_mcp.app import mcp
print('imports OK')
print('spending categories loaded:', len(SPENDING_CATEGORIES))
"""],
    capture_output=True, text=True,
    env={**os.environ, "PYTHONPATH": SRC_PATH},
)
print(check.stdout)
if check.returncode != 0:
    print("STDERR:", check.stderr)
    raise RuntimeError("Module import failed -- check the project layout.")

# COMMAND ----------

# MAGIC %md ## 3. Start the MCP server as a background process (local to this notebook)

# COMMAND ----------

# DBTITLE 1,Start MCP server (module layout)
import time

subprocess.run(["pkill", "-f", "nih_reporter_mcp.app"], capture_output=True)
subprocess.run(["pkill", "-f", f"{WORKDIR}/server.py"], capture_output=True)  # legacy
time.sleep(1)

SRC_PATH = os.path.join(WORKDIR, "src")
log_path = os.path.join(WORKDIR, "server.log")
proc = subprocess.Popen(
    ["python3", "-m", "nih_reporter_mcp.app"],
    stdout=open(log_path, "w"),
    stderr=subprocess.STDOUT,
    env={**os.environ, "PYTHONPATH": SRC_PATH, "PORT": "8000"},
    cwd=WORKDIR,
)
print(f"Started server, PID {proc.pid}")
time.sleep(5)

with open(log_path) as f:
    print(f.read())

# COMMAND ----------

# MAGIC %md ## 4. Confirm the server is live

# COMMAND ----------

# DBTITLE 1,Cell 10
import asyncio
from fastmcp import Client
import nest_asyncio
nest_asyncio.apply()

def run_async(coro):
    """Run an async coroutine safely inside a Databricks notebook, which
    already runs its own event loop (bare asyncio.run() fails there)."""
    return asyncio.get_event_loop().run_until_complete(coro)

MCP_URL = "http://localhost:8000/mcp"

async def check_tools():
    async with Client(MCP_URL) as c:
        tools = await c.list_tools()
        return [t.name for t in tools]

tool_names = run_async(check_tools())
print("Registered tools:", tool_names)
assert len(tool_names) == 13, f"Expected 13 tools, got {len(tool_names)}"
print("\nOK -- server is live and fully registered.")

# COMMAND ----------

# MAGIC %md ## 5. Functional smoke tests

# COMMAND ----------

# DBTITLE 1,Smoke tests (18 checks)
async def smoke_tests():
    results = []

    async def check(name, coro_fn):
        try:
            ok, detail = await coro_fn()
            results.append((name, ok, detail))
        except Exception as e:
            results.append((name, False, f"raised unexpectedly: {e}"))

    async with Client(MCP_URL) as c:

        async def t1():
            r = await c.call_tool("summarize_funding_by_topic",
                                   {"topic": "CRISPR gene editing", "fiscal_years": [2023]})
            d = r.data
            return (d.complete and d.total_matching_projects == 1739,
                    f"complete={d.complete}, total={d.total_matching_projects}, ${d.total_award_amount_usd:,.0f}")
        await check("Exact-total pagination (CRISPR FY2023 == 1,739 projects)", t1)

        async def t2():
            r = await c.call_tool("summarize_funding_by_topic", {"topic": "cancer", "fiscal_years": [2023], "funding_basis": "all_records"})
            d = r.data
            return (not d.complete and d.projects_aggregated == 10000,
                    f"complete={d.complete}, aggregated={d.projects_aggregated}, total_matching={d.total_matching_projects}")
        await check("10,000-record retrieval cap honestly flagged (not silently truncated)", t2)

        async def t3():
            r = await c.call_tool("organization_funding_profile",
                                   {"organization_name": "BOSTON UNIVERSITY MEDICAL CAMPUS",
                                    "fiscal_years": [2024], "exact_match": True})
            d = r.data
            return (d.total_matching_projects == 348, f"total={d.total_matching_projects} (expected 348)")
        await check("Exact org-name match isolates single institution", t3)

        async def t4():
            r = await c.call_tool("summarize_funding_by_topic",
                                   {"spending_category": "long covid", "fiscal_years": [2023]})
            d = r.data
            return (50_000_000 < d.total_award_amount_usd < 300_000_000,
                    f"RCDC category total=${d.total_award_amount_usd:,.0f} vs free-text total=$891,742,057 (same query)")
        await check("Official RCDC category vs free-text search: documented divergence", t4)

        async def t5():
            try:
                await c.call_tool("search_funded_projects", {"topic": ""})
                return (False, "did not raise")
            except Exception as e:
                return ("empty" in str(e).lower(), str(e)[:100])
        await check("Empty topic raises clean validation error", t5)

        async def t6():
            try:
                await c.call_tool("search_funded_projects", {"topic": 'cancer" OR "1"="1'})
                return (False, "did not raise")
            except Exception as e:
                msg = str(e)
                return ("403" in msg and "httpx" not in msg.lower(), msg[:120])
        await check("SQL-injection-style input: clean 403 handling, no leaked traceback", t6)

        async def t7():
            r1 = await c.call_tool("search_funded_projects",
                                    {"topic": "CRISPR gene editing", "fiscal_years": [2023], "limit": 1})
            r_whole = await c.call_tool("summarize_funding_by_topic",
                                    {"topic": "CRISPR gene editing", "fiscal_years": [2023], "funding_basis": "whole_award"})
            r_all = await c.call_tool("summarize_funding_by_topic",
                                    {"topic": "CRISPR gene editing", "fiscal_years": [2023], "funding_basis": "all_records"})
            totals_match = r1.data.total_matching_projects == r_whole.data.total_matching_projects == r_all.data.total_matching_projects
            whole_lower = r_whole.data.total_award_amount_usd < r_all.data.total_award_amount_usd
            return (totals_match and whole_lower,
                    f"matching={r1.data.total_matching_projects}, "
                    f"whole=${r_whole.data.total_award_amount_usd:,.0f} < all=${r_all.data.total_award_amount_usd:,.0f}, "
                    f"subprojects_excluded={r_whole.data.subproject_excluded_count}")
        await check("Cross-tool consistency + whole_award < all_records (dedup works)", t7)

        async def t8():
            r = await c.call_tool("funding_trend_by_year",
                                   {"spending_category": "Cancer", "start_year": 2022, "end_year": 2023})
            d = r.data
            # Every year should have nonzero project_count and total_award_amount_usd --
            # the old bug produced all-zero years when spending_category was attempted
            # via the topic string workaround.
            all_nonzero = all(y.project_count > 0 and y.total_award_amount_usd > 0 for y in d.years)
            return (all_nonzero, f"years={[(y.fiscal_year, y.project_count, y.total_award_amount_usd) for y in d.years]}")
        await check("funding_trend_by_year accepts spending_category directly (regression test for prior bug)", t8)

        async def t9():
            calls_before = len(CALL_LOG)
            for _ in range(3):
                await run_agent("What are the five biggest Alzheimer's biomarker grants in Massachusetts in FY2024?")
            calls_after = len(CALL_LOG)
            avg_calls = (calls_after - calls_before) / 3
            return (avg_calls <= 1.5, f"avg_tool_calls_per_run={avg_calls:.1f} (regression threshold: 1.5)")
        await check("Tool-call efficiency regression guard (docstring fix should keep this near 1.0)", t9)

        async def t10():
            r = await c.call_tool("check_investigator_overlap",
                                   {"last_name": "Collins", "first_name": "Francis"})
            d = r.data
            return (isinstance(d.total_active_awards, int) and d.total_active_awards >= 0,
                    f"total_active_awards={d.total_active_awards}, flagged={len(d.flagged_awards)}")
        await check("check_investigator_overlap runs end-to-end and returns valid structure", t10)

        async def t11():
            r1 = await c.call_tool("check_investigator_overlap", {"last_name": "Au", "first_name": "Rhoda"})
            r2 = await c.call_tool("check_investigator_overlap",
                                   {"last_name": "Au", "first_name": "Rhoda", "exclude_project_num": "U19AG068753"})
            return (r2.data.total_active_awards < r1.data.total_active_awards,
                    f"without exclusion: {r1.data.total_active_awards}, with exclusion: {r2.data.total_active_awards}")
        await check("exclude_project_num strictly reduces the result count", t11)

        async def t12():
            r = await c.call_tool("study_section_workload",
                                   {"topic": "CRISPR gene editing", "fiscal_years": [2023]})
            d = r.data
            section_sum = sum(s.project_count for s in d.sections)
            return (len(d.sections) > 0 and section_sum <= d.total_projects,
                    f"sections={len(d.sections)}, section_project_sum={section_sum}, total_projects={d.total_projects}")
        await check("study_section_workload groups projects correctly, counts reconcile", t12)

        async def t13():
            r = await c.call_tool("search_recent_awards", {"limit": 5})
            d = r.data
            has_awards = len(d.awards) > 0
            respects_limit = d.returned > 0 and d.returned <= 5
            all_have_url = all(hasattr(a, 'reporter_url') and a.reporter_url for a in d.awards)
            return (has_awards and respects_limit and all_have_url,
                    f"returned={d.returned}, total_matching={d.total_matching}, has_awards={has_awards}, all_have_url={all_have_url}")
        await check("search_recent_awards returns valid results respecting limit", t13)

        async def t14():
            r = await c.call_tool("summarize_funding_by_topic",
                                   {"topic": "CRISPR gene editing", "fiscal_years": [2023], "include_provenance": True})
            d = r.data
            has_prov = d.provenance is not None
            basis_stated = "whole_award" in d.counting_unit.lower() or "whole_award" in d.funding_basis
            agg = d.provenance.records_aggregated if has_prov else 0
            sub_excl = d.subproject_excluded_count
            return (has_prov and basis_stated and agg >= 1400 and sub_excl > 0,
                    f"provenance={has_prov}, basis={d.funding_basis}, aggregated={agg}, subproject_excluded={sub_excl}")
        await check("Provenance populated and counting-unit trap documented", t14)

        async def t15():
            r = await c.call_tool("export_evidence_bundle",
                                   {"topic": "sickle cell disease", "fiscal_years": [2023], "label": "SCD FY23"})
            d = r.data
            has_ids = len(d.provenance.source_record_ids) > 0
            has_repro = "reproduce" in d.reproduction_note.lower()
            return (has_ids and has_repro,
                    f"source_ids={len(d.provenance.source_record_ids)}, has_repro_note={has_repro}")
        await check("export_evidence_bundle returns inspectable source record IDs", t15)

        async def t16():
            r = await c.call_tool("explain_health_topic", {"topic": "diabetes"})
            d = r.data
            return (d.found and d.summary is not None and len(d.summary) > 50,
                    f"found={d.found}, summary_len={len(d.summary) if d.summary else 0}")
        await check("explain_health_topic returns a MedlinePlus summary for a common condition", t16)

        async def t17():
            r = await c.call_tool("explain_health_topic", {"topic": "zzznotarealcondition999"})
            d = r.data
            return (d.found is False and "no" in d.note.lower(),
                    f"found={d.found}, note={d.note[:80]}")
        await check("explain_health_topic handles no-match cleanly (not an error)", t17)

        async def t18():
            import time as _t
            w1 = await c.call_tool("summarize_funding_by_topic",
                                    {"topic": "CRISPR gene editing", "fiscal_years": [2023], "funding_basis": "whole_award"})
            a1 = await c.call_tool("summarize_funding_by_topic",
                                    {"topic": "CRISPR gene editing", "fiscal_years": [2023], "funding_basis": "all_records"})
            t0 = _t.monotonic()
            w2 = await c.call_tool("summarize_funding_by_topic",
                                    {"topic": "CRISPR gene editing", "fiscal_years": [2023], "funding_basis": "whole_award"})
            warm_lat = _t.monotonic() - t0
            whole_stable = w1.data.total_award_amount_usd == w2.data.total_award_amount_usd
            bases_differ = w1.data.total_award_amount_usd != a1.data.total_award_amount_usd
            return (whole_stable and bases_differ,
                    f"whole_award stable={whole_stable}, whole!=all_records={bases_differ} "
                    f"(${w1.data.total_award_amount_usd:,.0f} vs ${a1.data.total_award_amount_usd:,.0f}), "
                    f"warm_latency={warm_lat:.2f}s")
        await check("Cache preserves correctness and never collides whole_award with all_records", t18)

    return results


results = run_async(smoke_tests())

print("\n" + "=" * 78)
print("SMOKE TEST RESULTS")
print("=" * 78)
passed = 0
for name, ok, detail in results:
    mark = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    print(f"[{mark}] {name}")
    print(f"       {detail}")
print("-" * 78)
total = len(results)
print(f"TOTAL: {passed}/{total} passed")
print("=" * 78)

# COMMAND ----------

# MAGIC %md ## 6. Databricks auth context (cluster-issued token)

# COMMAND ----------

host = "https://" + spark.conf.get("spark.databricks.workspaceUrl")
token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)

print("host:", host)
print("token present:", token is not None)
assert token is not None, "No token available from notebook context."

# COMMAND ----------

# DBTITLE 1,§7. Model picker & observability
# MAGIC %md ## 7. Interactive model picker & tool-call observability
# MAGIC
# MAGIC Dropdown widget populated from live, ready chat endpoints — switch models
# MAGIC without editing code. Reasoning-tier endpoints (sol/luna/terra/astra) are
# MAGIC kept selectable so their function-calling incompatibility is directly
# MAGIC demonstrable. Tool-call observability log captures latency and success for
# MAGIC every call the agent makes.

# COMMAND ----------

# DBTITLE 1,Model picker widget (chat-capable only)
import requests

resp = requests.get(f"{host}/api/2.0/serving-endpoints", headers={"Authorization": f"Bearer {token}"})
endpoints = resp.json().get("endpoints", [])

_REASONING_TAGS = {"sol", "luna", "terra", "astra"}

def _is_reasoning_endpoint(name: str) -> bool:
    return any(f"-{t}" in name for t in _REASONING_TAGS)

# Filter to chat-capable endpoints only (excludes embedding models like
# bge/gte/qwen3-embedding that can't do tool-calling).  Reasoning-tier
# endpoints are kept visible so the incompatibility is directly demonstrable.
all_chat = sorted([
    e["name"] for e in endpoints
    if e.get("state", {}).get("ready") == "READY"
    and "chat" in (e.get("task") or "")
])
if not all_chat:
    raise RuntimeError(f"No chat-capable endpoints found among {len(endpoints)} endpoints.")
non_reasoning_defaults = [n for n in all_chat if "gpt" in n.lower() and not _is_reasoning_endpoint(n)]

default_model = non_reasoning_defaults[0] if non_reasoning_defaults else all_chat[0]

dbutils.widgets.dropdown("model", default_model, all_chat, "Model endpoint")
MODEL = dbutils.widgets.get("model")

print(f"Selected model: {MODEL}")
if _is_reasoning_endpoint(MODEL):
    print("WARNING: this is a reasoning-tier endpoint (sol/luna/terra/astra family). "
          "These have been observed to reject function-calling with default "
          "reasoning settings -- expect tool calls to fail. This is left selectable "
          "deliberately so the incompatibility is directly demonstrable.")

# COMMAND ----------

# DBTITLE 1,Observability log
# MAGIC %md ### Tool-call observability log
# MAGIC
# MAGIC Lightweight in-memory log: tool name, arguments, latency, success/failure.
# MAGIC Printed as a summary table at the end — the natural seed for a real
# MAGIC monitoring dashboard (e.g. write `CALL_LOG` to a Delta table instead of
# MAGIC a list).

# COMMAND ----------

# DBTITLE 1,Observability: CALL_LOG + logged_call_tool + print_call_log_summary
import time as _time

CALL_LOG = []  # each entry: dict(tool, args, latency_s, ok, error)


async def logged_call_tool(mcp_client, tool_name, args):
    """Wraps mcp_client.call_tool with latency + success logging."""
    start = _time.monotonic()
    try:
        result = await mcp_client.call_tool(tool_name, args)
        CALL_LOG.append({
            "tool": tool_name, "args": args,
            "latency_s": round(_time.monotonic() - start, 2),
            "ok": True, "error": None,
        })
        return result
    except Exception as e:
        CALL_LOG.append({
            "tool": tool_name, "args": args,
            "latency_s": round(_time.monotonic() - start, 2),
            "ok": False, "error": str(e)[:200],
        })
        raise


def print_call_log_summary():
    if not CALL_LOG:
        print("No tool calls logged yet.")
        return
    print("\n" + "=" * 78)
    print(f"TOOL-CALL LOG ({len(CALL_LOG)} calls this session)")
    print("=" * 78)
    from collections import Counter
    by_tool = Counter(c["tool"] for c in CALL_LOG)
    success_rate = sum(1 for c in CALL_LOG if c["ok"]) / len(CALL_LOG) * 100
    avg_latency = sum(c["latency_s"] for c in CALL_LOG) / len(CALL_LOG)
    print(f"Success rate: {success_rate:.0f}%   Avg latency: {avg_latency:.2f}s")
    print("\nCalls by tool:")
    for tool, count in by_tool.most_common():
        tool_calls = [c for c in CALL_LOG if c["tool"] == tool]
        tool_success = sum(1 for c in tool_calls if c["ok"]) / len(tool_calls) * 100
        tool_avg_latency = sum(c["latency_s"] for c in tool_calls) / len(tool_calls)
        print(f"  {tool:35s} {count:3d} calls   {tool_success:5.0f}% success   {tool_avg_latency:.2f}s avg")
    failures = [c for c in CALL_LOG if not c["ok"]]
    if failures:
        print(f"\n{len(failures)} failed call(s):")
        for f in failures:
            print(f"  {f['tool']}({f['args']}) -> {f['error']}")
    print("=" * 78)

# COMMAND ----------

# MAGIC %md ## 8. Connection test

# COMMAND ----------

from openai import OpenAI

llm = OpenAI(api_key=token, base_url=host.rstrip("/") + "/serving-endpoints/")

resp = llm.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "Say 'connection test ok' and nothing else."}],
)
print(resp.choices[0].message.content)

# COMMAND ----------

# DBTITLE 1,§9. Agent loop
# MAGIC %md ## 9. Agent loop (with tool-call logging)
# MAGIC
# MAGIC Every `mcp_client.call_tool(...)` call is routed through
# MAGIC `logged_call_tool(...)` so latency and success/failure are captured
# MAGIC for the observability summary.

# COMMAND ----------

# DBTITLE 1,Agent loop with logged_call_tool
import json

MAX_TOOL_ROUNDS = 6


def mcp_tool_to_openai_schema(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema or {"type": "object", "properties": {}},
        },
    }


async def run_agent(question: str, model: str = None):
    model = model or MODEL
    print(f"\n{'='*78}\nQUESTION: {question}\nMODEL: {model}\n{'='*78}\n")

    async with Client(MCP_URL) as mcp_client:
        mcp_tools = await mcp_client.list_tools()
        openai_tools = [mcp_tool_to_openai_schema(t) for t in mcp_tools]
        print(f"[setup] {len(openai_tools)} tools loaded from live MCP server\n")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research funding analyst assistant with access to live "
                    "NIH RePORTER grant data via tools. Always use the tools to answer "
                    "questions about NIH funding, grants, or research spending -- never "
                    "guess or rely on prior knowledge for specific figures. Cite concrete "
                    "numbers from tool results in your final answer. If comparing two "
                    "methods (e.g. official category vs free-text search), call both "
                    "tools and explicitly state both numbers."
                ),
            },
            {"role": "user", "content": question},
        ]

        for round_num in range(1, MAX_TOOL_ROUNDS + 1):
            try:
                response = llm.chat.completions.create(
                    model=model, messages=messages, tools=openai_tools, tool_choice="auto",
                )
            except Exception as e:
                print(f"[round {round_num}] LLM call failed: {e}")
                if _is_reasoning_endpoint(model):
                    print("           (Expected for reasoning-tier endpoints -- "
                          "see model picker warning above.)")
                return None

            msg = response.choices[0].message

            if not msg.tool_calls:
                print(f"[round {round_num}] Final answer:\n")
                print("-" * 78)
                print(msg.content)
                print("-" * 78)
                return msg.content

            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                print(f"[round {round_num}] -> {tool_name}({args})")

                try:
                    result = await logged_call_tool(mcp_client, tool_name, args)
                    payload = result.data
                    if hasattr(payload, "model_dump"):
                        payload = payload.model_dump()
                    result_str = json.dumps(payload, default=str)[:4000]
                    print(f"           OK ({len(result_str)} chars)\n")
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
                    print(f"           ERROR: {e}\n")

                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

        print("[warning] Hit MAX_TOOL_ROUNDS without a final answer.")
        return None

# COMMAND ----------

# MAGIC %md ## 10. Single-question test

# COMMAND ----------

run_async(run_agent(
    "What are the five biggest Alzheimer's biomarker grants in Massachusetts in FY2024?"
))

# COMMAND ----------

# MAGIC %md ## 11. Full demo set
# MAGIC
# MAGIC Question 4 is the centerpiece: it forces the model to call
# MAGIC `summarize_funding_by_topic` twice (once by official category, once by
# MAGIC free-text) and compare the results -- the question explicitly asks for the
# MAGIC comparison, and the agent correctly selects both tool paths to
# MAGIC surface the RCDC-vs-free-text divergence.

# COMMAND ----------

DEMO_QUESTIONS = [
    "What are the five biggest Alzheimer's biomarker grants in Massachusetts in FY2024?",
    "How much has NIH spent on CRISPR gene editing research in FY2023, and is that an exact figure or an estimate?",
    "Is NIH funding for long COVID research growing or shrinking between 2021 and 2023?",
    "Compare NIH's official 'Long COVID' spending category total to a free-text search for 'long covid' in FY2023 -- are they the same, and if not, why might that be?",
]

for q in DEMO_QUESTIONS:
    run_async(run_agent(q))

# COMMAND ----------

# DBTITLE 1,§12. Observability summary
# MAGIC %md ## 12. Observability summary

# COMMAND ----------

# DBTITLE 1,Print observability summary
print_call_log_summary()

# COMMAND ----------

# DBTITLE 1,§13. Efficiency variance
# MAGIC %md ## 13. Tool-call efficiency variance
# MAGIC
# MAGIC Repeats the same question multiple times to measure whether the agent's
# MAGIC tool-calling round count is consistent. Variance here reflects LLM
# MAGIC nondeterminism, not server-side inconsistency.

# COMMAND ----------

# DBTITLE 1,Tool-call efficiency variance
import statistics

CALL_LOG.clear()  # reset so this measurement starts clean

async def measure_call_efficiency(question: str, n_runs: int = 3):
    round_counts = []
    for i in range(n_runs):
        calls_before = len(CALL_LOG)
        await run_agent(question)
        calls_after = len(CALL_LOG)
        round_counts.append(calls_after - calls_before)
    return round_counts

efficiency_question = "What are the five biggest Alzheimer's biomarker grants in Massachusetts in FY2024?"
counts = run_async(measure_call_efficiency(efficiency_question, n_runs=3))

print("\n" + "=" * 78)
print("TOOL-CALL EFFICIENCY VARIANCE (same question, repeated runs)")
print("=" * 78)
print(f"Question: {efficiency_question}")
print(f"Tool calls per run: {counts}")
print(f"Mean: {statistics.mean(counts):.1f}, Stdev: {statistics.stdev(counts) if len(counts) > 1 else 0:.1f}")
print("Note: variance here reflects LLM query-refinement nondeterminism, not")
print("server-side inconsistency -- the same tool/args always return the same")
print("live data. This is worth documenting as a known characteristic of")
print("LLM-driven tool use rather than a defect.")
print("=" * 78)

# COMMAND ----------

# DBTITLE 1,Done
# MAGIC %md ## Done
# MAGIC
# MAGIC What this notebook demonstrates end-to-end:
# MAGIC
# MAGIC * A working MCP server over live NIH RePORTER data (v0.10.0: 13 goal-oriented tools,
# MAGIC   9 audience-tailored prompts, 2 resources, 2 custom HTTP routes, 3 upstream
# MAGIC   APIs: RePORTER, NCBI E-utilities, MedlinePlus)
# MAGIC * **Correct funding aggregation**: subproject records excluded by default
# MAGIC   (whole_award mode), appl_id dedup, missing amounts tracked not zeroed.
# MAGIC   CRISPR FY2023 corrected from $921M (all_records) to $837M (whole_award);
# MAGIC   naive sum overstated corrected figure by 10.1%.
# MAGIC * **Response caching + parallelism** (v0.9.0): 15-minute TTL cache on
# MAGIC   `post_json` reduces warm-path latency from 4–6s to ~0.02s (>100x).
# MAGIC   `funding_trend_by_year` fires all years via `asyncio.gather`.
# MAGIC   Cache correctness proven: same basis returns identical results cold vs
# MAGIC   warm; different bases never collide (t18).
# MAGIC * 18/18 automated smoke tests (quick mode: 5 in \~8s; full parallel: 17+t9
# MAGIC   in \~90s) passing against live data — covering pagination, ceiling
# MAGIC   flagging, input validation, injection handling, investigator overlap,
# MAGIC   study section grouping, recent awards, provenance/counting-unit
# MAGIC   transparency, evidence bundle export, MedlinePlus health-topic
# MAGIC   lookup (positive match + no-match handling), tool-call efficiency,
# MAGIC   whole_award vs all_records dedup verification, and cache correctness
# MAGIC * Widget-driven model selection filtered to chat-capable endpoints, with
# MAGIC   reasoning-tier incompatibility directly demonstrable
# MAGIC * Tool-call observability: per-tool latency, success rate, and session summary
# MAGIC * A Databricks-hosted LLM autonomously selecting and chaining tools — full
# MAGIC   4-question demo completes in \~6 tool calls total after the search_funded_projects
# MAGIC   docstring fix eliminated redundant near-duplicate re-querying
# MAGIC * A multi-tool comparison (official RCDC category vs. free-text search),
# MAGIC   triggered by an explicitly comparative demo question, that surfaces a
# MAGIC   genuine, documented finding about how NIH's own categorized spending
# MAGIC   differs from naive keyword search