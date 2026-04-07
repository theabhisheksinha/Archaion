import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from crewai import Agent, Crew, Task
from langchain_openai import ChatOpenAI

from app.tools.mcp_tools import create_mcp_tool

logger = logging.getLogger("archaion.crew")

class ModernizationCrew:
    _OPENROUTER_INTERNAL_MODELS: Dict[str, str] = {
        "default": "openai/gpt-4o",
        "manager": "openai/gpt-4o",
        "portfolio_specialist": "openai/gpt-4o-mini",
        "system_profile_analyst": "openai/gpt-4o-mini",
        "transformation_manager": "openai/gpt-4o",
        "data_architect": "openai/gpt-4o",
        "logic_specialist": "openai/gpt-4o",
        "risk_auditor": "openai/gpt-4o",
    }
    _AGENTS: Dict[str, Dict[str, str]] = {
        "portfolio_specialist": {
            "role": "Discovery Analyst",
            "goal": "Populate the UI with available applications upon initial load.",
            "backstory": "Senior IT Asset Manager. You ensure the interface represents the ground truth of the scanned portfolio.",
        },
        "system_profile_analyst": {
            "role": "Technical Profiler",
            "goal": "Generate the System Technical Profile for the selected application.",
            "backstory": "Architectural Archaeologist. You extract facts (LOC, interactions, stack) to ground the crew's reasoning.",
        },
        "transformation_manager": {
            "role": "Orchestrator Agent",
            "goal": "Synthesize user input (objective: {objective}, goal: {goal}, strategy: {strategy}) and delegate to specialists.",
            "backstory": "Modernization Program Director. You coordinate the Mission and ensure the final Word report is actionable.",
        },
        "data_architect": {
            "role": "DB Specialist",
            "goal": "Design the {db_migration} plan and map CRUD interaction hotspots.",
            "backstory": "Data Sovereignty Lead. You use deterministic schema maps to propose per-service database splits.",
        },
        "logic_specialist": {
            "role": "Legacy Transformation specialist",
            "goal": "Trace functional clusters and Mainframe {rewrite_mainframe} logic paths.",
            "backstory": "Senior Modernization Engineer. You trace JCL/COBOL paths back to cloud-native triggers.",
        },
        "risk_auditor": {
            "role": "Quality Specialist",
            "goal": "Audit the proposed architecture for ISO 5055 compliance (Security/Reliability).",
            "backstory": "Software Integrity Auditor. You ensure the new microservices are born clean and free of legacy vulnerabilities.",
        },
    }

    _TASKS: Dict[str, Dict[str, str]] = {
        "portfolio_task": {
            "description": "Discover applications from the CAST Imaging MCP server using the 'applications' tool.",
            "expected_output": "A list of applications to populate the UI.",
            "agent": "portfolio_specialist",
        },
        "profile_task": {
            "description": "Analyze the Application Technical DNA Profile:\n{dna_profile}\nExtract LOC, Elements, and Interactions. Check for Mainframe technology.",
            "expected_output": "A system technical profile summary.",
            "agent": "system_profile_analyst",
        },
        "orchestration_task": {
            "description": (
                "Coordinate the modernization mission for {app_name}.\n"
                "Objective: {objective}\n"
                "Goal: {goal}\n"
                "Strategy: {strategy}\n"
                "Target Language for Mainframe (if applicable): {target_lang}\n"
                "Ensure the final report includes all 10 mandatory sections:\n"
                "1. As-IS Architecture (Layering/Component structure)\n"
                "2. Present Database Architecture\n"
                "3. Database Access Patterns (CRUD hotspots)\n"
                "4. API Inventory & Anomalies\n"
                "5. Proposed Recommended Architecture (Microservices/Containerization)\n"
                "6. Rationale (Why this recommendation?)\n"
                "7. Mono2micro Decomposition (Code & DB refactoring steps)\n"
                "8. Cloud Service Map (Target Cloud rationale)\n"
                "9. Strategic Consulting Conclusion (Risk/ROI)\n"
                "10. Disclaimer: \"This is an AI generated report using deterministic details for {app_name} from CAST Imaging through its MCP Server.\"\n\n"
                "IMPORTANT: The final report must use specific Object IDs from the MCP tools as evidence for its refactoring recommendations."
            ),
            "expected_output": "A structured report outlining the modernization strategy, integrating inputs from all specialists, and strictly containing the 10 mandatory sections with Object ID evidence.",
            "agent": "transformation_manager",
        },
        "data_architecture_task": {
            "description": "Design the DB Migration plan based on {db_migration}. Map CRUD interaction hotspots.",
            "expected_output": "Database architecture and access patterns sections.",
            "agent": "data_architect",
        },
        "logic_transformation_task": {
            "description": "Trace functional clusters and Mainframe logic paths based on {rewrite_mainframe} instructions.",
            "expected_output": "Mono2micro decomposition and API inventory sections.",
            "agent": "logic_specialist",
        },
        "risk_audit_task": {
            "description": "Audit the proposed architecture considering {risk_profile} and {vulnerabilities}.\nConsider flaws: {iso_5055_flaws}",
            "expected_output": "Strategic consulting conclusion (Risk/ROI) and compliance report.",
            "agent": "risk_auditor",
        },
    }

    def __init__(
        self,
        llm_provider: str,
        llm_key: str,
        llm_model: Optional[str] = None,
        enable_per_agent_models: bool = True,
        mcp_client: Any = None,
        loop: Any = None,
        step_callback: Any = None,
    ):
        self.mcp_client = mcp_client
        self.loop = loop
        self.step_callback = step_callback
        self.llm_provider = llm_provider
        self.llm_key = llm_key
        self._llm_cache: Dict[str, Any] = {}
        self.model_overrides: Dict[str, str] = {}
        if self.llm_provider == "openrouter" and enable_per_agent_models:
            self.model_overrides = dict(self._OPENROUTER_INTERNAL_MODELS)
        
        try:
            if llm_provider == "openrouter":
                self.default_model = llm_model or os.getenv("OPENROUTER_MODEL") or self.model_overrides.get("default") or "openai/gpt-4o"
                self.llm = self._openrouter_llm(self.default_model)
            elif llm_provider == "openai":
                self.default_model = llm_model or "gpt-4o"
                self.llm = ChatOpenAI(model=self.default_model, api_key=llm_key)
            elif llm_provider == "gemini":
                try:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                except Exception as e:
                    raise RuntimeError("Missing dependency: langchain-google-genai") from e
                self.default_model = llm_model or "gemini-1.5-pro"
                self.llm = ChatGoogleGenerativeAI(model=self.default_model, google_api_key=llm_key)
            elif llm_provider == "azure":
                self.default_model = llm_model or "gpt-4o"
                self.llm = ChatOpenAI(model=self.default_model, api_key=llm_key)
            else:
                self.default_model = llm_model or self.model_overrides.get("default") or os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o"
                self.llm = self._openrouter_llm(self.default_model)
        except Exception as e:
            logger.warning(f"Error configuring LLM: {e}")
            self.llm = None

        if self.llm_provider == "openrouter":
            manager_model = (
                self.model_overrides.get("manager")
                or self.model_overrides.get("transformation_manager")
                or self.default_model
            )
            self.manager_llm = self._openrouter_llm(manager_model)
        else:
            self.manager_llm = self.llm

    def _openrouter_llm(self, model: str):
        key = f"openrouter::{model}"
        if key in self._llm_cache:
            return self._llm_cache[key]
        llm = ChatOpenAI(model=model, api_key=self.llm_key, base_url="https://openrouter.ai/api/v1")
        self._llm_cache[key] = llm
        return llm

    def _agent_llm(self, agent_key: str):
        if self.llm_provider != "openrouter" or not self.llm:
            return self.llm
        model = self.model_overrides.get(agent_key) or self.model_overrides.get("default") or self.default_model
        return self._openrouter_llm(model)

    def _get_tool(self, name: str, desc: str):
        if not self.mcp_client or not self.loop:
            return None
        return create_mcp_tool(name, desc, self.mcp_client, self.loop)

    def portfolio_specialist(self) -> Agent:
        tool = self._get_tool("applications", "List all available applications available in CAST Imaging.")
        return Agent(
            role=self._AGENTS["portfolio_specialist"]["role"],
            goal=self._AGENTS["portfolio_specialist"]["goal"],
            backstory=self._AGENTS["portfolio_specialist"]["backstory"],
            llm=self._agent_llm("portfolio_specialist"),
            tools=[tool] if tool else [],
            verbose=True,
            allow_delegation=False,
        )

    def system_profile_analyst(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("stats", "Get basic statistics for an application including size, complexity, and technology metrics."))
            tools.append(self._get_tool("architectural_graph", "Visualize application architecture (nodes/links) at layer/component level."))
        return Agent(
            role=self._AGENTS["system_profile_analyst"]["role"],
            goal=self._AGENTS["system_profile_analyst"]["goal"],
            backstory=self._AGENTS["system_profile_analyst"]["backstory"],
            llm=self._agent_llm("system_profile_analyst"),
            tools=tools,
            verbose=True,
            allow_delegation=False,
        )

    def transformation_manager(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("advisors", "Get migration/modernization advisors, rules, and violations for an application."))
            tools.append(self._get_tool("architectural_graph_focus", "Get architecture focused on specific components for exploring architecture around key areas."))
        return Agent(
            role=self._AGENTS["transformation_manager"]["role"],
            goal=self._AGENTS["transformation_manager"]["goal"],
            backstory=self._AGENTS["transformation_manager"]["backstory"],
            llm=self._agent_llm("transformation_manager"),
            tools=tools,
            verbose=True,
            allow_delegation=True,
        )

    def data_architect(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("application_database_explorer", "Explore database tables and columns in an application."))
            tools.append(self._get_tool("data_graphs", "Fetch data call graph views for an application."))
            tools.append(self._get_tool("data_graphs_involving_object", "Find all data call graphs involving specific objects to trace data dependencies."))
        return Agent(
            role=self._AGENTS["data_architect"]["role"],
            goal=self._AGENTS["data_architect"]["goal"],
            backstory=self._AGENTS["data_architect"]["backstory"],
            llm=self._agent_llm("data_architect"),
            tools=tools,
            verbose=True,
            allow_delegation=False,
        )

    def logic_specialist(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("transactions", "Fetch transactions for an application with optional filtering capabilities by name or type."))
            tools.append(self._get_tool("transaction_details", "Get comprehensive details about specific transactions including complexity, nodes, and links."))
            tools.append(self._get_tool("transactions_using_object", "Identify all transactions that use a specific object."))
        return Agent(
            role=self._AGENTS["logic_specialist"]["role"],
            goal=self._AGENTS["logic_specialist"]["goal"],
            backstory=self._AGENTS["logic_specialist"]["backstory"],
            llm=self._agent_llm("logic_specialist"),
            tools=tools,
            verbose=True,
            allow_delegation=False,
        )

    def risk_auditor(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("application_iso_5055_explorer", "Explore ISO 5055 software quality characteristics and their associated weaknesses."))
            tools.append(self._get_tool("quality_insights", "Retrieve quality issues including CVE, cloud patterns, green patterns, structural flaws, and ISO-5055 violations."))
            tools.append(self._get_tool("quality_insight_violations", "Get detailed information about the occurrences for a particular quality-related insight type."))
        return Agent(
            role=self._AGENTS["risk_auditor"]["role"],
            goal=self._AGENTS["risk_auditor"]["goal"],
            backstory=self._AGENTS["risk_auditor"]["backstory"],
            llm=self._agent_llm("risk_auditor"),
            tools=tools,
            verbose=True,
            allow_delegation=False,
        )

    def _task(self, task_key: str, agent: Agent) -> Task:
        t = self._TASKS[task_key]
        return Task(
            description=t["description"],
            expected_output=t["expected_output"],
            agent=agent,
        )

    def crew(self) -> Crew:
        agents = [
            self.transformation_manager(),
            self.data_architect(),
            self.logic_specialist(),
            self.risk_auditor(),
        ]
        tasks = [
            self._task("orchestration_task", agents[0]),
            self._task("data_architecture_task", agents[1]),
            self._task("logic_transformation_task", agents[2]),
            self._task("risk_audit_task", agents[3]),
        ]

        base_kwargs: Dict[str, Any] = {"agents": agents, "tasks": tasks, "verbose": True}

        # Best-effort hierarchical process + manager_llm + step_callback, but stay compatible with older CrewAI.
        try:
            from crewai import Process  # type: ignore
            base_kwargs["process"] = getattr(Process, "hierarchical", getattr(Process, "sequential", None))
        except Exception:
            pass

        if self.manager_llm is not None:
            base_kwargs["manager_llm"] = self.manager_llm

        if self.step_callback is not None:
            base_kwargs["step_callback"] = self.step_callback

        try:
            return Crew(**base_kwargs)
        except TypeError:
            base_kwargs.pop("step_callback", None)
            base_kwargs.pop("manager_llm", None)
            base_kwargs.pop("process", None)
            return Crew(**base_kwargs)
