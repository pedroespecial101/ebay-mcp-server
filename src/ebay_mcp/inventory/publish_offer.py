"""
eBay Inventory MCP Server - Publish Offer Functionality
"""
import logging
import os
import sys
import httpx
import json

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def publish_offer_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def publish_offer(offer_id: str) -> str:
        """Publishes a specific offer, converting it into an active eBay listing.

        This action makes an unpublished offer available for sale on eBay.

        Args:
            offer_id: The unique identifier of the offer to be published.

        Returns:
            A JSON string containing the `listingId` of the newly created eBay listing 
            and any `warnings`, or an error message if the publication fails.
        """
        logger.info(f"Executing publish_offer MCP tool for offer_id='{offer_id}'")

        try:
            async def _api_call(access_token: str, client: httpx.AsyncClient):
                headers = get_standard_ebay_headers(access_token)
                # The publishOffer endpoint is a POST request with the offer_id in the path
                # and no request body.
                publish_url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish"

                logger.debug(f"publish_offer: Sending POST request to {publish_url}")
                
                response = await client.post(publish_url, headers=headers)
                response.raise_for_status() # Will raise an exception for 4xx/5xx responses

                response_data = response.json()
                listing_id = response_data.get('listingId')
                warnings = response_data.get('warnings')

                if listing_id:
                    logger.info(f"Successfully published offer {offer_id}. New listing ID: {listing_id}")
                    return json.dumps({"listingId": listing_id, "warnings": warnings if warnings else []})
                else:
                    logger.error(f"publish_offer for {offer_id} did not return a listingId. Response: {response_data}")
                    return json.dumps({"error": "Failed to publish offer, no listingId returned.", "details": response_data})

            async with httpx.AsyncClient() as client:
                result = await execute_ebay_api_call("publish_offer", client, _api_call)
                return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in publish_offer for {offer_id}: {str(e.response.text)}")
            return json.dumps({"error": f"HTTP error publishing offer: {e.response.status_code}", "details": e.response.text})
        except Exception as e:
            logger.error(f"Error in publish_offer for {offer_id}: {str(e)}")
            return json.dumps({"error": f"Error publishing offer: {str(e)}"})
