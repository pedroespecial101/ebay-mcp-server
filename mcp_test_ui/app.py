import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from dotenv import load_dotenv

import uvicorn
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add parent directory to path to import FastMCP
sys.path.append(str(Path(__file__).parent.parent))


# Imports for MCP Test UI refactor
from . import config
from . import mcp_utils
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


@app.post("/set_server_path", response_class=JSONResponse)
async def set_server_path_route(server_path: str = Form(...)):
    logger.info(f"Attempting to set MCP server path to: {server_path}")
    path_obj = Path(server_path)
    if path_obj.is_file():
        config.mcp_server_path = str(path_obj.resolve()) # Store resolved absolute path
        mcp_utils.clear_mcp_tool_cache()
        logger.info(f"MCP server path updated to: {config.mcp_server_path}")
        return JSONResponse({"message": "Server path updated successfully. Reloading..."})
    else:
        logger.error(f"Invalid server path provided: {server_path} - File not found.")
        # Raising HTTPException will be automatically converted to a JSONResponse by FastAPI
        raise HTTPException(status_code=400, detail=f"Invalid server path: '{server_path}' File not found.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Test UI")
    parser.add_argument("--server", "-s", help="Path to the MCP server script (overrides MCP_SERVER_PATH env var for this session)")
    parser.add_argument("--host", "-H", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to") # Default to 8000
    
    args = parser.parse_args()
    
    # Override MCP server path if --server argument is provided
    if args.server:
        config.mcp_server_path = args.server
        logger.info(f"Overriding MCP server path with command-line argument: {config.mcp_server_path}")
    
    # Log the MCP server path being used or warn if not set
    if not config.mcp_server_path:
        logger.warning("MCP_SERVER_PATH is not set (neither via environment nor --server arg). MCP UI may not function correctly.")
    else:
        logger.info(f"Using MCP server path: {config.mcp_server_path}")

    logger.info(f"Starting MCP Test UI on http://{args.host}:{args.port}/mcp/")
    uvicorn.run(app, host=args.host, port=args.port)
