import asyncio
import json
import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastmcp import Client # For execute_tool

from . import config
from .mcp_utils import get_mcp_tools, clear_mcp_tool_cache
from .models import MCPToolParameter, CustomJSONEncoder # MCPToolParameter used by execute_tool's logic

logger = logging.getLogger("mcp_routes")
router = APIRouter()

_templates: Optional[Jinja2Templates] = None

def init_router_dependencies(templates_obj: Jinja2Templates):
    """Initializes dependencies for this router, e.g., templates."""
    global _templates
    _templates = templates_obj

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page with all available MCP tools."""
    if not _templates:
        logger.error("Templates not initialized for MCP routes")
        raise HTTPException(status_code=500, detail="Internal server error: Templates not configured")
    
    tools = await get_mcp_tools()
    return _templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tools": tools,
            "mcp_server_path": config.mcp_server_path,
            "current_page": "home"
        },
    )

@router.post("/execute/{tool_name}")
async def execute_tool(request: Request, tool_name: str):
    """Execute an MCP tool with the provided parameters."""
    if not config.mcp_server_path:
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
    
    form_data = await request.form()
    params: Dict[str, Any] = {}

    # Find the MCPToolParameter definition to use its parse_value method
    # This assumes tool.parameters contains instances of models.MCPToolParameter
    for param_def in tool.parameters:
        if param_def.name in form_data:
            value = form_data[param_def.name]
            # MCPToolParameter.parse_value is not directly used here based on original app.py logic
            # The original logic re-parses based on type, let's stick to that for now
            # to maintain behavior, but this could be refactored to use param_def.parse_value()
            if not value and not param_def.required:
                continue
            try:
                if param_def.type in ["array", "list"]:
                    try:
                        if value.strip().startswith("["):
                            params[param_def.name] = json.loads(value)
                        else:
                            params[param_def.name] = [v.strip() for v in value.split(",") if v.strip()]
                    except json.JSONDecodeError:
                        params[param_def.name] = [v.strip() for v in value.split(",") if v.strip()]
                elif param_def.type in ["object", "dict"]:
                    params[param_def.name] = json.loads(value)
                elif param_def.type in ["boolean", "bool"]:
                    params[param_def.name] = value.lower() in ["true", "on", "yes", "1"]
                else: # string, number, int, float etc.
                    # Attempt to parse to specific types if they are numbers, otherwise keep as string
                    # This logic is from the original app.py's execute_tool
                    if param_def.type in ["integer", "int"]:
                        params[param_def.name] = int(value)
                    elif param_def.type in ["number", "float"]:
                        params[param_def.name] = float(value)
                    else:
                         params[param_def.name] = value # Default to string
            except Exception as e:
                logger.error(f"Error parsing parameter {param_def.name}: {e}")
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Invalid value for parameter '{param_def.name}': {str(e)}"},
                )
    
    logger.info(f"Executing tool '{tool_name}' with parameters: {params}")
    
    start_time = asyncio.get_event_loop().time()
    try:
        converted_params = {}
        for param_name, param_value in params.items():
            string_field_names = ['category_id', 'offer_id', 'sku', 'listing_id', 'merchant_location_key', 'query']
            if param_name in string_field_names:
                converted_params[param_name] = str(param_value) if param_value is not None else param_value
            elif isinstance(param_value, str):
                if param_value.isdigit() and not any(id_name in param_name.lower() for id_name in ['id', 'sku', 'key']):
                    converted_params[param_name] = int(param_value)
                elif param_value.replace('.', '', 1).isdigit() and param_value.count('.') <= 1:
                    if 'price' in param_name.lower() or 'quantity' in param_name.lower() or 'amount' in param_name.lower():
                        converted_params[param_name] = float(param_value)
                    else:
                        converted_params[param_name] = param_value
                else:
                    converted_params[param_name] = param_value
            else:
                converted_params[param_name] = param_value
        
        logger.info(f"Executing {tool_name} with converted parameters: {converted_params}")
        
        async with Client(config.mcp_server_path) as mcp_client:
            if hasattr(mcp_client, "call_tool"):
                result = await mcp_client.call_tool(tool_name, arguments=converted_params)
            elif hasattr(mcp_client, "call_tool_mcp"): # Fallback, if applicable
                result = await mcp_client.call_tool_mcp(tool_name, arguments=converted_params)
            else:
                raise AttributeError(f"Client has no method to invoke tools. Available methods: {dir(mcp_client)}")
            
        elapsed_time = round(asyncio.get_event_loop().time() - start_time, 2)
        
        formatted_result = []
        try:
            if isinstance(result, str):
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
                formatted_result.append({"type": "text", "content": str(result)})
        except TypeError as e:
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

@router.post("/set_server_path")
async def set_server_path(request: Request, server_path: str = Form(...)):
    """Set the MCP server path."""
    if not server_path:
        return JSONResponse(
            status_code=400,
            content={"error": "Server path not provided"},
        )
    
    config.mcp_server_path = server_path
    clear_mcp_tool_cache() # Clear cache when server path changes
    
    logger.info(f"MCP server path set to: {config.mcp_server_path}")
    
    try:
        tools = await get_mcp_tools() # Attempt to fetch tools to validate
        if not tools and config.mcp_server_path:
             logger.warning(f"MCP server path set to {config.mcp_server_path}, but no tools were found. Check server and path.")
             return JSONResponse(
                content={
                    "message": f"MCP server path set to '{config.mcp_server_path}'. No tools found, please verify the server is running and the path is correct.",
                    "path_set": True,
                    "tools_found": False
                }
            )
        return JSONResponse(
            content={
                "message": f"MCP server path set to '{config.mcp_server_path}'. Found {len(tools)} tools.",
                "path_set": True,
                "tools_found": len(tools) > 0
            }
        )
    except Exception as e:
        logger.error(f"Error validating MCP server path {config.mcp_server_path}: {e}")
        config.mcp_server_path = None # Reset if validation fails
        clear_mcp_tool_cache()
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to connect or fetch tools from '{server_path}': {str(e)}"},
        )

