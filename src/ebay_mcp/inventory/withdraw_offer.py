"""
eBay Inventory MCP Server - Withdraw Offer Functionality
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
from models.ebay.inventory import WithdrawOfferRequest
from models.mcp_tools import WithdrawOfferParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, is_token_error

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def withdraw_offer_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def withdraw_offer(offer_id: str) -> str:
        """Withdraw (delete) an existing offer from eBay.
        
        Args:
            offer_id: The unique identifier of the offer to withdraw.
        """
        logger.info(f"Executing withdraw_offer MCP tool with offer_id='{offer_id}'.")
        
        # Validate parameters using Pydantic model
        try:
            params = WithdrawOfferParams(offer_id=offer_id)
            
            async def _api_call(access_token: str, client: httpx.AsyncClient):
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",  # Default to UK
                }
                
                url = f"https://api.ebay.com/sell/inventory/v1/offer/{params.offer_id}/withdraw"
                logger.debug(f"withdraw_offer: Making API call to {url} using token {access_token[:10]}...")
                
                # Create an empty request body (required by eBay API)
                withdraw_request = WithdrawOfferRequest()
                
                response = await client.post(url, headers=headers, json=withdraw_request.dict())
                logger.debug(f"withdraw_offer: Response status code: {response.status_code}")
                response.raise_for_status()  # This will be caught by _execute_ebay_api_call if there's an error
                
                logger.info(f"withdraw_offer: Successfully withdrew offer {params.offer_id}")
                return response.text or json.dumps({"success": True, "message": f"Offer {params.offer_id} successfully withdrawn"})
            
            async with httpx.AsyncClient() as client:
                result = await execute_ebay_api_call("withdraw_offer", client, _api_call)
                return result
        except Exception as e:
            logger.error(f"Error in withdraw_offer: {str(e)}")
            return f"Error withdrawing offer: {str(e)}"
