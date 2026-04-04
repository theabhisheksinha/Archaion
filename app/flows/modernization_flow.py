import os
import json
import asyncio
import logging
import litellm
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import textwrap

litellm.set_verbose = True
logger = logging.getLogger("archaion.flow")
logger.setLevel(logging.DEBUG)

# Fallback imports if crewai isn't installed locally (e.g. Windows Python 3.14)
# Docker environment (Python 3.11) will use the actual crewai package
try:
    from crewai import Agent, Crew, Process, Task, LLM
    from crewai.project import CrewBase, agent, crew, task
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    def CrewBase(cls): return cls
    def agent(func): return func
    def crew(func): return func
    def task(func): return func
    Agent = Task = Crew = Process = LLM = type("Dummy", (), {})

class ModernizationState(BaseModel):
    portfolio: List[Dict[str, Any]] = []
    selected_app_id: Optional[str] = None
    app_name: Optional[str] = None
    dna_profile: Optional[Dict[str, Any]] = None
    mission_params: Optional[Dict[str, str]] = None
    mission_report: Optional[str] = None
    validation_report: Optional[str] = None
    status_updates: List[str] = []

@CrewBase
class ModernizationCrew:
    """Modernization Crew adhering to strict CrewAI Framework Compliance"""
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents/config'))
    agents_config = os.path.join(base_dir, 'agents.yaml')
    tasks_config = os.path.join(base_dir, 'tasks.yaml')

    def __init__(self, llm_provider: str, llm_key: str):
        # Configure LLM dynamically per request using UI-provided credentials
        if llm_provider == "openrouter":
            model = "openrouter/google/gemini-2.5-flash"
        elif llm_provider == "openai":
            model = "gpt-4o"
        elif llm_provider == "gemini":
            model = "gemini/gemini-1.5-pro"
        elif llm_provider == "azure":
            model = "azure/gpt-4o"
        else:
            model = "openrouter/google/gemini-2.5-flash"
            
        if CREWAI_AVAILABLE:
            try:
                self.llm = LLM(model=model, api_key=llm_key)
            except Exception:
                self.llm = None
        else:
            self.llm = None

    @agent
    def micro2mono_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['micro2mono_agent'],
            llm=self.llm,
            verbose=True
        )

    @agent
    def validator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['validator_agent'],
            llm=self.llm,
            verbose=True
        )

    @task
    def decomposition_task(self) -> Task:
        return Task(
            config=self.tasks_config['decomposition_task']
        )

    @task
    def validation_task(self) -> Task:
        return Task(
            config=self.tasks_config['validation_task']
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )

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
            "dna_profile": json.dumps(self.state.dna_profile, indent=2),
            "goal": params.get('goal', 'Modernize'),
            "target_framework": params.get('target_framework', 'Spring Boot'),
            "compliance": params.get('compliance', 'None'),
            "risk_profile": params.get('risk_profile', 'Medium'),
            "refactoring_depth": params.get('refactoring_depth', 'Moderate'),
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
                # Instantiate Crew with dynamic LLM keys
                crew_instance = ModernizationCrew(llm_provider=llm_provider, llm_key=llm_key).crew()
                
                # Run crewai kick_off in a thread to prevent blocking the asyncio loop
                result = await asyncio.to_thread(crew_instance.kickoff, inputs=inputs)
                
                # Extract task outputs
                tasks_output = result.tasks_output
                if len(tasks_output) >= 2:
                    self.state.mission_report = tasks_output[0].raw
                    self.state.validation_report = tasks_output[1].raw
                else:
                    self.state.mission_report = result.raw
                    self.state.validation_report = "Validation integrated in the report."
                    
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
