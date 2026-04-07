import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import logging
import asyncio
from typing import Dict, Any, Optional
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

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("archaion.backend")
logger.setLevel(logging.DEBUG)

class MCPServerHTTP:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
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
            await self._stack.__aexit__(None, None, None)

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
    goal: str
    strategy: str
    risk_profile: str
    vulnerabilities: str
    db_migration: str
    rewrite_mainframe: Optional[str] = ""
    target_lang: Optional[str] = ""
    mcp_url: Optional[str] = None
    mcp_key: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_key: Optional[str] = None

from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from app.tools.document_generator import generate_docx_from_markdown

# In-memory store for demo
flow_states = {}

import json

def parse_mcp_response(res):
    logger.debug(f"parse_mcp_response called with type {type(res)}: {repr(res)[:200]}")
    if isinstance(res, dict):
        content = res.get("content", [])
        if isinstance(content, list) and len(content) > 0:
            first = content[0]
            if isinstance(first, dict) and first.get("type") == "text":
                text_content = first.get("text", "")
                try:
                    clean_str = text_content.replace('\\n', '\n')
                    return json.loads(clean_str)
                except Exception as e:
                    logger.error(f"Error parsing MCP JSON content: {e}")
                    pass
        
        # Legacy fallback
        if "content" in res and isinstance(res["content"], str):
            try:
                clean_str = res["content"].replace('\\n', '\n')
                return json.loads(clean_str)
            except:
                pass
        if "items" in res:
            return res["items"]
    if isinstance(res, list):
        return res
    return res

from app.backend.crew import ModernizationCrew
from crewai import Crew, Task

@app.get("/applications")
async def get_applications(request: Request):
    mcp_url = request.headers.get("x-mcp-url") or CAST_MCP_URL
    mcp_key = request.headers.get("x-api-key") or CAST_X_API_KEY
    llm_provider = request.headers.get("x-llm-provider") or "openrouter"
    llm_key = request.headers.get("x-llm-key") or os.environ.get("OPENROUTER_API_KEY", "")
    
    if not mcp_url or not mcp_key:
        raise HTTPException(status_code=400, detail="Missing CAST MCP credentials.")
    
    mcp = MCPServerHTTP(mcp_url, mcp_key)
    try:
        await mcp.open()
        
        loop = asyncio.get_running_loop()
        mod_crew = ModernizationCrew(llm_provider=llm_provider, llm_key=llm_key, mcp_client=mcp, loop=loop)
        
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
            parsed = parse_mcp_response(res)
            if parsed:
                return parsed
        except:
            pass
            
        # Return the LLM's raw output if fallback fails
        return [{"id": "llm-output", "name": result.raw}]
        
    except Exception as e:
        logger.error(f"Error fetching apps: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch applications: {e}")
    finally:
        await mcp.aclose()

@app.get("/config")
async def get_config():
    return {"default_mcp_url": CAST_MCP_URL}

@app.get("/dna")
async def get_dna(request: Request, app_id: str = Query(...)):
    mcp_url = request.headers.get("x-mcp-url") or CAST_MCP_URL
    mcp_key = request.headers.get("x-api-key") or CAST_X_API_KEY
    llm_provider = request.headers.get("x-llm-provider") or "openrouter"
    llm_key = request.headers.get("x-llm-key") or os.environ.get("OPENROUTER_API_KEY", "")
    
    if not mcp_url or not mcp_key:
        raise HTTPException(status_code=400, detail="Missing CAST MCP credentials.")
        
    mcp = MCPServerHTTP(mcp_url, mcp_key)
    try:
        await mcp.open()
        
        loop = asyncio.get_running_loop()
        mod_crew = ModernizationCrew(llm_provider=llm_provider, llm_key=llm_key, mcp_client=mcp, loop=loop)
        
        profile_agent = mod_crew.system_profile_analyst()
        profile_task = Task(
            description=f"Analyze the Application Technical DNA Profile for {app_id} using 'stats' and 'architectural_graph'. Return a JSON containing LOC, elements, interactions, and a boolean 'mainframe_detected'.",
            expected_output="A JSON object representing the system technical profile.",
            agent=profile_agent
        )
        
        mini_crew = Crew(
            agents=[profile_agent],
            tasks=[profile_task],
            verbose=True
        )
        
        # We also call MCP directly as a reliable fallback for UI rendering 
        try:
            res = await mcp.invoke_tool("stats", {"application": app_id})
            parsed = parse_mcp_response(res)
            # Add simple heuristic if missing
            dna_str = json.dumps(parsed).lower()
            if "mainframe" not in parsed:
                parsed["mainframe"] = "cobol" in dna_str or "mainframe" in dna_str or "jcl" in dna_str
                
            # Fire and forget the LLM profiling so we aren't blocking the UI too long
            # asyncio.create_task(asyncio.to_thread(mini_crew.kickoff))
            
            # Or run it synchronously to fully fulfill prompt:
            await asyncio.to_thread(mini_crew.kickoff)
            
            return parsed
        except Exception as fallback_e:
            logger.warning(f"Fallback DNA fetch failed: {fallback_e}")
            pass
            
    except Exception as e:
        logger.error(f"Error fetching DNA: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch DNA: {e}")
    finally:
        await mcp.aclose()

@app.post("/kickoff")
async def kickoff_mission(req: AnalyzeRequest):
    # Instead of blocking, we initiate the flow and return an ID
    job_id = req.app_id
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
        mcp_url = req_data.get("mcp_url") or CAST_MCP_URL
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
                "iso_5055_flaws": flow.state.validation_report or ""
            }
            state["report"] = report
            state["status"] = "completed"
            
            yield {"event": "complete", "data": json.dumps(report)}
        except Exception as e:
            logger.exception("Analyze stream failed")
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
    md = f"{report.get('executive_summary', '')}\n\n{report.get('architecture_insights', '')}\n\n{report.get('modernization_roadmap', '')}\n\n{report.get('iso_5055_flaws', '')}"
    
    app_name = state["req"].get("app_id", job_id)
    file_stream = generate_docx_from_markdown(md, app_name)
    headers = {
        'Content-Disposition': f'attachment; filename="{app_name}_Modernization_Roadmap.docx"'
    }
    return StreamingResponse(file_stream, headers=headers, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

# Serve the frontend statically at the root
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
    uvicorn.run("app.backend.main:app", host="0.0.0.0", port=9999, reload=True)
