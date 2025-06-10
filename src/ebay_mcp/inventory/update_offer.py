"""
eBay Inventory MCP Server - Unsafe Update Offer Functionality
"""
import logging
import os
import sys
import httpx
import json

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import inventory-related models
from models.ebay.inventory import UpdateOfferRequest

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def update_offer_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def update_offer(
        offer_id: str,
        sku: str,
        marketplace_id: str,
        format: str,
        available_quantity: int,
        category_id: str,
        listing_description: str,
        listing_policies: dict,
        merchant_location_key: str,
        pricing_summary: dict,
        listing_duration: str = 'GTC',
        **kwargs
    ) -> str:
        """(UNSAFE) Updates an eBay offer by performing a direct REPLACE operation.

        ⚠️ CRITICAL WARNING: This is a direct-access, unsafe tool that performs a COMPLETE REPLACEMENT of the offer object. 
        ALL current offer data will be overwritten with the values you provide. Any fields not included in the request 
        will be cleared or reset to their default values. 

        For a safer alternative, use the `update_offer_safe` tool.

        RECOMMENDED WORKFLOW:
        1. Use the `get_offer` tool to retrieve the full, current offer data.
        2. Modify the necessary fields in the retrieved data.
        3. Pass the ENTIRE modified object back to this tool to ensure no data is lost.

        Args:
            offer_id: The unique identifier of the offer to update (REQUIRED).
            sku: The seller-defined SKU (REQUIRED).
            marketplace_id: The eBay marketplace ID (e.g., EBAY_US) (REQUIRED).
            format: The listing format (e.g., FIXED_PRICE) (REQUIRED).
            available_quantity: The quantity available for purchase (REQUIRED).
            category_id: The primary eBay category ID (REQUIRED).
            listing_description: The listing description (can include HTML) (REQUIRED).
            listing_policies: A dictionary of business policies (payment, return, fulfillment) (REQUIRED).
            merchant_location_key: The key for the merchant's inventory location (REQUIRED).
            pricing_summary: A dictionary defining the price (REQUIRED).
            listing_duration: The duration of the listing. Defaults to 'GTC'.
            **kwargs: Any other valid fields for the updateOffer call can be passed as keyword arguments.

        Returns:
            Success message or error details.
        """
        logger.warning(f"Executing UNSAFE update_offer MCP tool for offer_id='{offer_id}'. This is a REPLACE operation.")

        try:
            # Construct the payload from required args and any optional kwargs
            update_data = {
                "sku": sku,
                "marketplaceId": marketplace_id,
                "format": format,
                "availableQuantity": available_quantity,
                "categoryId": category_id,
                "listingDescription": listing_description,
                "listingPolicies": listing_policies,
                "merchantLocationKey": merchant_location_key,
                "pricingSummary": pricing_summary,
                "listingDuration": listing_duration,
                **kwargs
            }

            # Validate the structure with the Pydantic model
            # Note: We don't use the model for the actual payload to allow for dynamic kwargs
            UpdateOfferRequest(**update_data, offer_id=offer_id) 

            async def _api_call(access_token: str, client: httpx.AsyncClient):
                headers = get_standard_ebay_headers(access_token)
                update_url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}"

                logger.debug(f"update_offer (unsafe): Sending request to {update_url} with data: {update_data}")
                
                response = await client.put(update_url, headers=headers, data=json.dumps(update_data))
                response.raise_for_status()

                logger.info(f"Successfully executed unsafe update for offer {offer_id}")
                return f"Successfully updated offer {offer_id}. Response: {response.text if response.text else 'No response body (success)'}"

            async with httpx.AsyncClient() as client:
                result = await execute_ebay_api_call("update_offer", client, _api_call)
                return result

        except Exception as e:
            logger.error(f"Error in unsafe update_offer: {str(e)}")
            return f"Error updating offer (unsafe): {str(e)}"
