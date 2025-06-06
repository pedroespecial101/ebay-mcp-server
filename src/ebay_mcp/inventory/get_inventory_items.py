"""
eBay Inventory MCP Server - Get Inventory Items with Pagination Functionality
"""
import logging
import os
import sys
import httpx
from fastmcp import FastMCP
import json

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import inventory-related models
from models.ebay.inventory import InventoryItemsListResponse
from models.mcp_tools import GetInventoryItemsParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers, is_token_error
from utils.debug_httpx import create_debug_client

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def get_inventory_items_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def get_inventory_items(limit: int = 25, offset: int = 0) -> str:
        """Retrieve multiple inventory items with pagination support.
        
        Args:
            limit: The maximum number of inventory items to return per page (1-200, default: 25).
            offset: The number of inventory items to skip before starting to return results (default: 0).
        """
        logger.info(f"Executing get_inventory_items MCP tool with limit={limit}, offset={offset}.")
        
        # Validate parameters using Pydantic model
        try:
            params = GetInventoryItemsParams(limit=limit, offset=offset)
            
            async def _api_call(access_token: str, client: httpx.AsyncClient):
                # Use standardized eBay API headers
                headers = get_standard_ebay_headers(access_token)
                
                base_url = "https://api.ebay.com/sell/inventory/v1/inventory_item"
                
                # Build query parameters
                query_params = {
                    "limit": str(params.limit),
                    "offset": str(params.offset)
                }
                
                log_headers = headers.copy()
                log_headers['Authorization'] = f"Bearer {access_token[:20]}...<truncated>"
                logger.debug(f"get_inventory_items: Headers for API call: {log_headers}")
                logger.debug(f"get_inventory_items: Request URL: {base_url} with params: {query_params} using token {access_token[:10]}...")
                
                # Make the API call to get inventory items with pagination
                response = await client.get(base_url, headers=headers, params=query_params)
                logger.info(f"get_inventory_items: API response status: {response.status_code}")
                response_text_snippet = response.text[:500] if response.text else "[Empty Response Body]"
                logger.debug(f"get_inventory_items: API response text (first 500 chars): {response_text_snippet}...")
                
                # Raise for status to trigger error handling in execute_ebay_api_call
                response.raise_for_status()
                
                logger.info(f"get_inventory_items: Successfully retrieved inventory items with limit={params.limit}, offset={params.offset}.")
                return response.text
            
            # Use the enhanced debug client
            async with create_debug_client() as client:
                result = await execute_ebay_api_call("get_inventory_items", client, _api_call)
                
                # Try to parse the response as an InventoryItemsListResponse
                try:
                    if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                        result_json = json.loads(result)
                        
                        # Create Pydantic model for the inventory items list
                        inventory_list_response = InventoryItemsListResponse.success_response(result_json)
                        logger.info(f"Parsed inventory items list with {len(inventory_list_response.inventory_items)} items")
                        # Return the original JSON for backward compatibility
                        return result
                except Exception as e:
                    logger.warning(f"Failed to parse inventory items list: {str(e)}")
                
                return result
        except Exception as e:
            logger.error(f"Error in get_inventory_items: {str(e)}")
            return f"Error in inventory items parameters: {str(e)}"
