"""
eBay Inventory MCP Server - Delete Inventory Item Functionality
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
from models.ebay.inventory import DeleteInventoryItemResponse
from models.mcp_tools import DeleteInventoryItemParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers, is_token_error
from utils.debug_httpx import create_debug_client

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def delete_inventory_item_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def delete_inventory_item(sku: str) -> str:
        """Delete an inventory item by its SKU.
        
        This will delete the inventory item record and have the following effects:
        - Delete any and all unpublished offers associated with that SKU
        - Delete any and all single-variation eBay listings associated with that SKU
        - Automatically remove that SKU from multiple-variation listings and inventory item groups
        
        Args:
            sku: The seller-defined SKU (Stock Keeping Unit) of the inventory item to delete.
        """
        logger.info(f"Executing delete_inventory_item MCP tool with SKU='{sku}'.")
        
        # Validate parameters using Pydantic model
        try:
            params = DeleteInventoryItemParams(sku=sku)
            
            async def _api_call(access_token: str, client: httpx.AsyncClient):
                # Use standardized eBay API headers
                headers = get_standard_ebay_headers(access_token)
                
                base_url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{params.sku}"
                
                log_headers = headers.copy()
                log_headers['Authorization'] = f"Bearer {access_token[:20]}...<truncated>"
                logger.debug(f"delete_inventory_item: Headers for API call: {log_headers}")
                logger.debug(f"delete_inventory_item: Request URL: {base_url} using token {access_token[:10]}...")
                
                # Make the API call to delete inventory item by SKU
                response = await client.delete(base_url, headers=headers)
                logger.info(f"delete_inventory_item: API response status: {response.status_code}")
                response_text_snippet = response.text[:500] if response.text else "[Empty Response Body]"
                logger.debug(f"delete_inventory_item: API response text (first 500 chars): {response_text_snippet}...")
                
                # For DELETE operations, 204 No Content is the expected success response
                if response.status_code == 204:
                    logger.info(f"delete_inventory_item: Successfully deleted inventory item for SKU {params.sku}.")
                    return json.dumps(DeleteInventoryItemResponse.success_response(params.sku).dict())
                else:
                    # Raise for status to trigger error handling in execute_ebay_api_call
                    response.raise_for_status()
                    return response.text
            
            # Use the enhanced debug client
            async with create_debug_client() as client:
                result = await execute_ebay_api_call("delete_inventory_item", client, _api_call)
                
                # Check if the result is already a success response from our function
                try:
                    if result.startswith('{"success":true'):
                        logger.info(f"Successfully processed delete request for SKU {params.sku}")
                        return result
                    elif not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                        # If we get here, it means the API returned something other than 204
                        # This could be an error response or unexpected success response
                        logger.warning(f"Unexpected response from delete API: {result}")
                        return result
                    else:
                        # This is an error from the authentication or network layer
                        return result
                except Exception as e:
                    logger.warning(f"Failed to parse delete response: {str(e)}")
                    return result
                
        except Exception as e:
            logger.error(f"Error in delete_inventory_item: {str(e)}")
            error_response = DeleteInventoryItemResponse.error_response(str(e), sku)
            return json.dumps(error_response.dict())
