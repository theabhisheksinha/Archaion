import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import logging
from pathlib import Path
import re
from logging.handlers import RotatingFileHandler
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import httpx
from contextlib import asynccontextmanager, AsyncExitStack
from dotenv import load_dotenv

from app.flows.modernization_flow import ModernizationFlow, ModernizationState

load_dotenv()
CAST_MCP_URL = os.getenv("CAST_MCP_URL", "")
CAST_X_API_KEY = os.getenv("CAST_X_API_KEY", "")

DISCLAIMER_TEXT = (
    "## Disclaimer\n"
    "Disclaimer - This document and the information contained herein are provided for informational and guidance purposes only. "
    "Before incorporating any of these configurations, scripts, or architectural patterns into a formal modernization journey, "
    "they must be reviewed and verified by a competent Solutions Architect to ensure alignment with specific infrastructure, "
    "security, and compliance requirements.\n\n"
    "The developer of this platform and CAST Software assume no responsibility or liability for any errors, omissions, or damages—"
    "direct or indirect—resulting from the use or implementation of this information. "
    "All actions taken based on this content are at the user's own risk and discretion."
)

def _setup_logging() -> logging.Logger:
    lvl = (os.getenv("LOG_LEVEL") or "INFO").upper()
    log_file = os.getenv("LOG_FILE")
    if log_file is None:
        log_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs", "archaion.log"))
    if str(log_file).strip().lower() in {"", "0", "false", "none", "null"}:
        log_file = None

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    root = logging.getLogger()
    root.setLevel(getattr(logging, lvl, logging.INFO))

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        existing = [
            h
            for h in root.handlers
            if isinstance(h, RotatingFileHandler)
            and getattr(h, "baseFilename", None)
            and os.path.abspath(getattr(h, "baseFilename")) == os.path.abspath(log_file)
        ]

        if not existing:
            fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
            fh.setFormatter(fmt)
            root.addHandler(fh)

    return logging.getLogger("archaion.backend")


logger = _setup_logging()

def _normalize_mcp_url(url: Optional[str]) -> str:
    if not url:
        return ""
    s = str(url).strip()
    s = s.strip("`'\"").strip()
    return s.rstrip("/")

class MCPServerHTTP:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = _normalize_mcp_url(base_url)
        self.headers = {"x-api-key": api_key, "Accept": "application/json, text/event-stream"}
        self._stack: Optional[AsyncExitStack] = None
        self._http: Optional[httpx.AsyncClient] = None
        self.session: Optional[ClientSession] = None

    async def open(self):
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        self._http = await self._stack.enter_async_context(httpx.AsyncClient(headers=self.headers, follow_redirects=True))
        read, write, _ = await self._stack.enter_async_context(streamable_http_client(self.base_url, http_client=self._http))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

    async def aclose(self):
        if self._stack:
            try:
                await self._stack.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"MCP shutdown failed: {e!r}")

    async def invoke_tool(self, tool: str, payload: dict) -> Any:
        if not self.session:
            raise HTTPException(status_code=500, detail="MCP not initialized")
        tool_name = tool
        if tool == "iso-5055-flaws":
            tool_name = "iso_5055_flaws"
        try:
            res = await self.session.call_tool(tool_name, payload)
            
            # Simple dump to dict if possible
            if hasattr(res, "model_dump"):
                return res.model_dump()
            elif hasattr(res, "dict"):
                return res.dict()
            else:
                return res
                
        except Exception as e:
            logger.warning(f"MCP tool {tool} failed: {e!r}")
            raise HTTPException(status_code=502, detail=str(e))


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    app_id: str
    objective: str
    goal: Optional[str] = None
    modernization_goal: Optional[str] = None
    modernization_type: Optional[str] = None
    criteria: Optional[List[str]] = None
    advisor_id: Optional[str] = None
    strategy: str
    risk_profile: str
    vulnerabilities: Optional[str] = None
    db_migration: str
    rewrite_mainframe: Optional[str] = ""
    target_lang: Optional[str] = ""
    mcp_url: Optional[str] = None
    mcp_key: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_key: Optional[str] = None
    llm_model: Optional[str] = None
    searchapi_key: Optional[str] = None
    use_llm: Optional[bool] = False
    include_locations: Optional[bool] = False

from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from app.tools.document_generator import generate_docx_from_markdown

