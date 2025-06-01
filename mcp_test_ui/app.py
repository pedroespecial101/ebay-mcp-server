import asyncio
import inspect
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Tuple, Union, AsyncGenerator
from dotenv import load_dotenv

import uvicorn
from fastapi import FastAPI, Form, Request, Query, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, create_model, Field
import httpx
from dotenv import load_dotenv, find_dotenv

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

# Load environment variables from .env file
load_dotenv()

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


class Message(BaseModel):
    """Model for a chat message."""
    role: str
    content: str


class ChatRequest(BaseModel):
    """Model for a chat request."""
    provider: str
    model: str
    messages: List[Message]
    stream: bool = True
    mcp_server: str
    api_key: str


class ToolCall(BaseModel):
    """Model for an MCP tool call."""
    name: str
    args: Dict[str, Any]


class ToolResult(BaseModel):
    """Model for an MCP tool result."""
    result: Any


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
            "mcp_server_path": mcp_server_path or "",
        }
    )


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Render the chat interface page."""
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "title": "LLM Chat",
            "mcp_server_path": mcp_server_path or "/Users/petetreadaway/Projects/ebay-mcp-server/src/server.py",
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


async def execute_mcp_tool(mcp_server: str, tool_name: str, args: Dict[str, Any]) -> Any:
    """Execute an MCP tool and return its result."""
    try:
        client = Client(mcp_server)
        async with client:
            result = await client.call_tool(tool_name, arguments=args)
            return result
    except Exception as e:
        logger.exception(f"Error executing MCP tool {tool_name}: {e}")
        return f"Error executing tool: {str(e)}"


@app.post("/chat")
async def chat(request: ChatRequest):
    """Handle a chat request."""
    try:
        # Try to load API key from environment if not provided and using OpenRouter
        if not request.api_key and request.provider == "openrouter":
            request.api_key = os.environ.get("OPENROUTER_API_KEY", "")
            
        if not request.api_key:
            return JSONResponse(
                status_code=400,
                content={"error": "API key is required"},
            )
            
        # Use the appropriate provider
        if request.provider == "openai":
            content, tool_calls = await call_openai(request)
        elif request.provider == "anthropic":
            content, tool_calls = await call_anthropic(request)
        elif request.provider == "gemini":
            content, tool_calls = await call_gemini(request)
        elif request.provider == "openrouter":
            content, tool_calls = await call_openrouter(request)
        else:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown provider: {request.provider}"},
            )
            
        return {
            "content": content,
            "tool_calls": tool_calls,
        }
        
    except Exception as e:
        logger.exception(f"Error in chat: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.get("/chat/stream")
async def chat_stream(data: str = Query(...)):
    """Stream a chat response."""
    try:
        # Parse the encoded request data
        request_data = json.loads(data)
        chat_request = ChatRequest(**request_data)
        
        # Try to load API key from environment if not provided and using OpenRouter
        if not chat_request.api_key and chat_request.provider == "openrouter":
            chat_request.api_key = os.environ.get("OPENROUTER_API_KEY", "")
            
        if not chat_request.api_key:
            return StreamingResponse(
                content=stream_error("API key is required"),
                media_type="text/event-stream"
            )
            
        # Use the appropriate provider with streaming
        if chat_request.provider == "openai":
            return StreamingResponse(
                content=stream_openai(chat_request),
                media_type="text/event-stream"
            )
        elif chat_request.provider == "anthropic":
            return StreamingResponse(
                content=stream_anthropic(chat_request),
                media_type="text/event-stream"
            )
        elif chat_request.provider == "gemini":
            return StreamingResponse(
                content=stream_gemini(chat_request),
                media_type="text/event-stream"
            )
        elif chat_request.provider == "openrouter":
            return StreamingResponse(
                content=stream_openrouter(chat_request),
                media_type="text/event-stream"
            )
        else:
            return StreamingResponse(
                content=stream_error(f"Unknown provider: {chat_request.provider}"),
                media_type="text/event-stream"
            )
            
    except Exception as e:
        logger.exception(f"Error in chat_stream: {e}")
        return StreamingResponse(
            content=stream_error(str(e)),
            media_type="text/event-stream"
        )


def run_server(server_path: Optional[str] = None, host: str = "127.0.0.1", port: int = 8000):
    """Run the MCP Test UI server."""
    global mcp_server_path
    
    if server_path:
        mcp_server_path = server_path
    
    uvicorn.run(app, host=host, port=port)


async def stream_error(error_message: str) -> AsyncGenerator[str, None]:
    """Generate an error message for streaming."""
    yield f"data: {json.dumps({'type': 'error', 'error': error_message})}\n\n"


async def get_mcp_tools_for_openai(server_path: str) -> List[Dict[str, Any]]:
    """Get MCP tools formatted for OpenAI."""
    tools = []
    
    try:
        # Get all MCP tools
        mcp_tools = await get_mcp_tools()
        
        # Format each tool for OpenAI
        for tool in mcp_tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            # Add parameters
            for param in tool.parameters:
                param_schema = {}
                
                # Convert parameter type to OpenAI format
                if param.type in ["integer", "int"]:
                    param_schema["type"] = "integer"
                elif param.type in ["number", "float"]:
                    param_schema["type"] = "number"
                elif param.type in ["boolean", "bool"]:
                    param_schema["type"] = "boolean"
                elif param.type in ["array", "list"]:
                    param_schema["type"] = "array"
                    param_schema["items"] = {"type": "string"}
                elif param.type in ["object", "dict"]:
                    param_schema["type"] = "object"
                else:
                    param_schema["type"] = "string"
                
                if param.description:
                    param_schema["description"] = param.description
                    
                openai_tool["function"]["parameters"]["properties"][param.name] = param_schema
                
                if param.required:
                    openai_tool["function"]["parameters"]["required"].append(param.name)
            
            tools.append(openai_tool)
        
        return tools
    
    except Exception as e:
        logger.exception(f"Error getting MCP tools for OpenAI: {e}")
        return []



async def call_openai(request: ChatRequest) -> Tuple[str, List[Dict[str, Any]]]:
    """Call the OpenAI API for chat completion."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Convert the messages to OpenAI format
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in request.messages
            ]
            
            # Prepare the payload
            payload = {
                "model": request.model,
                "messages": messages,
                "stream": False,
                "tools": []
            }
            
            # Add MCP tools if server path is provided
            if request.mcp_server:
                # Get MCP tools and format for OpenAI
                mcp_tools = await get_mcp_tools_for_openai(request.mcp_server)
                if mcp_tools:
                    payload["tools"] = mcp_tools
                    payload["tool_choice"] = "auto"
            
            # Call the OpenAI API
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"].get("content") or ""
            tool_calls = []
            
            # Process any tool calls
            if "tool_calls" in data["choices"][0]["message"]:
                raw_tool_calls = data["choices"][0]["message"]["tool_calls"]
                
                for tool_call in raw_tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])
                    
                    # Execute the tool using MCP
                    tool_result = await execute_mcp_tool(
                        request.mcp_server, 
                        tool_name, 
                        tool_args
                    )
                    
                    tool_calls.append({
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result
                    })
            
            return content, tool_calls
    
    except Exception as e:
        logger.exception(f"Error calling OpenAI: {e}")
        raise


