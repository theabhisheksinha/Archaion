import json
import asyncio
from typing import Any, Type, Optional
from pydantic import BaseModel, Field
try:
    from crewai.tools import BaseTool
except Exception:
    from crewai.tools.tool_usage import BaseTool
import logging

logger = logging.getLogger("archaion.mcp_tools")

class MCPToolInput(BaseModel):
    tool_args: Optional[str] = Field(
        default="{}",
        description="JSON string representing the arguments for the MCP tool. Defaults to '{}' when omitted.",
    )

class MCPToolWrapper(BaseTool):
    name: str = "mcp_tool"
    description: str = "A generic wrapper for CAST MCP tools"
    args_schema: Type[BaseModel] = MCPToolInput
    
    # We pass the async mcp client and event loop to run it
    mcp_client: Any = Field(exclude=True)
    loop: Any = Field(exclude=True)

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

def create_mcp_tool(tool_name: str, tool_description: str, mcp_client: Any, loop: Any) -> MCPToolWrapper:
    """Factory to create a CrewAI BaseTool wrapper for a specific MCP tool."""
    return MCPToolWrapper(
        name=tool_name,
        description=tool_description,
        mcp_client=mcp_client,
        loop=loop
    )
