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

# Imports for MCP Test UI refactor
from . import config
from . import mcp_utils
from . import models # Required for get_mcp_tools_for_openai type hints
from .routes_mcp import router as mcp_router, init_router_dependencies

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

# Initialize MCP server path from environment variable
config.mcp_server_path = os.getenv("MCP_SERVER_PATH")
logger.info(f"Initial MCP_SERVER_PATH from env: {config.mcp_server_path}")

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)

# Set up templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Initialize templates for MCP router and include it
init_router_dependencies(templates)
app.include_router(mcp_router, prefix="/mcp", tags=["MCP Tools"])


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


def run_server(server_path_override: Optional[str] = None, host: str = "127.0.0.1", port: int = 8001):
    """Run the MCP Test UI server (refactored version)."""
    if server_path_override:
        config.mcp_server_path = server_path_override
        logger.info(f"MCP_SERVER_PATH overridden by command line: {config.mcp_server_path}")
    
    logger.info(f"Refactored MCP Test UI will run on http://{host}:{port}")
    logger.info(f"Using MCP Server Path: {config.mcp_server_path}")
    uvicorn.run(app, host=host, port=port)


async def stream_error(error_message: str) -> AsyncGenerator[str, None]:
    """Generate an error message for streaming."""
    yield f"data: {json.dumps({'type': 'error', 'error': error_message})}\n\n"


async def get_mcp_tools_for_openai(server_path: str) -> List[Dict[str, Any]]:
    """Get MCP tools formatted for OpenAI."""
    tools_formatted = []
    
    try:
        # Get all MCP tools using the utility function, providing the specific server_path
        # The models MCPTool and MCPToolParameter are now accessed via models.MCPTool etc.
        mcp_tools_list: List[models.MCPTool] = await mcp_utils.get_mcp_tools(server_path_override=server_path)
        
        # Format each tool for OpenAI
        for tool_item in mcp_tools_list:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool_item.name,
                    "description": tool_item.description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            # Add parameters
            for param_item in tool_item.parameters:
                param_schema = {}
                
                # Convert parameter type to OpenAI format
                if param_item.type_ in ["integer", "int"]:
                    param_schema["type"] = "integer"
                elif param_item.type_ in ["number", "float"]:
                    param_schema["type"] = "number"
                elif param_item.type_ in ["boolean", "bool"]:
                    param_schema["type"] = "boolean"
                elif param_item.type_ in ["array", "list"]:
                    param_schema["type"] = "array"
                    param_schema["items"] = {"type": "string"}
                elif param_item.type_ in ["object", "dict"]:
                    param_schema["type"] = "object"
                else:
                    param_schema["type"] = "string"
                
                if param_item.description:
                    param_schema["description"] = param_item.description
                    
                openai_tool["function"]["parameters"]["properties"][param_item.name] = param_schema
                
                if param_item.required:
                    openai_tool["function"]["parameters"]["required"].append(param_item.name)
            
            tools_formatted.append(openai_tool)
        
        return tools_formatted
    
    except Exception as e:
        logger.exception(f"Error getting MCP tools for OpenAI from {server_path}: {e}")
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
    
    parser = argparse.ArgumentParser(description="MCP Test UI (Refactored)")
    parser.add_argument("--server", "-s", help="Path to the MCP server file (overrides MCP_SERVER_PATH env var for this session)")
    parser.add_argument("--host", "-H", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8001, help="Port to bind to (default 8001 for refactored app)")
    
    args = parser.parse_args()
    
    # Ensure .env is loaded if running as script, for config.mcp_server_path initialization
    if not config.mcp_server_path and not args.server:
        logger.warning("MCP_SERVER_PATH environment variable not set and --server argument not provided.")
        logger.warning("MCP UI may not function correctly without a server path.")
        # Attempt to load .env again in case it wasn't loaded because this is run as a script directly
        load_dotenv(find_dotenv(usecwd=True)) # Try to find .env in current working directory
        config.mcp_server_path = os.getenv("MCP_SERVER_PATH")
        logger.info(f"Attempted re-load of MCP_SERVER_PATH from env: {config.mcp_server_path}")


    run_server(server_path_override=args.server, host=args.host, port=args.port)