# In-memory store for demo
flow_states = {}

import json

def parse_mcp_response(res):
    logger.debug(f"parse_mcp_response called with type {type(res)}: {repr(res)[:200]}")
    def _try_load(s: str):
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            try:
                return json.loads(s, strict=False)
            except Exception:
                # Escape invalid backslash sequences (e.g., \_, \x not valid JSON)
                s2 = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s)
                try:
                    return json.loads(s2, strict=False)
                except Exception:
                    # Strip control chars as a last resort
                    s3 = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", s2)
                    return json.loads(s3, strict=False)
    if isinstance(res, dict):
        content = res.get("content", [])
        if isinstance(content, list) and len(content) > 0:
            first = content[0]
            if isinstance(first, dict) and first.get("type") == "text":
                text_content = first.get("text", "")
                try:
                    clean_str = text_content.replace('\\n', '\n')
                    return _try_load(clean_str)
                except Exception as e:
                    logger.error(f"Error parsing MCP JSON content: {e}")
                    pass
        
        # Legacy fallback
        if "content" in res and isinstance(res["content"], str):
            try:
                clean_str = res["content"].replace('\\n', '\n')
                return _try_load(clean_str)
            except:
                pass
        if "items" in res:
            return res["items"]
    if isinstance(res, list):
        return res
    return res

def _try_parse_json_str(s: str):
    if not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    candidates = [
        s,
        s.replace("\\n", "\n"),
        s.replace("\\r", "\r"),
        s.replace("\\n", "\n").replace("\\r", "\r"),
        re.sub("\\\\\r?\n", "\n", s),
        re.sub("\\\\\r?\n", "\n", s.replace("\\n", "\n")),
    ]
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
        except Exception:
            continue
    try:
        return json.loads(s, strict=False)
    except json.JSONDecodeError:
        try:
            return json.loads(s.replace("\\n", "\n").replace("\\r", "\r"), strict=False)
        except Exception:
            try:
                s2 = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s)
                return json.loads(s2, strict=False)
            except Exception:
                try:
                    s3 = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", s)
                    return json.loads(s3, strict=False)
                except Exception:
                    return None

def _extract_first_dict_from_stats_payload(obj):
    def _from_any(x):
        if isinstance(x, list) and x:
            return x[0] if isinstance(x[0], dict) else None
        if isinstance(x, dict):
            return x
        return None

    if isinstance(obj, list):
        return obj[0] if obj and isinstance(obj[0], dict) else None

    if isinstance(obj, dict):
        sc = obj.get("structuredContent")
        if isinstance(sc, dict) and isinstance(sc.get("content"), str):
            parsed = _try_parse_json_str(sc["content"])
            first = _from_any(parsed)
            if first is not None:
                return first

        content = obj.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
                parsed = _try_parse_json_str(first["text"])
                if isinstance(parsed, dict) and isinstance(parsed.get("content"), str):
                    parsed2 = _try_parse_json_str(parsed["content"])
                    first2 = _from_any(parsed2)
                    if first2 is not None:
                        return first2
                first = _from_any(parsed)
                if first is not None:
                    return first

        if isinstance(content, str):
            parsed = _try_parse_json_str(content)
            if isinstance(parsed, dict) and isinstance(parsed.get("content"), str):
                parsed2 = _try_parse_json_str(parsed["content"])
                first2 = _from_any(parsed2)
                if first2 is not None:
                    return first2
            first = _from_any(parsed)
            if first is not None:
                return first

    return None

def _infer_mainframe(obj):
    if not isinstance(obj, dict):
        return False
    if isinstance(obj.get("mainframe"), bool):
        return bool(obj.get("mainframe"))
    platforms = obj.get("platforms")
    if isinstance(platforms, dict) and isinstance(platforms.get("mainframe"), bool):
        return bool(platforms.get("mainframe"))
    keywords = (
        "mainframe",
        "cobol",
        "jcl",
        "cics",
        "ims",
        "db2",
        "vsam",
        "z/os",
        "zos",
        "pl/i",
        "pli",
        "pl1",
        "natural",
        "adabas",
        "rpg",
        "as/400",
        "as400",
        "ibm i",
        "ibm z",
    )
    for k in ("technologies", "element_types"):
        v = obj.get(k)
        if isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    s = item.strip().lower()
                    if any(kw in s for kw in keywords):
                        return True
        if isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, list):
                    for item in vv:
                        if isinstance(item, str):
                            s = item.strip().lower()
                            if any(kw in s for kw in keywords):
                                return True
    return False

