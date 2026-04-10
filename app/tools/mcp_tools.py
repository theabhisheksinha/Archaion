import json
import asyncio
from typing import Any, Type, Optional, Dict, Literal
from pydantic import BaseModel, Field, ConfigDict
try:
    from crewai.tools import BaseTool
except Exception:
    from crewai.tools.tool_usage import BaseTool
import logging

logger = logging.getLogger("archaion.mcp_tools")

class MCPToolInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    tool_args: Optional[str] = Field(
        default="{}",
        description="JSON string representing the arguments for the MCP tool. Defaults to '{}' when omitted.",
    )

class QualityInsightViolationsInput(BaseModel):
    application: str = Field(description="Application name (required)")
    nature: Literal["cloud-detection-patterns", "green-detection-patterns", "cve", "structural-flaws", "iso-5055"] = Field(description="Type of quality insights (required)")
    id: Optional[str] = Field(default=None, description="Optional ID to filter for a specific quality insight/detection pattern. Required when include_locations=True")
    include_locations: Optional[bool] = Field(default=False, description="If False, returns impacted objects. If True, returns detailed locations (default: False)")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class QualityInsightsInput(BaseModel):
    application: str = Field(description="Application name (required)")
    nature: Literal["cloud-detection-patterns", "green-detection-patterns", "cve", "structural-flaws", "iso-5055"] = Field(description="Type of quality insights (required)")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class ApplicationIso5055ExplorerInput(BaseModel):
    application: str = Field(description="Application name (required)")
    characteristic_id: Optional[str] = Field(default=None, description="Optional ID to get weaknesses for this specific characteristic ID")
    name_filter: Optional[str] = Field(default=None, description="Optional filter by name containing this value")
    limit: Optional[int] = Field(default=10, description="Default: 10, for weakness listing")
    skip: Optional[int] = Field(default=0, description="Default: 0, for pagination")

class AdvisorsInput(BaseModel):
    application: str = Field(description="Application name (required)")
    focus: Literal["list", "rules", "violations"] = Field(default="list", description="Focus operation (default: 'list')")
    advisor_id: Optional[str] = Field(default=None, description="Advisor ID (required for focus='rules' or focus='violations')")
    rule_id: Optional[str] = Field(default=None, description="Rule ID (required for focus='violations')")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class AdvisorOccurrencesInput(BaseModel):
    application: str = Field(description="Application name (required)")
    id: str = Field(description="ID of the advisor occurrence")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class ApplicationDatabaseExplorerInput(BaseModel):
    application: str = Field(description="Application name (required)")
    table_name: Optional[str] = Field(default=None, description="Optional specific table name")
    name_filter: Optional[str] = Field(default=None, description="Optional filter by name containing this value")
    limit: Optional[int] = Field(default=10, description="Default: 10, for table listing")
    skip: Optional[int] = Field(default=0, description="Default: 0, for pagination")

class TransactionsInput(BaseModel):
    application: str = Field(description="Application name (required)")
    filters: Optional[str] = Field(default=None, description="Filter transactions using query string format (e.g., 'name:contains:myapp')")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class TransactionDetailsInput(BaseModel):
    application: str = Field(description="Application name (required)")
    id: str = Field(description="ID of the transaction")
    focus: Literal["complexity","insights","nodes","links","graph","type_graph","complexity_graph","documents","summary","callers","callees"] = Field(default="type_graph", description="Focus type (default: 'type_graph')")
    focus_size: Optional[int] = Field(default=10, description="Focus size (default: 10)")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class ArchitecturalGraphInput(BaseModel):
    application: str = Field(description="Application name (required)")
    mode: Literal["nodes", "links"] = Field(description="Mode: 'nodes' or 'links'")
    level: Literal["layer", "component", "sub-component", "technology-category", "element-type"] = Field(description="Level to graph")
    layout: Optional[str] = Field(default="none", description="Layout type (e.g., 'none', 'spring')")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class ApplicationsTransactionsInput(BaseModel):
    application: str = Field(description="Application name (required)")
    filters: Optional[str] = Field(default=None, description="Filter transactions")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class ApplicationsDataGraphsInput(BaseModel):
    application: str = Field(description="Application name (required)")
    filters: Optional[str] = Field(default=None, description="Filter data graphs")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class PackagesInput(BaseModel):
    application: str = Field(description="Application name (required)")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class DataGraphsInput(BaseModel):
    application: str = Field(description="Application name (required)")
    filters: Optional[str] = Field(default=None, description="Filter data graphs using query string format (e.g., 'name:contains:myapp')")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class DataGraphDetailsInput(BaseModel):
    application: str = Field(description="Application name (required)")
    id: str = Field(description="ID of the data graph")
    focus: Literal["complexity","insights","objects","links","graph","type_graph","complexity_graph","documents"] = Field(default="type_graph", description="Focus type (default: 'type_graph')")
    focus_size: Optional[int] = Field(default=10, description="Focus size (default: 10)")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")


