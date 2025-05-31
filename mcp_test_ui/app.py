import asyncio
import inspect
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, create_model

# Add parent directory to path to import FastMCP
sys.path.append(str(Path(__file__).parent.parent))

from fastmcp import Client, FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp_test_ui")

app = FastAPI(
    title="MCP Test UI",
    description="A web UI for testing FastMCP tools",
    version="0.1.0",
)

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)

# Set up templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Global variables
mcp_server_path = None
cached_tools = []


class Parameter(BaseModel):
    """Model for a tool parameter."""
    name: str
    type: str
    description: str = ""
    required: bool = False

    def get_html_input_type(self) -> str:
        """Get the HTML input type based on the parameter type."""
        type_mapping = {
            "integer": "number",
            "int": "number",
            "number": "number",
            "float": "number",
            "string": "text",
            "str": "text",
            "boolean": "checkbox",
            "bool": "checkbox",
            "date": "date",
            "time": "time",
            "datetime": "datetime-local",
            "email": "email",
            "url": "url",
            "password": "password",
        }
        return type_mapping.get(self.type.lower(), "text")


class MCPToolParameter:
    """Represents a parameter for an MCP tool."""

    def __init__(
        self,
        name: str,
        type_: str,
        description: str = "",
        required: bool = True,
        default: Any = None,
    ):
        self.name = name
        self.type = type_
        self.description = description
        self.required = required
        self.default = default
        
    def get_html_input_type(self) -> str:
        """Get the HTML input type for this parameter type."""
        if self.type in ["string", "str"]:
            return "text"
        elif self.type in ["integer", "int"]:
            return "number"
        elif self.type in ["number", "float"]:
            return "number" 
        elif self.type in ["boolean", "bool"]:
            return "checkbox"
        elif self.type in ["array", "list"]:
            return "textarea"
        elif self.type in ["object", "dict"]:
            return "textarea"
        return "text"
    
    def parse_value(self, value: str) -> Any:
        """Parse a string value to the appropriate type."""
        if not value and not self.required:
            return self.default
        
        if self.type in ["string", "str"]:
            return value
        elif self.type in ["integer", "int"]:
            return int(value) if value else None
        elif self.type in ["number", "float"]:
            return float(value) if value else None
        elif self.type in ["boolean", "bool"]:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ["true", "1", "yes", "y", "on"]
            return bool(value)
        elif self.type in ["array", "list"]:
            try:
                if not value:
                    return []
                # Handle both JSON array and comma-separated values
                if value.startswith("[") and value.endswith("]"):
                    return json.loads(value)
                return [item.strip() for item in value.split(",")]
            except:
                logger.warning(f"Failed to parse array value: {value}")
                return []
        elif self.type in ["object", "dict"]:
            try:
                return json.loads(value) if value else {}
            except:
                logger.warning(f"Failed to parse object value: {value}")
                return {}
        return value


class MCPTool:
    """Represents an MCP tool with its parameters and metadata."""

    def __init__(self, name: str, description: str, parameters: List[MCPToolParameter]):
        self.name = name
        self.description = description
        self.parameters = parameters