from app.backend.crew import ModernizationCrew
from crewai import Crew, Task

@app.get("/applications")
async def get_applications(request: Request):
    mcp_url = _normalize_mcp_url(request.headers.get("x-mcp-url") or CAST_MCP_URL)
    mcp_key = request.headers.get("x-api-key") or CAST_X_API_KEY
    llm_provider = request.headers.get("x-llm-provider") or "openrouter"
    llm_key = request.headers.get("x-llm-key") or os.environ.get("OPENROUTER_API_KEY", "")
    llm_model = request.headers.get("x-llm-model") or os.environ.get("OPENROUTER_MODEL") or "openai/gpt-4o"
    
    if not mcp_url or not mcp_key:
        raise HTTPException(status_code=400, detail="Missing CAST MCP credentials.")
    
    mcp = MCPServerHTTP(mcp_url, mcp_key)
    try:
        await mcp.open()
        
        loop = asyncio.get_running_loop()
        mod_crew = ModernizationCrew(llm_provider=llm_provider, llm_key=llm_key, llm_model=llm_model, mcp_client=mcp, loop=loop)
        
        portfolio_agent = mod_crew.portfolio_specialist()
        portfolio_task = Task(
            description="List all available applications using the 'applications' tool and return them in JSON format.",
            expected_output="A list of applications to populate the UI.",
            agent=portfolio_agent
        )
        
        mini_crew = Crew(
            agents=[portfolio_agent],
            tasks=[portfolio_task],
            verbose=True
        )
        
        result = await asyncio.to_thread(mini_crew.kickoff)
        
        # We also call MCP directly as a reliable fallback for UI rendering 
        # since LLM parsing of arrays might sometimes be unpredictable
        try:
            res = await mcp.invoke_tool("applications", {})
            def _extract_apps(obj):
                def _try_parse_array_string(s: str):
                    candidates = [
                        s,
                        s.replace("\\n", "\n"),
                        s.replace("\\r", "\r"),
                        s.replace("\\n", "\n").replace("\\r", "\r"),
                        s.replace('\\"', '"'),
                        s.replace('\\"', '"').replace("\\n", "\n").replace("\\r", "\r"),
                        s.replace("\\\\n", "\\n"),
                        s.replace("\\\\n", "\\n").replace("\\n", "\n").replace("\\r", "\r"),
                        s.replace("\\\\n", "\\n").replace('\\"', '"').replace("\\n", "\n").replace("\\r", "\r"),
                    ]
                    for c in candidates:
                        try:
                            arr = json.loads(c)
                            if isinstance(arr, list):
                                return arr
                        except Exception:
                            pass
                    try:
                        import re as _re
                        m = _re.search(r"\[[\s\S]*\]", s)
                        if m:
                            for c in (m.group(0), m.group(0).replace("\\n", "\n")):
                                try:
                                    arr = json.loads(c)
                                    if isinstance(arr, list):
                                        return arr
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    return None
                # Already an array
                if isinstance(obj, list):
                    return obj
                # Inner JSON object with stringified array under 'content'
                if isinstance(obj, dict):
                    content = obj.get("content")
                    if isinstance(content, str):
                        arr = _try_parse_array_string(content)
                        if isinstance(arr, list):
                            return arr
                    # structuredContent.content path
                    sc = obj.get("structuredContent", {})
                    if isinstance(sc, dict) and isinstance(sc.get("content"), str):
                        arr = _try_parse_array_string(sc["content"])
                        if isinstance(arr, list):
                            return arr
                return None
            # Prefer MCP structuredContent payload (most reliable)
            try:
                sc_content = res.get("structuredContent", {}).get("content") if isinstance(res, dict) else None
                if isinstance(sc_content, str):
                    arr = _extract_apps({"structuredContent": {"content": sc_content}})
                    if isinstance(arr, list):
                        return arr
            except Exception:
                pass

            parsed = parse_mcp_response(res)
            apps_arr = _extract_apps(parsed)
            if apps_arr is not None:
                return apps_arr
        except:
            pass
            
        # Return the LLM's raw output if fallback fails
        # Try to recover a JSON array from the LLM's raw output
        try:
            if isinstance(result.raw, str):
                import re as _re
                m = _re.search(r"\[[\s\S]*\]", result.raw)
                if m:
                    arr = json.loads(m.group(0))
                    if isinstance(arr, list):
                        return arr
        except Exception:
            pass
        return []
        
    except Exception as e:
        logger.error(f"Error fetching apps: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch applications: {e}")
    finally:
        try:
            await mcp.aclose()
        except Exception as e:
            logger.warning(f"MCP close failed in /applications: {e!r}")