async def stream_openai(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Stream responses from OpenAI API."""
    try:
        # Signal start of streaming
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Convert the messages to OpenAI format
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in request.messages
            ]
            
            # Prepare the payload
            payload = {
                "model": request.model,
                "messages": messages,
                "stream": True,
                "tools": []
            }
            
            # Add MCP tools if server path is provided
            if request.mcp_server:
                # Get MCP tools and format for OpenAI
                mcp_tools = await get_mcp_tools_for_openai(request.mcp_server)
                if mcp_tools:
                    payload["tools"] = mcp_tools
                    payload["tool_choice"] = "auto"
            
            # Call the OpenAI API with streaming
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                stream=True,
            )
            
            content_buffer = ""
            current_tool_call = None
            tool_calls = []
            
            async with response as r:
                r.raise_for_status()
                async for chunk in r.aiter_lines():
                    if not chunk.strip() or not chunk.startswith('data: '):
                        continue
                        
                    # Extract the data part
                    if chunk.startswith('data: '):
                        chunk = chunk[6:]
                    
                    try:
                        data = json.loads(chunk)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        
                        # Handle content updates
                        if "content" in delta and delta["content"]:
                            content_buffer += delta["content"]
                            yield f"data: {json.dumps({'type': 'content', 'chunk': delta['content']})}\n\n"
                            
                        # Handle tool calls
                        if "tool_calls" in delta:
                            for tool_delta in delta["tool_calls"]:
                                # Get the tool call index
                                index = tool_delta.get("index", 0)
                                
                                # Ensure we have a list of tool calls of sufficient length
                                while len(tool_calls) <= index:
                                    tool_calls.append({
                                        "id": "",
                                        "type": "function", 
                                        "function": {"name": "", "arguments": ""}
                                    })
                                
                                # Update the tool call at this index
                                if "id" in tool_delta:
                                    tool_calls[index]["id"] = tool_delta["id"]
                                
                                if "function" in tool_delta:
                                    if "name" in tool_delta["function"]:
                                        tool_calls[index]["function"]["name"] = tool_delta["function"]["name"]
                                    
                                    if "arguments" in tool_delta["function"]:
                                        tool_calls[index]["function"]["arguments"] += tool_delta["function"]["arguments"]
                                        
                                # Check if we have a complete tool call
                                tool_call = tool_calls[index]
                                if (tool_call["id"] and 
                                    tool_call["function"]["name"] and 
                                    tool_call["function"]["arguments"]):
                                    try:
                                        # Try to parse the arguments as JSON
                                        args = json.loads(tool_call["function"]["arguments"])
                                        
                                        # Emit the tool call event
                                        yield f"data: {json.dumps({'type': 'tool_call', 'tool_call': {
                                            'name': tool_call['function']['name'],
                                            'args': args
                                        }})}\n\n"
                                        
                                        # Execute the tool
                                        tool_result = await execute_mcp_tool(
                                            request.mcp_server,
                                            tool_call["function"]["name"],
                                            args
                                        )
                                        
                                        # Emit the tool result event
                                        yield f"data: {json.dumps({'type': 'tool_result', 'tool_result': tool_result})}\n\n"
                                    except json.JSONDecodeError:
                                        # Arguments are not complete JSON yet, continue
                                        pass
                    except json.JSONDecodeError:
                        # Skip invalid JSON
                        pass
            
            # Signal end of streaming
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
    
    except Exception as e:
        logger.exception(f"Error streaming from OpenAI: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


async def call_anthropic(request: ChatRequest) -> Tuple[str, List[Dict[str, Any]]]:
    """Call the Anthropic Claude API for chat completion."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Convert the messages to Anthropic format
            messages = []
            system_prompt = ""
            
            for msg in request.messages:
                if msg.role == "system":
                    system_prompt = msg.content
                else:
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # Prepare the payload
            payload = {
                "model": request.model,
                "messages": messages,
                "stream": False,
                "max_tokens": 4096
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            # Call the Anthropic API
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": request.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            
            response.raise_for_status()
            data = response.json()
            
            content = data.get("content", [])
            text_content = ""
            
            # Extract text content from blocks
            for block in content:
                if block.get("type") == "text":
                    text_content += block.get("text", "")
            
            # Claude doesn't natively support tool calls, so we return empty list
            tool_calls = []
            
            return text_content, tool_calls
    
    except Exception as e:
        logger.exception(f"Error calling Anthropic: {e}")
        raise


async def stream_anthropic(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Stream responses from Anthropic Claude API."""
    try:
        # Signal start of streaming
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Convert the messages to Anthropic format
            messages = []
            system_prompt = ""
            
            for msg in request.messages:
                if msg.role == "system":
                    system_prompt = msg.content
                else:
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # Prepare the payload
            payload = {
                "model": request.model,
                "messages": messages,
                "stream": True,
                "max_tokens": 4096
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            # Call the Anthropic API with streaming
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": request.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
                stream=True,
            )
            
            async with response as r:
                r.raise_for_status()
                async for chunk in r.aiter_lines():
                    if not chunk.strip() or not chunk.startswith('data: '):
                        continue
                        
                    # Extract the data part
                    if chunk.startswith('data: '):
                        chunk = chunk[6:]
                        
                    try:
                        data = json.loads(chunk)
                        
                        # Check for event type
                        event_type = data.get("type")
                        
                        if event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    yield f"data: {json.dumps({'type': 'content', 'chunk': text})}\n\n"
                        
                        elif event_type == "message_stop":
                            break
                            
                    except json.JSONDecodeError:
                        # Skip invalid JSON
                        pass
            
            # Signal end of streaming
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
    
    except Exception as e:
        logger.exception(f"Error streaming from Anthropic: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


async def call_openrouter(request: ChatRequest) -> Tuple[str, List[Dict[str, Any]]]:
    """Call the OpenRouter API for chat completion."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Convert the messages to OpenRouter format
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in request.messages
            ]
            
            # Prepare the payload
            payload = {
                "model": request.model,
                "messages": messages,
                "stream": False,
                "tools": []
            }
            
            # Add MCP tools if server path is provided
            if request.mcp_server:
                # Get MCP tools and format for OpenAI (compatible with OpenRouter)
                mcp_tools = await get_mcp_tools_for_openai(request.mcp_server)
                if mcp_tools:
                    payload["tools"] = mcp_tools
                    payload["tool_choice"] = "auto"
            
            # Call the OpenRouter API
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "HTTP-Referer": "http://localhost:8000",  # Required by OpenRouter
                    "X-Title": "MCP Test UI",  # Optional app name
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"].get("content") or ""
            tool_calls = []
            
            # Process any tool calls
            if "tool_calls" in data["choices"][0]["message"]:
                raw_tool_calls = data["choices"][0]["message"]["tool_calls"]
                
                for tool_call in raw_tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])
                    
                    # Execute the tool using MCP
                    tool_result = await execute_mcp_tool(
                        request.mcp_server, 
                        tool_name, 
                        tool_args
                    )
                    
                    tool_calls.append({
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result
                    })
            
            return content, tool_calls
    
    except Exception as e:
        logger.exception(f"Error calling OpenRouter: {e}")
        raise


