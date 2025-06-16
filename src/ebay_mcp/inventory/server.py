"""
eBay Inventory MCP Server - Handles eBay Inventory APIs
"""
import logging
import os
import sys
import httpx
from fastmcp import FastMCP
import json
import asyncio
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, is_token_error
from utils.debug_httpx import create_debug_client

# Load environment variables
load_dotenv()

# Determine if we're in DEBUG mode
DEBUG_MODE = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper() == 'DEBUG'

# Import tool modules
from ebay_mcp.inventory.manage_offer import manage_offer_tool
from ebay_mcp.inventory.manage_inventory_item import manage_inventory_item_tool

# Get logger
logger = logging.getLogger(__name__)

# Create Inventory MCP server
inventory_mcp = FastMCP("eBay Inventory API")

# Register tools from modules
async def register_all_tools():
    await manage_offer_tool(inventory_mcp)  
    await manage_inventory_item_tool(inventory_mcp)

# Run the async registration function
loop = asyncio.get_event_loop()
loop.run_until_complete(register_all_tools())