async def get_mcp_tools() -> List[MCPTool]:
    """Get all MCP tools from the server."""
    global cached_tools
    
    if cached_tools:
        return cached_tools
    
    if not mcp_server_path:
        return []
    
    try:
        client = Client(mcp_server_path)
        async with client:
            raw_tools = await client.list_tools()
            
            tools = []
            for tool in raw_tools:
                params = []
                
                # Debug logging for investigating tool parameters
                logger.info(f"Tool: {tool.name}")
                logger.info(f"Has inputSchema: {hasattr(tool, 'inputSchema')}")
                
                if hasattr(tool, "inputSchema") and tool.inputSchema:
                    logger.info(f"inputSchema: {tool.inputSchema}")
                    logger.info(f"inputSchema type: {type(tool.inputSchema)}")
                    logger.info(f"inputSchema dir: {dir(tool.inputSchema)}")
                    logger.info(f"inputSchema dict: {tool.inputSchema.__dict__ if hasattr(tool.inputSchema, '__dict__') else None}")
                    
                    # Check if it has properties
                    has_properties = hasattr(tool.inputSchema, "properties")
                    logger.info(f"Has properties: {has_properties}")
                    
                    if has_properties:
                        logger.info(f"Properties: {tool.inputSchema.properties}")
                        logger.info(f"Properties type: {type(tool.inputSchema.properties)}")
                        if isinstance(tool.inputSchema.properties, dict):
                            for param_name, param_schema in tool.inputSchema.properties.items():
                                logger.info(f"Param: {param_name}, Schema: {param_schema}")
                
                # Extract parameters from the inputSchema
                if hasattr(tool, "inputSchema") and tool.inputSchema:
                    input_schema = tool.inputSchema
                    properties = {}
                    required_params = []
                    
                    # Handle different ways inputSchema might be structured
                    if isinstance(input_schema, dict):
                        properties = input_schema.get("properties", {})
                        required_params = input_schema.get("required", [])
                    elif hasattr(input_schema, "properties"):
                        if isinstance(input_schema.properties, dict):
                            properties = input_schema.properties
                        elif hasattr(input_schema.properties, "__dict__"):
                            properties = input_schema.properties.__dict__
                        
                        if hasattr(input_schema, "required"):
                            required_params = input_schema.required
                    
                    logger.info(f"Extracted properties: {properties}")
                    logger.info(f"Required params: {required_params}")
                    
                    for param_name, param_schema in properties.items():
                        # Skip special attributes
                        if param_name.startswith("__") and param_name.endswith("__"):
                            continue
                            
                        logger.info(f"Processing parameter: {param_name}, schema: {param_schema}")
                        
                        # Extract parameter information based on schema structure
                        param_type = "string"
                        param_description = ""
                        param_title = param_name
                        param_required = param_name in required_params
                        param_default = None
                        
                        if isinstance(param_schema, dict):
                            param_type = param_schema.get("type", "string")
                            param_description = param_schema.get("description", "")
                            param_title = param_schema.get("title", param_name)
                            param_default = param_schema.get("default", None)
                        elif hasattr(param_schema, "type"):
                            param_type = getattr(param_schema, "type", "string")
                            param_description = getattr(param_schema, "description", "")
                            param_title = getattr(param_schema, "title", param_name)
                            param_default = getattr(param_schema, "default", None)
                        
                        logger.info(f"Adding parameter: {param_name}, type: {param_type}, desc: {param_description}")
                        
                        params.append(
                            MCPToolParameter(
                                name=param_name,
                                type_=param_type,
                                description=param_description or param_title,
                                required=param_required,
                                default=param_default,
                            )
                        )
                
                tools.append(
                    MCPTool(
                        name=tool.name,
                        description=tool.description if hasattr(tool, "description") else "",
                        parameters=params,
                    )
                )
            
            cached_tools = tools
            return tools
    except Exception as e:
        logger.error(f"Error getting MCP tools: {e}")
        return []


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page with all available MCP tools."""
    tools = await get_mcp_tools()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tools": tools,
            "mcp_server_path": mcp_server_path or "Not set",
        },
    )


# Tool page route removed as all tools are now displayed on the main page


@app.post("/execute/{tool_name}")
async def execute_tool(request: Request, tool_name: str):
    """Execute an MCP tool with the provided parameters."""
    if not mcp_server_path:
        return JSONResponse(
            status_code=400,
            content={"error": "MCP server path not set"},
        )
        
    tools = await get_mcp_tools()
    tool = next((t for t in tools if t.name == tool_name), None)
    
    if not tool:
        return JSONResponse(
            status_code=404,
            content={"error": f"Tool '{tool_name}' not found"},
        )
    
    # Get form data
    form_data = await request.form()
    
    # Parse parameters
    params = {}
    for param in tool.parameters:
        if param.name in form_data:
            value = form_data[param.name]
            if not value and not param.required:
                continue
                
            try:
                # Handle different parameter types
                if param.type in ["array", "list"]:
                    # Try to parse as JSON array first
                    try:
                        if value.strip().startswith("["):
                            params[param.name] = json.loads(value)
                        else:
                            # Fallback to comma-separated values
                            params[param.name] = [v.strip() for v in value.split(",") if v.strip()]
                    except json.JSONDecodeError:
                        # Fallback to comma-separated values
                        params[param.name] = [v.strip() for v in value.split(",") if v.strip()]
                elif param.type in ["object", "dict"]:
                    # Parse as JSON
                    params[param.name] = json.loads(value)
                elif param.type in ["boolean", "bool"]:
                    # Handle checkbox value
                    params[param.name] = value.lower() in ["true", "on", "yes", "1"]
                else:
                    # Use the standard parser for other types
                    params[param.name] = param.parse_value(value)
            except Exception as e:
                logger.error(f"Error parsing parameter {param.name}: {e}")
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Invalid value for parameter '{param.name}': {str(e)}"},
                )
    
    # Log the tool call
    logger.info(f"Executing tool '{tool_name}' with parameters: {params}")
    
    logger.info(f"Executing tool {tool_name} with params: {params}")
    
    # Execute the tool
    start_time = asyncio.get_event_loop().time()
    try:
        # Convert string parameters to appropriate types based on tool definition
        converted_params = {}
        for param_name, param_value in params.items():
            # Special handling for known ID fields and query parameters that should remain as strings
            string_field_names = ['category_id', 'offer_id', 'sku', 'listing_id', 'merchant_location_key', 'query']
            
            # Keep IDs and query parameters as strings even if they're numeric
            if param_name in string_field_names:
                converted_params[param_name] = str(param_value) if param_value is not None else param_value
            # Convert other parameters based on their apparent type
            elif isinstance(param_value, str):
                # Only convert string params that aren't IDs to numeric types if appropriate
                if param_value.isdigit() and not any(id_name in param_name.lower() for id_name in ['id', 'sku', 'key']):
                    converted_params[param_name] = int(param_value)
                elif param_value.replace('.', '', 1).isdigit() and param_value.count('.') <= 1:
                    # Only convert to float if it's explicitly a price or a known numeric field
                    if 'price' in param_name.lower() or 'quantity' in param_name.lower() or 'amount' in param_name.lower():
                        converted_params[param_name] = float(param_value)
                    else:
                        converted_params[param_name] = param_value
                else:
                    converted_params[param_name] = param_value
            else:
                converted_params[param_name] = param_value
        
        logger.info(f"Executing {tool_name} with converted parameters: {converted_params}")
        
        # Use the FastMCP Client within an async context manager
        async with Client(mcp_server_path) as mcp_client:
            # Log available methods
            logger.info(f"Client methods: {dir(mcp_client)}")
            
            # Looking at the error message, call_tool expects a dictionary in the 'arguments' parameter
            # So we should pass our parameters as the 'arguments' dictionary
            logger.info(f"Calling tool: {tool_name} with parameters as dictionary")
            
            if hasattr(mcp_client, "call_tool"):
                # Pass the parameters as a dictionary to the arguments parameter
                result = await mcp_client.call_tool(tool_name, arguments=converted_params)
            elif hasattr(mcp_client, "call_tool_mcp"):
                # Try alternative method
                result = await mcp_client.call_tool_mcp(tool_name, arguments=converted_params)
            else:
                raise AttributeError(f"Client has no method to invoke tools. Available methods: {dir(mcp_client)})")
            
            # Log the result
            logger.info(f"Tool execution completed. Result type: {type(result)}")
        
        elapsed_time = round(asyncio.get_event_loop().time() - start_time, 2)
        
        # Format result
        formatted_result = []
        
        # Define a custom JSON encoder to handle non-serializable types
        class CustomJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                # Handle TextContent or other custom types
                if hasattr(obj, '__str__'):
                    return str(obj)
                return super().default(obj)
                
        try:
            if isinstance(result, str):
                # Check if result is JSON string
                try:
                    if result.strip().startswith(("{" ,"[")):
                        json_result = json.loads(result)
                        formatted_result.append({"type": "text", "content": json.dumps(json_result, indent=2, cls=CustomJSONEncoder)})
                    else:
                        formatted_result.append({"type": "text", "content": result})
                except json.JSONDecodeError:
                    formatted_result.append({"type": "text", "content": result})
            elif isinstance(result, (dict, list)):
                formatted_result.append({"type": "text", "content": json.dumps(result, indent=2, cls=CustomJSONEncoder)})
            elif result is None:
                formatted_result.append({"type": "text", "content": "(No result)"})
            else:
                # Try to convert to string first
                formatted_result.append({"type": "text", "content": str(result)})
        except TypeError as e:
            # If we still can't serialize, log the error and return a simplified result
            logger.error(f"Error serializing result: {e}")
            formatted_result.append({"type": "text", "content": f"Result of type {type(result).__name__} (not JSON serializable): {str(result)}"})
        
        return {
            "success": True,
            "result": formatted_result,
            "elapsed_time": elapsed_time,
        }
    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error executing tool: {str(e)}"},
        )


@app.post("/set_server_path")
async def set_server_path(request: Request):
    """Set the MCP server path."""
    global mcp_server_path, cached_tools
    
    form_data = await request.form()
    path = form_data.get("server_path", "")
    
    if not path:
        return JSONResponse(
            content={"error": "Server path cannot be empty"},
            status_code=400,
        )
    
    # Validate the path
    if not os.path.exists(path):
        return JSONResponse(
            content={"error": f"File not found: {path}"},
            status_code=400,
        )
    
    # Try to connect to the server
    try:
        client = Client(path)
        async with client:
            # Just test the connection
            pass
        
        mcp_server_path = path
        cached_tools = []  # Clear cache to force refresh
        
        return {"success": True, "message": f"Server path set to {path}"}
    except Exception as e:
        logger.error(f"Error connecting to MCP server at {path}: {e}")
        return JSONResponse(
            content={"error": f"Failed to connect to MCP server: {e}"},
            status_code=500,
        )


def run_server(server_path: Optional[str] = None, host: str = "127.0.0.1", port: int = 8000):
    """Run the MCP Test UI server."""
    global mcp_server_path
    
    if server_path:
        mcp_server_path = server_path
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Test UI")
    parser.add_argument("--server", "-s", help="Path to the MCP server file")
    parser.add_argument("--host", "-H", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to")
    
    args = parser.parse_args()
    
    run_server(args.server, args.host, args.port)