async def stream_openrouter(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Stream responses from OpenRouter API."""
    try:
        # Signal start of streaming
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Convert the messages to OpenRouter format
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in request.messages
            ]
            
            # Prepare the payload
            payload = {
                "model": request.model,
                "messages": messages,
                "stream": True,
                "tools": []
            }
            
            # Add MCP tools if server path is provided
            if request.mcp_server:
                # Get MCP tools and format for OpenAI (compatible with OpenRouter)
                mcp_tools = await get_mcp_tools_for_openai(request.mcp_server)
                if mcp_tools:
                    payload["tools"] = mcp_tools
                    payload["tool_choice"] = "auto"
            
            # Call the OpenRouter API with streaming
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "HTTP-Referer": "http://localhost:8000",  # Required by OpenRouter
                    "X-Title": "MCP Test UI",  # Optional app name
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=90.0
            )
            
            response.raise_for_status()
            
            # Process the streaming response line by line
            async for line in response.aiter_lines():
                if not line.strip() or not line.startswith('data: '):
                    continue
                    
                # Extract the data part
                if line.startswith('data: '):
                    line = line[6:]
                
                if line == "[DONE]":
                    break
                
                try:
                    data = json.loads(line)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    
                    # Handle content updates
                    if "content" in delta and delta["content"]:
                        yield f"data: {json.dumps({'type': 'content', 'chunk': delta['content']})}\n\n"
                        
                    # Handle tool calls
                    if "tool_calls" in delta:
                        for tool_delta in delta["tool_calls"]:
                            # Get the tool call index
                            index = tool_delta.get("index", 0)
                            function_data = tool_delta.get("function", {})
                            
                            # Emit the tool call event if complete
                            if "name" in function_data and "arguments" in function_data:
                                try:
                                    # Try to parse the arguments as JSON
                                    args = json.loads(function_data["arguments"])
                                    
                                    # Emit the tool call event
                                    tool_call_data = {
                                        'type': 'tool_call', 
                                        'tool_call': {
                                            'name': function_data['name'],
                                            'args': args
                                        }
                                    }
                                    yield f"data: {json.dumps(tool_call_data)}\n\n"
                                    
                                    # Execute the tool
                                    try:
                                        tool_result = await execute_mcp_tool(
                                            request.mcp_server,
                                            function_data["name"],
                                            args
                                        )
                                        
                                        # Emit the tool result event
                                        yield f"data: {json.dumps({'type': 'tool_result', 'tool_result': tool_result})}\n\n"
                                    except Exception as tool_error:
                                        logger.exception(f"Error executing tool: {tool_error}")
                                        yield f"data: {json.dumps({'type': 'error', 'error': f'Tool execution error: {str(tool_error)}'})}\n\n"
                                except json.JSONDecodeError:
                                    # Arguments are not complete JSON yet
                                    pass
                except json.JSONDecodeError:
                    # Skip invalid JSON
                    pass
        
        # Signal end of streaming
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
    
    except Exception as e:
        logger.exception(f"Error streaming from OpenRouter: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


async def call_gemini(request: ChatRequest) -> Tuple[str, List[Dict[str, Any]]]:
    """Call the Google Gemini API for chat completion."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Convert the messages to Gemini format
            gemini_messages = []
            
            for msg in request.messages:
                role = msg.role
                # Map roles to Gemini format
                if role == "system":
                    # Prepend system message to first user message as Gemini doesn't have system role
                    continue
                elif role == "assistant":
                    role = "model"
                    
                gemini_messages.append({
                    "role": role,
                    "parts": [{"text": msg.content}]
                })
            
            # Add system message to the beginning if it exists
            system_content = next((msg.content for msg in request.messages if msg.role == "system"), None)
            if system_content and gemini_messages:
                # Find first user message
                for i, msg in enumerate(gemini_messages):
                    if msg["role"] == "user":
                        # Prepend system message to this user message
                        gemini_messages[i]["parts"][0]["text"] = f"[System: {system_content}]\n\n" + gemini_messages[i]["parts"][0]["text"]
                        break
            
            # Prepare the payload
            payload = {
                "contents": gemini_messages,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 4096,
                }
            }
            
            # Call the Gemini API
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent?key={request.api_key}"
            response = await client.post(
                api_url,
                json=payload,
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract the response text
            content = ""
            if "candidates" in data and data["candidates"]:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                for part in parts:
                    if "text" in part:
                        content += part["text"]
            
            # Gemini doesn't natively support tool calls, so we return empty list
            tool_calls = []
            
            return content, tool_calls
    
    except Exception as e:
        logger.exception(f"Error calling Gemini: {e}")
        raise


async def stream_gemini(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Stream responses from Google Gemini API."""
    try:
        # Signal start of streaming
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        
        # Note: Gemini's API doesn't support true streaming in the way OpenAI or Anthropic do
        # We'll simulate streaming by breaking up the response
        content, _ = await call_gemini(request)
        
        # Simulate streaming by sending chunks of text
        chunk_size = 10  # Characters per chunk
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i+chunk_size]
            yield f"data: {json.dumps({'type': 'content', 'chunk': chunk})}\n\n"
            await asyncio.sleep(0.05)  # Small delay to simulate streaming
        
        # Signal end of streaming
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
    
    except Exception as e:
        logger.exception(f"Error streaming from Gemini: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Test UI")
    parser.add_argument("--server", "-s", help="Path to the MCP server file")
    parser.add_argument("--host", "-H", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to")
    
    args = parser.parse_args()
    
    run_server(args.server, args.host, args.port)
