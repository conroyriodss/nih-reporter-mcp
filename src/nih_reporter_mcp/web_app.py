"""NIH RePORTER MCP - Web test interface.

Single-process: FastAPI serves UI + API; FastMCP mounted at /mcp.
Agent connects via in-process Client to localhost:{port}/mcp.
"""
from __future__ import annotations
import asyncio, json, logging, os, time, traceback
from pathlib import Path
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from nih_reporter_mcp.app import mcp

log = logging.getLogger(__name__)


def _extract_data(result):
    """Extract JSON-serializable data from an MCP call_tool result.

    fastmcp Client.call_tool returns different shapes depending on transport:
    - In-process: .data may be a Pydantic model with .model_dump()
    - HTTP transport: .data may be a string repr of a model
    - .content[0].text always contains the JSON text
    """
    # Try .data first (Pydantic model)
    d = result.data
    if hasattr(d, "model_dump"):
        return d.model_dump()
    if isinstance(d, dict):
        return d
    # Fall back to .content text
    for item in (result.content or []):
        text = getattr(item, "text", None)
        if text:
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                pass
    # Last resort: stringify
    return {"raw": str(d)}


def _truncate_tool_result(payload, max_chars: int = 4000) -> str:
    """Serialize tool output to valid JSON, preserving status/caveat fields
    while trimming bulky data arrays.  Mirrors the notebook agent loop."""
    full = json.dumps(payload, default=str)
    if len(full) <= max_chars:
        return full
    if not isinstance(payload, dict):
        return full[:max_chars]

    def _trim(obj, max_items):
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if isinstance(v, list):
                    out[k] = [_trim(i, max_items) for i in v[:max_items]]
                    if len(v) > max_items:
                        out[k].append(f"... and {len(v) - max_items} more")
                elif isinstance(v, dict):
                    out[k] = _trim(v, max_items)
                else:
                    out[k] = v
            return out
        return obj

    for n in (3, 1):
        t = json.dumps(_trim(payload, n), default=str)
        if len(t) <= max_chars:
            return t
    # Tier 3: scalars only
    scalars = {k: v for k, v in payload.items()
               if not isinstance(v, (list, dict))}
    scalars["_omitted_keys"] = [k for k in payload
                                if isinstance(payload[k], (list, dict))]
    return json.dumps(scalars, default=str)


# ── Auth / config ────────────────────────────────────────────────────────────
PORT = int(os.environ.get("DATABRICKS_APP_PORT") or os.environ.get("PORT") or "8000")
MCP_URL = f"http://localhost:{PORT}/mcp-server/mcp"
MAX_TOOL_ROUNDS = 6
DEFAULT_MODEL = "databricks-gpt-5-5"
_REASONING_TAGS = {"sol", "luna", "terra", "astra"}

# Use the Databricks SDK for auth — it picks up the app service principal
# credentials automatically (managed OAuth), avoiding stale PAT tokens.
try:
    from databricks.sdk import WorkspaceClient
    _ws = WorkspaceClient()
    _h = _ws.config.host or ""
    DB_HOST = _h if _h.startswith("https://") else f"https://{_h}"
except Exception:
    _ws = None
    DB_HOST = os.environ.get("DATABRICKS_HOST", "")


def _get_token() -> str:
    """Return a fresh bearer token.  Prefers the SDK's token provider
    (auto-refreshes OAuth); falls back to DATABRICKS_TOKEN env var."""
    if _ws is not None:
        try:
            header = _ws.config.authenticate()
            # authenticate() returns a dict like {"Authorization": "Bearer ..."}
            auth_val = header.get("Authorization", "")
            if auth_val.startswith("Bearer "):
                return auth_val[7:]
        except Exception:
            pass
    return os.environ.get("DATABRICKS_TOKEN", "")


import logging as _logging
log = _logging.getLogger("nih_reporter_mcp.web_app")
log.info("STARTUP: DB_HOST=%s, _ws=%s, token_len=%d",
         DB_HOST, "OK" if _ws else "NONE", len(_get_token()))

# ── FastAPI app ──────────────────────────────────────────────────────────────
mcp_starlette = mcp.http_app()
app = FastAPI(title="NIH RePORTER MCP Test Interface", lifespan=mcp_starlette.lifespan)
# Mount MCP Starlette at /mcp-server — the MCP protocol endpoint
# becomes /mcp-server/mcp (FastMCP's http_app serves at /mcp internally).
app.mount("/mcp-server", mcp_starlette)


@app.get("/debug")
async def debug_config():
    """Diagnostic endpoint — no secrets, just config status."""
    token = _get_token()
    return {
        "db_host": DB_HOST or "(empty)",
        "ws_client": "OK" if _ws else "NONE",
        "token_present": bool(token),
        "token_len": len(token),
        "token_prefix": token[:8] + "..." if len(token) > 8 else "(short)",
        "env_DATABRICKS_HOST": os.environ.get("DATABRICKS_HOST", "(not set)"),
        "env_DATABRICKS_TOKEN_set": "DATABRICKS_TOKEN" in os.environ,
        "env_DATABRICKS_APP_PORT": os.environ.get("DATABRICKS_APP_PORT", "(not set)"),
        "mcp_url": MCP_URL,
        "port": PORT,
    }


