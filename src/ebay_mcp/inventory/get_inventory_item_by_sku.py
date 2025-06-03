"""
eBay Inventory MCP Server - Get Inventory Item by SKU Functionality
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
from models.ebay.inventory import InventoryItemDetails, InventoryItemResponse
from models.mcp_tools import GetInventoryItemBySkuParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, is_token_error
from utils.debug_httpx import create_debug_client

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def get_inventory_item_by_sku_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def get_inventory_item_by_sku(sku: str) -> str:
        """Retrieve a specific inventory item using its SKU identifier.
        
        Args:
            sku: The seller-defined SKU (Stock Keeping Unit) of the inventory item to retrieve.
        """
        logger.info(f"Executing get_inventory_item_by_sku MCP tool with SKU='{sku}'.")
        
        # Validate parameters using Pydantic model
        try:
            params = GetInventoryItemBySkuParams(sku=sku)
            
            async def _api_call(access_token: str, client: httpx.AsyncClient):
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
                    "Accept-Language": "en-GB",
                }
                
                base_url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{params.sku}"
                
                log_headers = headers.copy()
                log_headers['Authorization'] = f"Bearer {access_token[:20]}...<truncated>"
                logger.debug(f"get_inventory_item_by_sku: Headers for API call: {log_headers}")
                logger.debug(f"get_inventory_item_by_sku: Request URL: {base_url} using token {access_token[:10]}...")
                
                # Make the API call to get inventory item by SKU
                response = await client.get(base_url, headers=headers)
                logger.info(f"get_inventory_item_by_sku: API response status: {response.status_code}")
                response_text_snippet = response.text[:500] if response.text else "[Empty Response Body]"
                logger.debug(f"get_inventory_item_by_sku: API response text (first 500 chars): {response_text_snippet}...")
                
                # Raise for status to trigger error handling in execute_ebay_api_call
                response.raise_for_status()
                
                logger.info(f"get_inventory_item_by_sku: Successfully retrieved inventory item for SKU {params.sku}.")
                return response.text
            
            # Use the enhanced debug client
            async with create_debug_client() as client:
                result = await execute_ebay_api_call("get_inventory_item_by_sku", client, _api_call)
                
                # Try to parse the response as an InventoryItemResponse
                try:
                    if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                        result_json = json.loads(result)
                        
                        # Create Pydantic model for the inventory item
                        inventory_item = InventoryItemDetails(
                            sku=result_json.get('sku', params.sku),
                            locale=result_json.get('locale'),
                            condition=result_json.get('condition'),
                            condition_description=result_json.get('conditionDescription'),
                            package_weight_and_size=result_json.get('packageWeightAndSize'),
                            product=result_json.get('product'),
                            availability=result_json.get('availability'),
                            group_ids=result_json.get('groupIds', [])
                        )
                        
                        inventory_response = InventoryItemResponse.success_response(inventory_item)
                        logger.info(f"Parsed inventory item details for SKU {params.sku}")
                        # Return the original JSON for backward compatibility
                        return result
                except Exception as e:
                    logger.warning(f"Failed to parse inventory item details: {str(e)}")
                
                return result
        except Exception as e:
            logger.error(f"Error in get_inventory_item_by_sku: {str(e)}")
            return f"Error in inventory item parameters: {str(e)}"
