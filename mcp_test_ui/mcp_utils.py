import asyncio
import json
import logging
import sys
from typing import List, Any, Dict, Optional

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

# Assuming models.py and config.py are in the same directory (mcp_test_ui)
from . import config
from .models import MCPTool, MCPToolParameter

logger = logging.getLogger("mcp_utils")

async def get_mcp_tools(server_path_override: Optional[str] = None) -> List[MCPTool]:
    """Get all MCP tools from the server. Uses cache if server_path_override is None."""
    current_server_path = server_path_override if server_path_override else config.mcp_server_path

    if not current_server_path:
        logger.warning("MCP server path not set (and no override provided). Cannot fetch tools.")
        return []

    # Only use cache if no override is provided
    if not server_path_override and config.cached_tools:
        if all(isinstance(t, MCPTool) for t in config.cached_tools):
            return config.cached_tools  # type: ignore
        else:
            logger.warning("Cached tools are not of type MCPTool or cache is invalid. Refetching.")
            config.cached_tools.clear()

    try:
        actual_server_path = server_path_override if server_path_override else current_server_path
        # Use the Python interpreter from the currently active virtual environment
        python_executable = sys.executable
        
        # Initialize the transport with the script path and the python command
        custom_transport = PythonStdioTransport(
            script_path=actual_server_path,
            python_cmd=python_executable
            # args=[] # Add this if your server.py script needs arguments
        )
        
        async with Client(transport=custom_transport) as client:
            raw_tools = await client.list_tools()
            
            tools = []
            for tool_spec in raw_tools:
                params = []
                if hasattr(tool_spec, "inputSchema") and tool_spec.inputSchema:
                    input_schema = tool_spec.inputSchema
                    properties: Dict[str, Any] = {}
                    required_params: List[str] = []
                    
                    if isinstance(input_schema, dict):
                        properties = input_schema.get("properties", {})
                        required_params = input_schema.get("required", [])
                    elif hasattr(input_schema, "properties") and isinstance(input_schema.properties, dict):
                        properties = input_schema.properties
                        if hasattr(input_schema, "required") and isinstance(input_schema.required, list):
                            required_params = input_schema.required

                    for param_name, param_schema_data in properties.items():
                        if param_name.startswith("__") and param_name.endswith("__"):
                            continue
                        
                        param_type = "string"
                        param_description = ""
                        param_title = param_name
                        param_required = param_name in required_params
                        param_default = None
                        
                        if isinstance(param_schema_data, dict):
                            param_type = param_schema_data.get("type", "string")
                            param_description = param_schema_data.get("description", "")
                            param_title = param_schema_data.get("title", param_name)
                            param_default = param_schema_data.get("default", None)
                        elif hasattr(param_schema_data, "type"): # For Pydantic-like schema objects
                            param_type = getattr(param_schema_data, "type", "string")
                            param_description = getattr(param_schema_data, "description", "")
                            param_title = getattr(param_schema_data, "title", param_name)
                            param_default = getattr(param_schema_data, "default", None)
                        
                        params.append(
                            MCPToolParameter(
                                name=param_name,
                                type=param_type,
                                description=param_description or param_title,
                                required=param_required,
                                default=param_default,
                            )
                        )
                
                tools.append(
                    MCPTool(
                        name=tool_spec.name,
                        description=tool_spec.description if hasattr(tool_spec, "description") else "",
                        parameters=params,
                    )
                )
            
            # Only update cache if no override was provided
            if not server_path_override:
                config.cached_tools = tools
            return tools
    except Exception as e:
        logger.error(f"Error getting MCP tools from {current_server_path}: {e}", exc_info=True)
        return []


def clear_mcp_tool_cache():
    """Clears the cached MCP tools."""
    config.cached_tools.clear()
    logger.info("MCP tool cache cleared.")

