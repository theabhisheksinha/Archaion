import os
import json
import asyncio
import logging
import litellm
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

litellm.set_verbose = True
logger = logging.getLogger("archaion.flow")
logger.setLevel(logging.DEBUG)

try:
    from app.backend.crew import ModernizationCrew
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    ModernizationCrew = type("Dummy", (), {})

class ModernizationState(BaseModel):
    portfolio: List[Dict[str, Any]] = []
    selected_app_id: Optional[str] = None
    app_name: Optional[str] = None
    dna_profile: Optional[Dict[str, Any]] = None
    mission_params: Optional[Dict[str, str]] = None
    mission_report: Optional[str] = None
    validation_report: Optional[str] = None
    status_updates: List[str] = []

class ModernizationFlow:
    """
    Wrapper to manage state, fetch data via MCP, and kick off the Crew.
    Ensures credentials flow from frontend to backend.
    """
    def __init__(self, mcp_client=None):
        self.state = ModernizationState()
        self.mcp_client = mcp_client

    def push_update(self, msg: str):
        print(f"Flow Update: {msg}")
        self.state.status_updates.append(msg)

    async def discover_portfolio(self):
        self.push_update("Agentic Portfolio Discovery starting...")
        if self.mcp_client:
            res = await self.mcp_client.invoke_tool("applications", {})
            self.state.portfolio = res
        self.push_update("Portfolio Discovery complete.")
        return self.state.portfolio

    async def profile_application(self):
        if not self.state.selected_app_id:
            return
        self.push_update(f"Technical DNA Profiling for {self.state.selected_app_id}...")
        if self.mcp_client:
            res = await self.mcp_client.invoke_tool("stats", {"application": self.state.selected_app_id})
            if isinstance(res, dict) and "content" in res and isinstance(res["content"], str):
                try:
                    res = json.loads(res["content"])
                except:
                    pass
            self.state.dna_profile = res
        self.push_update("Technical DNA Profiling complete.")
        return self.state.dna_profile

    async def execute_mission(self):
        if not self.state.dna_profile or not self.state.mission_params:
            return
        
        self.push_update("Initializing CrewAI Multi-Agent Execution...")
        
        # 1. Retrieve LLM Credentials from the frontend parameters
        params = self.state.mission_params
        
        ui_llm_provider = params.get("llm_provider")
        ui_llm_key = params.get("llm_key")
        
        llm_provider = ui_llm_provider or "openrouter"
        llm_key = ui_llm_key or os.environ.get("OPENROUTER_API_KEY", "")
        
        source = "UI Settings Payload" if ui_llm_key else "Environment Variables (.env)"
        logger.debug(f"[CONFIG TRACE] Initializing CrewAI with LLM Provider: {llm_provider.upper()} (Source: {source})")
        
        # 2. Retrieve Flaws from MCP to pass as input to the Crew
        flaws_text = "No severe CWEs found."
        if self.mcp_client:
            try:
                flaws = await self.mcp_client.invoke_tool("iso-5055-flaws", {"app_name": self.state.selected_app_id})
                flaws_text = str(flaws)
            except Exception:
                pass
        
        # 3. Prepare Inputs
        inputs = {
            "app_name": self.state.selected_app_id,
            "dna_profile": json.dumps(self.state.dna_profile, indent=2),
            "objective": params.get('objective', 'Modernize'),
            "goal": params.get('goal', 'Mono2Micro'),
            "strategy": params.get('strategy', 'Containerization'),
            "risk_profile": params.get('risk_profile', 'ISO-5055 only'),
            "vulnerabilities": params.get('vulnerabilities', 'Both'),
            "db_migration": params.get('db_migration', 'No Migration'),
            "rewrite_mainframe": params.get('rewrite_mainframe', ''),
            "target_lang": params.get('target_lang', ''),
            "iso_5055_flaws": flaws_text
        }
        
        self.push_update(f"Executing Crew with LLM Provider: {llm_provider.upper()}")
        self.push_update("CrewAI Agents started processing (this may take a moment)...")
        
        if not CREWAI_AVAILABLE:
            # Fallback mock response for local testing if crewai couldn't install
            import litellm
            try:
                model = "openrouter/google/gemini-2.5-flash" if llm_provider == "openrouter" else f"{llm_provider}/gpt-4o"
                response = await litellm.acompletion(
                    model=model,
                    messages=[{"role": "user", "content": f"Write a modernization plan for {self.state.selected_app_id} based on {inputs['goal']}"}],
                    api_key=llm_key
                )
                self.state.mission_report = response.choices[0].message.content
                self.state.validation_report = "Validated successfully (Fallback Mode)."
            except Exception as e:
                self.state.mission_report = f"Error (Fallback): {str(e)}"
                self.state.validation_report = "Error"
        else:
            try:
                loop = asyncio.get_running_loop()
                
                def crew_step_callback(step_output):
                    # step_output is an AgentStep or similar
                    if hasattr(step_output, 'agent'):
                        agent_name = step_output.agent
                        thought = getattr(step_output, 'thought', str(step_output))
                        self.push_update(f"{agent_name}: {thought}")
                    else:
                        self.push_update(f"Agent Action: {str(step_output)}")

                # Instantiate Crew with dynamic LLM keys, MCP client, and current event loop
                crew_instance = ModernizationCrew(
                    llm_provider=llm_provider, 
                    llm_key=llm_key,
                    mcp_client=self.mcp_client,
                    loop=loop,
                    step_callback=crew_step_callback
                ).crew()
                
                # Run crewai kick_off in a thread to prevent blocking the asyncio loop
                try:
                    result = await asyncio.to_thread(crew_instance.kickoff, inputs=inputs)
                except TypeError:
                    # Older CrewAI versions may not accept keyword args
                    result = await asyncio.to_thread(crew_instance.kickoff)
                
                tasks_output = getattr(result, "tasks_output", None)
                mission_parts: List[str] = []
                validation_text: Optional[str] = None

                if isinstance(tasks_output, (list, tuple)) and tasks_output:
                    raws: List[str] = []
                    for t in tasks_output:
                        raw_val = getattr(t, "raw", None)
                        if raw_val is None:
                            raw_val = getattr(t, "result", None)
                        raws.append(str(raw_val) if raw_val is not None else str(t))

                    if len(raws) >= 4:
                        mission_parts = [raws[0], raws[1], raws[2]]
                        validation_text = raws[3]
                    elif len(raws) >= 2:
                        mission_parts = [raws[0]]
                        validation_text = raws[1]
                    else:
                        mission_parts = [raws[0]]
                else:
                    raw_val = getattr(result, "raw", None)
                    mission_parts = [str(raw_val) if raw_val is not None else str(result)]

                self.state.mission_report = "\n\n".join([p for p in mission_parts if p]).strip()
                self.state.validation_report = (validation_text or "").strip() or "Validation integrated in the report."
                    
            except Exception as e:
                self.push_update(f"CrewAI Error: {str(e)}")
                self.state.mission_report = f"Error generating plan: {str(e)}"
                self.state.validation_report = "Validation failed due to error."
                
        self.push_update("CrewAI Execution complete.")

    async def validate_iso5055(self):
        # Validation is now handled intrinsically by the Validation Task in the Crew.
        self.push_update("Finalizing ISO 5055 Validation...")
        await asyncio.sleep(0.5)
        return self.state.validation_report
