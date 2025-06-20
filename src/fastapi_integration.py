"""
FastAPI integration for the eBay MCP Server.
This module exposes the MCP server as a FastAPI application through ASGI.
"""
import os
import sys
import logging

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the MCP server instance from main_server
from src.main_server import mcp

# Set up logging
logger = logging.getLogger(__name__)

# Create ASGI app from MCP server
mcp_app = mcp.http_app(path='/mcp')

# Create FastAPI app
app = FastAPI(
    title="eBay MCP Server API",
    description="FastAPI integration for the eBay MCP Server",
    version="0.1.0",
    lifespan=mcp_app.lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount MCP server
app.mount("/mcp-server", mcp_app)
logger.info("MCP server mounted at /mcp-server/mcp")

# Root endpoint
@app.get("/")
async def read_root():
    """Root endpoint for the FastAPI server."""
    return {
        "message": "eBay MCP Server API",
        "endpoints": {
            "mcp": "/mcp-server/mcp",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server")
    uvicorn.run("src.fastapi_integration:app", host="0.0.0.0", port=8001, reload=True)