@app.get("/config")
async def get_config():
    return {
        "default_mcp_url": CAST_MCP_URL,
        "server_has_mcp_key": bool(CAST_X_API_KEY),
    }

@app.get("/advisors")
async def get_advisors(request: Request, app_id: str = Query(...)):
    mcp_url = _normalize_mcp_url(request.headers.get("x-mcp-url") or CAST_MCP_URL)
    mcp_key = request.headers.get("x-api-key") or CAST_X_API_KEY
    if not mcp_url or not mcp_key:
        raise HTTPException(status_code=400, detail="Missing CAST MCP credentials.")

    mcp = MCPServerHTTP(mcp_url, mcp_key)
    try:
        await mcp.open()
        res = await mcp.invoke_tool("advisors", {"application": app_id, "focus": "list", "page": 1})
        parsed = parse_mcp_response(res)
        if isinstance(parsed, dict) and isinstance(parsed.get("content"), str):
            inner = _try_parse_json_str(parsed.get("content"))
            if inner is not None:
                parsed = inner
        items = None
        if isinstance(parsed, list):
            items = parsed
        elif isinstance(parsed, dict):
            for k in ("items", "advisors", "results", "data"):
                if isinstance(parsed.get(k), list):
                    items = parsed.get(k)
                    break
            if items is None and isinstance(parsed.get("content"), list):
                items = parsed.get("content")
        return {"items": items or []}
    finally:
        try:
            await mcp.aclose()
        except Exception:
            pass

@app.get("/dna")
async def get_dna(request: Request, app_id: str = Query(...)):
    mcp_url = _normalize_mcp_url(request.headers.get("x-mcp-url") or CAST_MCP_URL)
    mcp_key = request.headers.get("x-api-key") or CAST_X_API_KEY
    
    if not mcp_url or not mcp_key:
        raise HTTPException(status_code=400, detail="Missing CAST MCP credentials.")
        
    mcp = MCPServerHTTP(mcp_url, mcp_key)
    try:
        await mcp.open()

        try:
            res = await mcp.invoke_tool("stats", {"application": app_id})
            stats_obj = _extract_first_dict_from_stats_payload(res)
            if stats_obj is None:
                parsed = parse_mcp_response(res)
                stats_obj = _extract_first_dict_from_stats_payload(parsed)
                if stats_obj is None and isinstance(parsed, dict):
                    stats_obj = parsed
            if stats_obj is None:
                stats_obj = {"name": app_id}
            if not isinstance(stats_obj.get("name"), str) or not stats_obj.get("name"):
                stats_obj["name"] = app_id
            if not isinstance(stats_obj.get("application"), str) or not stats_obj.get("application"):
                stats_obj["application"] = app_id
            if not isinstance(stats_obj.get("mainframe"), bool):
                stats_obj["mainframe"] = _infer_mainframe(stats_obj)
            return stats_obj
        except Exception as fallback_e:
            logger.warning(f"Fallback DNA fetch failed: {fallback_e}")
            pass
            
    except Exception as e:
        logger.error(f"Error fetching DNA: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch DNA: {e}")
    finally:
        try:
            await mcp.aclose()
        except Exception as e:
            logger.warning(f"MCP close failed in /dna: {e!r}")

@app.post("/kickoff")
async def kickoff_mission(req: AnalyzeRequest):
    # Instead of blocking, we initiate the flow and return an ID
    job_id = req.app_id
    existing = flow_states.get(job_id)
    if isinstance(existing, dict) and existing.get("status") == "started":
        raise HTTPException(status_code=409, detail="A mission is already running for this application. Please wait for it to complete.")
    flow_states[job_id] = {
        "req": req.dict(),
        "status": "started",
        "updates": [],
        "report": None
    }
    return {"job_id": job_id, "message": "Mission started"}

