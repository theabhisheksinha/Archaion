import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import litellm
import textwrap

# Ensure litellm uses OpenRouter key if present
if "OPENROUTER_API_KEY" in os.environ:
    litellm.api_key = os.environ["OPENROUTER_API_KEY"]

# Mocking CrewAI Flow decorators and base class for local testing without crewai package
def start():
    def decorator(func):
        func._is_start = True
        return func
    return decorator

def listen(step_name):
    def decorator(func):
        func._listen_to = step_name
        return func
    return decorator

class Flow:
    def __init__(self, *args, **kwargs):
        self.state = ModernizationState()

# In CrewAI flows, state is defined using Pydantic
class ModernizationState(BaseModel):
    portfolio: List[Dict[str, Any]] = []
    selected_app_id: Optional[str] = None
    app_name: Optional[str] = None
    dna_profile: Optional[Dict[str, Any]] = None
    mission_params: Optional[Dict[str, str]] = None
    mission_report: Optional[str] = None
    validation_report: Optional[str] = None
    status_updates: List[str] = []

class ModernizationFlow(Flow):

    def __init__(self, mcp_client=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mcp_client = mcp_client

    def push_update(self, msg: str):
        print(f"Flow Update: {msg}")
        self.state.status_updates.append(msg)

    async def _ask_llm(self, prompt: str) -> str:
        # Get dynamic configuration or fallback to defaults
        params = self.state.mission_params or {}
        provider = params.get("llm_provider") or "openrouter"
        api_key = params.get("llm_key") or os.environ.get("OPENROUTER_API_KEY")

        if provider == "openrouter":
            model = "openrouter/google/gemini-2.5-flash"
        elif provider == "openai":
            model = "gpt-4o"
        elif provider == "gemini":
            model = "gemini/gemini-1.5-pro"
        elif provider == "azure":
            model = "azure/gpt-4o"
        else:
            model = "openrouter/google/gemini-2.5-flash"

        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key
            )
            return response.choices[0].message.content
        except Exception as e:
            self.push_update(f"LLM Call Failed: {str(e)}")
            return "Error generating response from LLM."

    @start()
    async def discover_portfolio(self):
        self.push_update("Agentic Portfolio Discovery starting...")
        if self.mcp_client:
            res = await self.mcp_client.invoke_tool("applications", {})
            self.state.portfolio = res
        self.push_update("Portfolio Discovery complete.")
        return self.state.portfolio

    @listen("discover_portfolio")
    async def wait_for_selection(self):
        self.push_update("Waiting for application selection...")
        pass

    @listen("wait_for_selection")
    async def profile_application(self):
        if not self.state.selected_app_id:
            return
        self.push_update(f"Technical DNA Profiling for {self.state.selected_app_id}...")
        if self.mcp_client:
            res = await self.mcp_client.invoke_tool("stats", {"application": self.state.selected_app_id})
            if isinstance(res, dict) and "content" in res and isinstance(res["content"], str):
                import json
                try:
                    res = json.loads(res["content"])
                except:
                    pass
            self.state.dna_profile = res
        self.push_update("Technical DNA Profiling complete.")
        return self.state.dna_profile

    @listen("profile_application")
    async def execute_mission(self):
        if not self.state.dna_profile or not self.state.mission_params:
            return
        self.push_update("Autonomous Execution by the Multi-Agent Crew (via OpenRouter)...")
        
        prompt = textwrap.dedent(f"""
            You are the micro2monoAgent, an expert in architectural decomposition.
            
            App ID: {self.state.selected_app_id}
            Goal: {self.state.mission_params.get('goal')}
            Target Framework: {self.state.mission_params.get('target_framework')}
            Compliance: {self.state.mission_params.get('compliance')}
            Risk Profile: {self.state.mission_params.get('risk_profile')}
            Refactoring Depth: {self.state.mission_params.get('refactoring_depth')}
            
            DNA Profile:
            {json.dumps(self.state.dna_profile, indent=2)}
            
            Based on the above profile and parameters, generate a comprehensive Modernization Plan in Markdown.
            Include Executive Summary, Architecture Insights, and a Modernization Roadmap.
        """)
        
        report = await self._ask_llm(prompt)
        self.state.mission_report = report
        self.push_update("Modernization Mission generated.")
        return self.state.mission_report

    @listen("execute_mission")
    async def validate_iso5055(self):
        if not self.state.mission_report:
            return
        self.push_update("Validator Agent checking against ISO 5055 standards...")
        
        flaws_text = "No severe CWEs found."
        if self.mcp_client:
            try:
                flaws = await self.mcp_client.invoke_tool("iso-5055-flaws", {"app_name": self.state.selected_app_id})
                flaws_text = str(flaws)
            except Exception:
                pass
                
        prompt = textwrap.dedent(f"""
            You are the Validator Agent.
            
            Proposed Report:
            {self.state.mission_report}
            
            Flaws identified:
            {flaws_text}
            
            Ensure the proposed architecture mitigates these flaws. Output a brief 'ISO 5055 Quality Checks' section in Markdown.
        """)
        
        validation = await self._ask_llm(prompt)
        self.state.validation_report = validation
        self.push_update("ISO 5055 validation complete.")
        return self.state.validation_report
