import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from crewai import Agent, Crew, Task
from langchain_openai import ChatOpenAI
import yaml

from app.tools.mcp_tools import create_mcp_tool, FetchRedisDataTool
from app.tools.searchapi_tool import SearchApiTool

logger = logging.getLogger("archaion.crew")

class ModernizationCrew:
    _OPENROUTER_INTERNAL_MODELS: Dict[str, str] = {
        "default": "openai/gpt-4o-mini",
        "manager": "openai/gpt-4o-mini",
        "portfolio_specialist": "openai/gpt-4o-mini",
        "system_profile_analyst": "openai/gpt-4o-mini",
        "transformation_manager": "openai/gpt-4o-mini",
        "data_architect": "openai/gpt-4o-mini",
        "logic_specialist": "openai/gpt-4o-mini",
        "risk_auditor": "openai/gpt-4o-mini",
    }
    _AGENTS: Dict[str, Dict[str, str]] = {}

    _TASKS: Dict[str, Dict[str, str]] = {}

    def __init__(
        self,
        llm_provider: str,
        llm_key: str,
        llm_model: Optional[str] = None,
        enable_per_agent_models: bool = True,
        app_name: Optional[str] = None,
        execution_id: Optional[str] = None,
        mcp_client: Any = None,
        loop: Any = None,
        step_callback: Any = None,
        search_api_key: Optional[str] = None,
    ):
        self.mcp_client = mcp_client
        self.loop = loop
        self.step_callback = step_callback
        self.llm_provider = llm_provider
        self.llm_key = llm_key
        self.app_name = app_name
        self.execution_id = execution_id
        self.search_api_key = search_api_key or os.getenv("SEARCHAPI_API_KEY", "")
        self._llm_cache: Dict[str, Any] = {}
        self.model_overrides: Dict[str, str] = {}
        if self.llm_provider == "openrouter" and enable_per_agent_models:
            self.model_overrides = dict(self._OPENROUTER_INTERNAL_MODELS)
        # Load YAML configs for agents and tasks
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agents", "config"))
            with open(os.path.join(base_dir, "agents.yaml"), "r", encoding="utf-8") as f:
                agents_yaml = yaml.safe_load(f) or {}
            with open(os.path.join(base_dir, "tasks.yaml"), "r", encoding="utf-8") as f:
                tasks_yaml = yaml.safe_load(f) or {}
            # Normalize keys to match code expectations
            self._AGENTS = {
                "transformation_manager": agents_yaml.get("modernization_manager", {}),
                "portfolio_specialist": agents_yaml.get("portfolio_specialist", {}),
                "system_profile_analyst": agents_yaml.get("profile_analyst", {}),
                "data_architect": agents_yaml.get("database_architect", {}),
                "logic_specialist": agents_yaml.get("legacy_transformation_specialist", {}),
                "architecture_analyst": agents_yaml.get("architecture_analyst", {}),
                "risk_compliance_expert": agents_yaml.get("risk_compliance_expert", {}),
                "modernization_advisor": agents_yaml.get("modernization_advisor", {}),
            }
            # Pass through tasks.yaml verbatim
            self._TASKS = tasks_yaml or {}
        except Exception as e:
            logger.warning(f"YAML load failed, falling back to built-ins: {e!r}")
        
        try:
            if llm_provider == "openrouter":
                self.default_model = llm_model or os.getenv("OPENROUTER_MODEL") or self.model_overrides.get("default") or "openai/gpt-4o"
                self.llm = self._openrouter_llm(self.default_model)
            elif llm_provider == "openai":
                self.default_model = llm_model or "gpt-4o"
                self.llm = ChatOpenAI(model=self.default_model, api_key=llm_key, temperature=0)
            elif llm_provider == "gemini":
                from langchain_community.chat_models import ChatLiteLLM
                self.default_model = llm_model or "gemini/gemini-1.5-pro"
                self.llm = ChatLiteLLM(
                    model=self.default_model,
                    custom_llm_provider="gemini",
                    model_kwargs={"api_key": llm_key},
                )
            elif llm_provider == "azure":
                self.default_model = llm_model or "gpt-4o"
                self.llm = ChatOpenAI(model=self.default_model, api_key=llm_key, temperature=0)
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
        llm = ChatOpenAI(model=model, api_key=self.llm_key, base_url="https://openrouter.ai/api/v1", temperature=0)
        self._llm_cache[key] = llm
        return llm

    def _agent_llm(self, agent_key: str):
        if self.llm_provider != "openrouter" or not self.llm:
            # Enforce temperature=0 for non-OpenRouter where we directly build ChatOpenAI above
            return self.llm
        model = self.model_overrides.get(agent_key) or self.model_overrides.get("default") or self.default_model
        llm = self._openrouter_llm(model)
        try:
            llm.temperature = 0
        except Exception:
            pass
        return llm

    def _get_tool(self, name: str, desc: str):
        if not self.mcp_client or not self.loop:
            return None
        return create_mcp_tool(
            name,
            desc,
            self.mcp_client,
            self.loop,
            default_application=self.app_name,
            execution_id=self.execution_id
        )

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
            max_iter=4,
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
            max_iter=6,
        )

    def transformation_manager(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("advisors", "Get migration/modernization advisors, rules, and violations for an application."))
            tools.append(self._get_tool("architectural_graph_focus", "Get architecture focused on specific components for exploring architecture around key areas."))
            tools.append(self._get_tool("architectural_graph", "Visualize application architecture (nodes/links) at layer/component level."))
            tools.append(self._get_tool("stats", "Get basic statistics for an application including size, complexity, and technology metrics."))
        
        # Add the Redis fetch tool so it can retrieve the full intermediate data
        if self.loop:
            tools.append(FetchRedisDataTool(loop=self.loop))

        # Attach Serper only to manager
        # Attach searchapi.io tool (returns warnings when key is missing; never errors)
        tools.append(SearchApiTool(api_key=self.search_api_key))
        return Agent(
            role=self._AGENTS["transformation_manager"]["role"],
            goal=self._AGENTS["transformation_manager"]["goal"],
            backstory=self._AGENTS["transformation_manager"]["backstory"],
            llm=self._agent_llm("transformation_manager"),
            tools=tools,
            verbose=True,
            allow_delegation=True,
            max_iter=8,
        )

    def data_architect(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("application_database_explorer", "Explore database tables and columns in an application."))
            tools.append(self._get_tool("data_graphs", "Fetch data call graph views for an application."))
            tools.append(self._get_tool("data_graph_details", "Get detailed information about a specific data call graph (focus: graph/nodes/links/insights)."))
            tools.append(self._get_tool("data_graphs_involving_object", "Find all data call graphs involving specific objects to trace data dependencies."))
        return Agent(
            role=self._AGENTS["data_architect"]["role"],
            goal=self._AGENTS["data_architect"]["goal"],
            backstory=self._AGENTS["data_architect"]["backstory"],
            llm=self._agent_llm("data_architect"),
            tools=tools,
            verbose=True,
            allow_delegation=False,
            max_iter=6,
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
            max_iter=6,
        )

    def architecture_analyst(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("architectural_graph", "Visualize application architecture (nodes/links) at layer/component level."))
            tools.append(self._get_tool("packages", "Get all packages/namespaces in an application."))
            tools.append(self._get_tool("data_graphs", "Get application data graphs for detailed data flow mapping."))
        return Agent(
            role=self._AGENTS["architecture_analyst"]["role"],
            goal=self._AGENTS["architecture_analyst"]["goal"],
            backstory=self._AGENTS["architecture_analyst"]["backstory"],
            llm=self._agent_llm("architecture_analyst"),
            tools=tools,
            verbose=True,
            allow_delegation=False,
            max_iter=8,
        )

    def risk_compliance_expert(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("packages", "Get third-party packages for the application."))
            tools.append(self._get_tool("quality_insights", "Retrieve quality issues including CVE, cloud patterns, green patterns, structural flaws, and ISO-5055 violations."))
            tools.append(self._get_tool("quality_insight_violations", "Get detailed information about occurrences with optional code locations."))
        return Agent(
            role=self._AGENTS["risk_compliance_expert"]["role"],
            goal=self._AGENTS["risk_compliance_expert"]["goal"],
            backstory=self._AGENTS["risk_compliance_expert"]["backstory"],
            llm=self._agent_llm("risk_compliance_expert"),
            tools=tools,
            verbose=True,
            allow_delegation=False,
            max_iter=6,
        )

    def modernization_advisor(self) -> Agent:
        tools = []
        if self.mcp_client:
            tools.append(self._get_tool("advisors", "Get migration/modernization advisors, rules, and violations for an application."))
            tools.append(self._get_tool("advisor_occurrences", "Get specific code occurrences of findings supporting selected advisor."))
        return Agent(
            role=self._AGENTS["modernization_advisor"]["role"],
            goal=self._AGENTS["modernization_advisor"]["goal"],
            backstory=self._AGENTS["modernization_advisor"]["backstory"],
            llm=self._agent_llm("modernization_advisor"),
            tools=tools,
            verbose=True,
            allow_delegation=False,
            max_iter=6,
        )

    def _task(self, task_key: str, agent: Agent, resolved_context: Optional[List[Task]] = None) -> Task:
        t = self._TASKS[task_key]
        kwargs: Dict[str, Any] = {
            "description": t["description"],
            "expected_output": t.get("expected_output", ""),
            "agent": agent,
        }
        # Support CrewAI's context attribute if available; must be Task instances, not strings
        if resolved_context:
            try:
                kwargs["context"] = resolved_context
            except Exception:
                pass
        try:
            return Task(**kwargs)
        except TypeError:
            kwargs.pop("context", None)
            return Task(**kwargs)

    def crew(self) -> Crew:
        # Build agents from current YAML mapping
        manager = self.transformation_manager()
        arch_analyst = self.architecture_analyst()
        db_arch = self.data_architect()
        logic_spec = self.logic_specialist()
        risk_expert = self.risk_compliance_expert()
        mod_advisor = self.modernization_advisor()
        
        agents = [manager, arch_analyst, db_arch, logic_spec, risk_expert, mod_advisor]
        
        # Prefer YAML task keys if present, else fallback to prior defaults
        task_order = []
        
        if "architecture_analysis_task" in self._TASKS:
            task_order = [
                "architecture_analysis_task", 
                "db_analysis_task", 
                "logic_mapping_task", 
                "risk_compliance_audit_task", 
                "advisory_suggestions_task", 
                "synthesis_report_task"
            ]
            task_agents = {
                "architecture_analysis_task": arch_analyst,
                "db_analysis_task": db_arch,
                "logic_mapping_task": logic_spec,
                "risk_compliance_audit_task": risk_expert,
                "advisory_suggestions_task": mod_advisor,
                "synthesis_report_task": manager,
            }
        else:
            task_order = ["data_architecture_task", "logic_transformation_task", "risk_audit_task", "orchestration_task"]
            task_agents = {
                "data_architecture_task": db_arch,
                "logic_transformation_task": logic_spec,
                "risk_audit_task": risk_expert,
                "orchestration_task": manager,
            }
        # Build tasks in two passes so context can reference previously-built Task instances
        tasks_map: Dict[str, Task] = {}
        deferred_with_context: List[str] = []
        for k in task_order:
            if k not in self._TASKS:
                continue
            tdef = self._TASKS[k]
            if "context" in tdef and isinstance(tdef["context"], list):
                deferred_with_context.append(k)
                continue
            tasks_map[k] = self._task(k, task_agents[k])

        # Now build tasks that require context by resolving keys to Task instances
        for k in deferred_with_context:
            ctx_keys = self._TASKS[k].get("context", [])
            resolved_ctx: List[Task] = []
            for ck in ctx_keys:
                if isinstance(ck, Task):
                    resolved_ctx.append(ck)
                elif isinstance(ck, str) and ck in tasks_map:
                    resolved_ctx.append(tasks_map[ck])
                else:
                    logger.warning(f"Context item '{ck}' for task '{k}' not found or invalid; skipping.")
            tasks_map[k] = self._task(k, task_agents[k], resolved_context=resolved_ctx)

        # Preserve declared order
        tasks = [tasks_map[k] for k in task_order if k in tasks_map]

        base_kwargs: Dict[str, Any] = {"agents": agents, "tasks": tasks, "verbose": True}

        # Force sequential process to ensure deterministic execution of tasks by their assigned agents.
        try:
            from crewai import Process  # type: ignore
            base_kwargs["process"] = Process.sequential
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
