"""
eBay Catalog MCP Server - Handles eBay Catalog APIs
"""
import logging
import os
import sys
import asyncio
from fastmcp import FastMCP
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import the tool modules
from ebay_mcp.catalog.search import search_by_gtin_tool

# Load environment variables
load_dotenv()

# Determine if we're in DEBUG mode
DEBUG_MODE = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper() == 'DEBUG'

# Get logger
logger = logging.getLogger(__name__)

# Create Catalog MCP server
catalog_mcp = FastMCP("eBay Catalog API")

# Register tools from modules
async def register_all_tools():
    await search_by_gtin_tool(catalog_mcp)

# Run the async registration function
loop = asyncio.get_event_loop()
loop.run_until_complete(register_all_tools())
