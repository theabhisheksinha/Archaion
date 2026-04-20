import json
import asyncio
import uuid
import logging
from typing import Any, Type, Optional, Dict, Literal, List
from pydantic import BaseModel, Field, ConfigDict
try:
    from crewai.tools import BaseTool
except Exception:
    from crewai.tools.tool_usage import BaseTool

try:
    from app.backend.redis_manager import redis_client
except ImportError:
    redis_client = None

logger = logging.getLogger("archaion.mcp_tools")

def _clean_mcp_payload(payload: Any) -> Any:
    """Recursively cleans the MCP payload by removing excessive newline chars and structural bloat."""
    if isinstance(payload, str):
        # Attempt to parse embedded JSON strings
        try:
            parsed = json.loads(payload)
            return _clean_mcp_payload(parsed)
        except Exception:
            return payload.replace("\\n", " ").replace("\n", " ").strip()
    elif isinstance(payload, dict):
        # Flatten "structuredContent" if present
        if "structuredContent" in payload and isinstance(payload["structuredContent"], dict):
            content = payload["structuredContent"].get("content", {})
            return _clean_mcp_payload(content)
        # Flatten single "content" lists or dicts
        if "content" in payload:
            content = payload["content"]
            if isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict) and "text" in content[0]:
                try:
                    return _clean_mcp_payload(json.loads(content[0]["text"]))
                except Exception:
                    return _clean_mcp_payload(content[0]["text"])
            return _clean_mcp_payload(content)
        
        return {k: _clean_mcp_payload(v) for k, v in payload.items()}
    elif isinstance(payload, list):
        return [_clean_mcp_payload(item) for item in payload]
    return payload

def _generate_summary(tool_name: str, payload: Any, execution_id: str, call_id: str) -> str:
    """Generates a concise, token-efficient summary for the agent."""
    if not isinstance(payload, dict):
        if isinstance(payload, list):
            return f"Success: Fetched {len(payload)} items from {tool_name}. Full data saved to Redis under key 'execution:{execution_id}:data:{tool_name}:{call_id}'."
        return f"Success: Executed {tool_name}. Full data saved to Redis under key 'execution:{execution_id}:data:{tool_name}:{call_id}'."

    # Look for lists of items to summarize
    item_count = 0
    for key in ["items", "nodes", "links", "tables", "transactions", "results", "data", "insights", "violations", "occurrences"]:
        if key in payload and isinstance(payload[key], list):
            item_count = len(payload[key])
            break
            
    summary = f"Success: Executed {tool_name}."
    if item_count > 0:
        summary += f" Found {item_count} items."
    
    summary += f" Full structured data is safely stored in Redis under key 'execution:{execution_id}:data:{tool_name}:{call_id}'. DO NOT hallucinate details; trust that the final report generator will pull the full details from Redis."
    
    # If the payload is extremely small, we can just return it.
    if len(json.dumps(payload)) < 500:
        summary += f" Preview: {json.dumps(payload)}"
        
    return summary

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
    advisor_id: str = Field(description="ID of the advisor occurrence (sometimes called just 'id')")
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
    application: Optional[str] = Field(default=None, description="Application name (optional, will be auto-filled if missing)")
    filters: Optional[str] = Field(default=None, description="Filter transactions")
    page: Optional[int] = Field(default=1, description="Page number for paginated results (default: 1)")

class ApplicationsDataGraphsInput(BaseModel):
    application: Optional[str] = Field(default=None, description="Application name (optional, will be auto-filled if missing)")
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
    execution_id: Optional[str] = Field(default=None, exclude=True)

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
                "applications_transactions",
                "applications_data_graphs",
            }
            if self.name not in no_app_tools:
                payload["application"] = self.default_application

        # Handle specific parameter name mismatches for advisor_occurrences
        if self.name == "advisor_occurrences":
            if "advisor_id" in payload and "id" not in payload:
                payload["id"] = payload.pop("advisor_id")
            elif "id" in payload and "advisor_id" not in payload:
                pass # Already has id
                
        # Handle transaction_details expecting a single string but receiving a list
        if self.name == "transaction_details" and "id" in payload:
            if isinstance(payload["id"], list) and len(payload["id"]) > 0:
                # Log a warning and just take the first ID, as the tool only supports one string
                logger.warning(f"transaction_details expected string for 'id', got list. Using first element: {payload['id'][0]}")
                payload["id"] = str(payload["id"][0])

        try:
            # Execute the async method synchronously using the provided event loop
            future = asyncio.run_coroutine_threadsafe(
                self.mcp_client.invoke_tool(self.name, payload), 
                self.loop
            )
            res = future.result(timeout=30)
            
            # If execution_id is provided, clean and store it in Redis
            if self.execution_id and redis_client:
                call_id = str(uuid.uuid4())[:8]
                try:
                    cleaned_res = _clean_mcp_payload(res)
                    # Use threadsafe coroutine to store the output asynchronously
                    asyncio.run_coroutine_threadsafe(
                        redis_client.store_tool_output(self.execution_id, self.name, call_id, cleaned_res),
                        self.loop
                    )
                    return _generate_summary(self.name, cleaned_res, self.execution_id, call_id)
                except Exception as clean_err:
                    logger.warning(f"Error cleaning/storing MCP payload: {clean_err}")
                    return json.dumps(res, indent=2)

            return json.dumps(res, indent=2)
        except Exception as e:
            logger.error(f"Error executing MCP tool {self.name}: {e}")
            return f"Error executing tool {self.name}: {str(e)}"

    async def _arun(self, tool_args: Optional[Any] = None, **kwargs: Any) -> str:
        return self._run(tool_args=tool_args, **kwargs)

class FetchRedisDataInput(BaseModel):
    execution_id: str = Field(description="The execution ID for the current run.")
    tool_name: Optional[str] = Field(default=None, description="Optional: specific tool name to fetch data for (e.g., 'architectural_graph'). If omitted, fetches all data.")

class FetchRedisDataTool(BaseTool):
    name: str = "fetch_redis_data"
    description: str = "Fetches the full structured data stored in Redis by earlier MCP tool executions. Use this before writing the final synthesis report to get the exact data."
    args_schema: Type[BaseModel] = FetchRedisDataInput
    
    loop: Any = Field(exclude=True)

    def _run(self, execution_id: str, tool_name: Optional[str] = None, **kwargs: Any) -> str:
        if not redis_client:
            return "Redis client is not available."
        try:
            if tool_name:
                # Fetch specific tool's data
                future = asyncio.run_coroutine_threadsafe(
                    redis_client.get_all_execution_data(execution_id), 
                    self.loop
                )
                all_data = future.result(timeout=30)
                return json.dumps({tool_name: all_data.get(tool_name, [])}, indent=2)
            else:
                # Fetch all
                future = asyncio.run_coroutine_threadsafe(
                    redis_client.get_all_execution_data(execution_id), 
                    self.loop
                )
                all_data = future.result(timeout=30)
                return json.dumps(all_data, indent=2)
        except Exception as e:
            return f"Error fetching Redis data: {str(e)}"

def create_mcp_tool(
    tool_name: str,
    tool_description: str,
    mcp_client: Any,
    loop: Any,
    default_application: Optional[str] = None,
    execution_id: Optional[str] = None,
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
        execution_id=execution_id,
    )