@app.get("/analyze/stream/{job_id}")
async def analyze_stream(request: Request, job_id: str):
    async def event_generator():
        state = flow_states.get(job_id)
        if not state:
            yield {"event": "error", "data": "Job not found"}
            return
            
        req_data = state["req"]
        
        # Initialize and configure the flow
        mcp_url = _normalize_mcp_url(req_data.get("mcp_url") or CAST_MCP_URL)
        mcp_key = req_data.get("mcp_key") or CAST_X_API_KEY
        if not mcp_url or not mcp_key:
            yield {"event": "error", "data": "Missing CAST MCP credentials. Set them in the UI Settings or provide CAST_MCP_URL and CAST_X_API_KEY via environment variables."}
            return
        mcp_client = MCPServerHTTP(mcp_url, mcp_key)
        try:
            await mcp_client.open()
            
            flow = ModernizationFlow(mcp_client=mcp_client)
            flow.state.selected_app_id = job_id
            flow.state.mission_params = req_data
            
            # We start the flow manually for SSE stream
            yield {"event": "message", "data": "Flow initialized."}
            
            # Discover
            await flow.discover_portfolio()
            for update in flow.state.status_updates:
                yield {"event": "message", "data": update}
                await asyncio.sleep(0.5)
            flow.state.status_updates.clear()
            
            # Profile
            await flow.profile_application()
            for update in flow.state.status_updates:
                yield {"event": "message", "data": update}
                await asyncio.sleep(0.5)
            flow.state.status_updates.clear()
            
            # Execute (LLM)
            await flow.execute_mission()
            for update in flow.state.status_updates:
                yield {"event": "message", "data": update}
                await asyncio.sleep(0.5)
            flow.state.status_updates.clear()
            
            # Validate (LLM)
            await flow.validate_iso5055()
            for update in flow.state.status_updates:
                yield {"event": "message", "data": update}
                await asyncio.sleep(0.5)
            flow.state.status_updates.clear()
            
            report = {
                "executive_summary": flow.state.mission_report or "",
                "architecture_insights": "",
                "modernization_roadmap": "",
                "iso_5055_flaws": flow.state.validation_report or "",
                "disclaimer": DISCLAIMER_TEXT
            }
            state["report"] = report
            state["status"] = "completed"
            if isinstance(state.get("req"), dict):
                state["req"].pop("mcp_key", None)
                state["req"].pop("llm_key", None)
            
            yield {"event": "complete", "data": json.dumps(report)}
        except Exception as e:
            logger.exception("Analyze stream failed")
            state["status"] = "error"
            state["report"] = {
                "executive_summary": "",
                "architecture_insights": "",
                "modernization_roadmap": "",
                "iso_5055_flaws": "",
                "disclaimer": DISCLAIMER_TEXT,
                "error": str(e),
            }
            if isinstance(state.get("req"), dict):
                state["req"].pop("mcp_key", None)
                state["req"].pop("llm_key", None)
            yield {"event": "error", "data": f"Analyze stream failed: {e}"}
        finally:
            await mcp_client.aclose()
        
    return EventSourceResponse(event_generator())

@app.get("/report/download/{job_id}")
async def download_report(job_id: str):
    state = flow_states.get(job_id)
    if not state or not state.get("report"):
        raise HTTPException(status_code=404, detail="Report not found")
        
    report = state["report"]
    md = (
        f"{report.get('executive_summary', '')}\n\n"
        f"{report.get('architecture_insights', '')}\n\n"
        f"{report.get('modernization_roadmap', '')}\n\n"
        f"{report.get('iso_5055_flaws', '')}\n\n"
        f"{report.get('disclaimer', '')}"
    )
    
    app_name = state["req"].get("app_id", job_id)
    file_stream = generate_docx_from_markdown(md, app_name)
    headers = {
        'Content-Disposition': f'attachment; filename="{app_name}_Modernization_Roadmap.docx"'
    }
    return StreamingResponse(file_stream, headers=headers, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    ico_path = frontend_dir / "favicon.ico"
    if ico_path.exists():
        return FileResponse(str(ico_path), media_type="image/x-icon")
    png_path = frontend_dir / "assets" / "Archaion - agentic platform.png"
    if png_path.exists():
        return FileResponse(str(png_path), media_type="image/png")
    return Response(status_code=204)

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
    uvicorn.run("app.backend.main:app", host="0.0.0.0", port=9999, reload=True)