@app.exception_handler(Exception)
async def _global_error_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return JSON, never HTML."""
    log.error("Unhandled error on %s %s: %s", request.method, request.url.path,
              exc, exc_info=True)
    return JSONResponse(
        {"error": str(exc)[:500], "detail": traceback.format_exception_only(type(exc), exc)[-1].strip()},
        status_code=500,
    )

class AskRequest(BaseModel):
    question: str
    model: str = DEFAULT_MODEL

class EvidenceRequest(BaseModel):
    topic: str | None = None
    spending_category: str | None = None
    fiscal_years: list[int] = [2024]
    label: str = "web-ui"
    funding_basis: str = "whole_award"

HTML_PATH = Path(__file__).parent / "static" / "index.html"

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    if HTML_PATH.exists():
        return HTMLResponse(HTML_PATH.read_text())
    return HTMLResponse("<h1>static/index.html not found</h1>", status_code=500)

@app.get("/models")
async def list_models():
    token = _get_token()
    if not DB_HOST or not token:
        return {"models": [DEFAULT_MODEL], "default": DEFAULT_MODEL}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{DB_HOST}/api/2.0/serving-endpoints",
                                    headers={"Authorization": f"Bearer {token}"})
            endpoints = resp.json().get("endpoints", [])
        chat = sorted([e["name"] for e in endpoints
                       if e.get("state",{}).get("ready")=="READY" and "chat" in (e.get("task") or "")])
        dflt = DEFAULT_MODEL if DEFAULT_MODEL in chat else (chat[0] if chat else DEFAULT_MODEL)
        return {"models": chat, "default": dflt}
    except Exception as e:
        return {"models": [DEFAULT_MODEL], "default": DEFAULT_MODEL, "error": str(e)[:200]}

def _to_openai(tool):
    return {"type":"function","function":{"name":tool.name,"description":tool.description or "",
            "parameters":tool.input_schema or {"type":"object","properties":{}}}}

async def _run_agent(question: str, model: str) -> dict:
    from openai import OpenAI
    from fastmcp import Client
    token = _get_token()
    if not token:
        return {"answer": "Error: no authentication token available. "
                "Check that the app's service principal has CAN_QUERY on "
                "the serving endpoint (see app.yaml resources).",
                "trace": []}
    llm = OpenAI(api_key=token, base_url=DB_HOST.rstrip("/")+"/serving-endpoints/")
    trace = []
    async with Client(MCP_URL) as mc:
        tools = [_to_openai(t) for t in await mc.list_tools()]
        msgs = [{"role":"system","content":"You are a research funding analyst with live NIH RePORTER tools. Use tools for all funding questions. Cite concrete numbers."},
                {"role":"user","content":question}]
        for rnd in range(1, MAX_TOOL_ROUNDS+1):
            try:
                resp = llm.chat.completions.create(model=model, messages=msgs, tools=tools, tool_choice="auto")
            except Exception as e:
                return {"answer":f"LLM error: {e}","trace":trace}
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return {"answer":msg.content or "","trace":trace}
            msgs.append({"role":"assistant","content":msg.content,
                         "tool_calls":[{"id":tc.id,"type":"function",
                                        "function":{"name":tc.function.name,"arguments":tc.function.arguments}}
                                       for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                t0 = time.monotonic()
                try:
                    r = await mc.call_tool(name, args)
                    p = _extract_data(r)
                    rs = _truncate_tool_result(p)
                    trace.append({"tool":name,"args":args,"latency_s":round(time.monotonic()-t0,2),"ok":True})
                except Exception as e:
                    rs = json.dumps({"error":str(e)})
                    trace.append({"tool":name,"args":args,"latency_s":round(time.monotonic()-t0,2),"ok":False,"error":str(e)[:200]})
                msgs.append({"role":"tool","tool_call_id":tc.id,"content":rs})
    return {"answer":"Hit max tool rounds.","trace":trace}

@app.post("/ask")
async def ask(req: AskRequest):
    return await _run_agent(req.question, req.model)

@app.post("/evidence")
async def get_evidence(req: EvidenceRequest):
    from fastmcp import Client
    args = {"fiscal_years":req.fiscal_years,"label":req.label,"funding_basis":req.funding_basis}
    if req.topic: args["topic"] = req.topic
    if req.spending_category: args["spending_category"] = req.spending_category
    async with Client(MCP_URL) as mc:
        try:
            r = await mc.call_tool("export_evidence_bundle", args)
            p = _extract_data(r)
            return {"ok":True,"data":json.loads(json.dumps(p, default=str))}
        except Exception as e:
            return JSONResponse({"ok":False,"error":str(e)[:500]}, status_code=400)

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
