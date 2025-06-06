"""
eBay Inventory MCP Server - Listing Fees Functionality
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
from models.ebay.inventory import ListingFeeRequest, ListingFeeResponse
from models.mcp_tools import ListingFeesParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers, is_token_error

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def listing_fees_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def get_listing_fees(offer_ids: list) -> str:
        """Get listing fees for unpublished offers.
        
        Args:
            offer_ids: List of offer IDs to get fees for (up to 250).
        """
        logger.info(f"Executing get_listing_fees MCP tool with {len(offer_ids)} offer IDs.")
        
        # Validate parameters using Pydantic model
        try:
            params = ListingFeesParams(offer_ids=offer_ids)
            
            async def _api_call(access_token: str, client: httpx.AsyncClient):
                # Use standardized eBay API headers
                headers = get_standard_ebay_headers(access_token)
                
                url = "https://api.ebay.com/sell/inventory/v1/offer/get_listing_fees"
                logger.debug(f"get_listing_fees: Making API call to {url} using token {access_token[:10]}...")
                
                # Create the request payload
                fee_request = ListingFeeRequest(offers=[{"offerId": offer_id} for offer_id in params.offer_ids])
                
                response = await client.post(url, headers=headers, json=fee_request.dict())
                logger.debug(f"get_listing_fees: Response status code: {response.status_code}")
                response.raise_for_status()  # This will be caught by _execute_ebay_api_call if there's an error
                
                logger.info(f"get_listing_fees: Successfully retrieved listing fees for {len(params.offer_ids)} offers")
                return response.text
            
            async with httpx.AsyncClient() as client:
                result = await execute_ebay_api_call("get_listing_fees", client, _api_call)
                
                # Try to parse the response as a ListingFeeResponse
                try:
                    if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                        result_json = json.loads(result)
                        # Parse the response here if needed
                        # This would involve extracting fee details and constructing a Pydantic model
                        logger.info(f"Parsed listing fees response")
                    return result
                except Exception as e:
                    logger.warning(f"Failed to parse listing fees response: {str(e)}")
                    return result
        except Exception as e:
            logger.error(f"Error in get_listing_fees: {str(e)}")
            return f"Error getting listing fees: {str(e)}"
