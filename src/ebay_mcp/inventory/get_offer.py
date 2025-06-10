"""
eBay Inventory MCP Server - Get Offer Functionality
"""
import logging
import os
import sys
import httpx

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def get_offer_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def get_offer(offer_id: str) -> str:
        """Retrieves the complete details for a specific eBay offer by its Offer ID.

        This tool is essential for safely updating an offer using the `update_offer` (unsafe) tool.
        The recommended workflow is to first get the offer details with this tool, modify the necessary
        fields, and then pass the entire object to the `update_offer` tool.

        Args:
            offer_id: The unique identifier of the offer to retrieve.

        Returns:
            A JSON string containing the full offer details, or an error message.
        """
        logger.info(f"Executing get_offer MCP tool for offer_id='{offer_id}'")

        try:
            async def _api_call(access_token: str, client: httpx.AsyncClient):
                headers = get_standard_ebay_headers(access_token)
                get_url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}"

                logger.debug(f"get_offer: Sending request to {get_url}")
                
                response = await client.get(get_url, headers=headers)
                response.raise_for_status()

                offer_details = response.json()
                logger.info(f"Successfully retrieved offer details for {offer_id}")
                return offer_details

            async with httpx.AsyncClient() as client:
                result = await execute_ebay_api_call("get_offer", client, _api_call)
                return result

        except Exception as e:
            logger.error(f"Error in get_offer: {str(e)}")
            return f"Error retrieving offer: {str(e)}"