_SCHEMA_MAP = {
    "quality_insight_violations": QualityInsightViolationsInput,
    "quality_insights": QualityInsightsInput,
    "application_iso_5055_explorer": ApplicationIso5055ExplorerInput,
    "advisors": AdvisorsInput,
    "advisor_occurrences": AdvisorOccurrencesInput,
    "application_database_explorer": ApplicationDatabaseExplorerInput,
    "transactions": TransactionsInput,
    "transaction_details": TransactionDetailsInput,
    "architectural_graph": ArchitecturalGraphInput,
    "applications_transactions": ApplicationsTransactionsInput,
    "applications_data_graphs": ApplicationsDataGraphsInput,
    "packages": PackagesInput,
    "data_graphs": DataGraphsInput,
    "data_graph_details": DataGraphDetailsInput
}

class MCPToolWrapper(BaseTool):
    name: str = "mcp_tool"
    description: str = "A generic wrapper for CAST MCP tools"
    args_schema: Type[BaseModel] = MCPToolInput
    
    # We pass the async mcp client and event loop to run it
    mcp_client: Any = Field(exclude=True)
    loop: Any = Field(exclude=True)
    default_application: Optional[str] = Field(default=None, exclude=True)

    def _run(self, tool_args: Optional[Any] = None, **kwargs: Any) -> str:
        try:
            # Parse the incoming JSON args
            if tool_args is None and kwargs:
                payload = kwargs
            elif tool_args is None:
                payload = {}
            elif isinstance(tool_args, dict):
                payload = tool_args
            else:
                payload = json.loads(tool_args)
        except Exception:
            payload = {}

        if isinstance(payload, dict) and kwargs:
            payload = {**payload, **kwargs}

        if isinstance(payload, dict) and self.default_application and "application" not in payload:
            no_app_tools = {
                "applications",
                "applications_dependencies",
                "applications_quality_insights",
                "inter_app_detailed_dependencies",
                "inter_applications_dependencies",
            }
            if self.name not in no_app_tools:
                payload["application"] = self.default_application

        try:
            # Execute the async method synchronously using the provided event loop
            future = asyncio.run_coroutine_threadsafe(
                self.mcp_client.invoke_tool(self.name, payload), 
                self.loop
            )
            res = future.result(timeout=30)
            return json.dumps(res, indent=2)
        except Exception as e:
            logger.error(f"Error executing MCP tool {self.name}: {e}")
            return f"Error executing tool {self.name}: {str(e)}"

    async def _arun(self, tool_args: Optional[Any] = None, **kwargs: Any) -> str:
        return self._run(tool_args=tool_args, **kwargs)

def create_mcp_tool(
    tool_name: str,
    tool_description: str,
    mcp_client: Any,
    loop: Any,
    default_application: Optional[str] = None,
) -> MCPToolWrapper:
    """Factory to create a CrewAI BaseTool wrapper for a specific MCP tool."""
    schema = _SCHEMA_MAP.get(tool_name, MCPToolInput)
    return MCPToolWrapper(
        name=tool_name,
        description=tool_description,
        args_schema=schema,
        mcp_client=mcp_client,
        loop=loop,
        default_application=default_application,
    )
