"""
eBay Inventory MCP Server - Update Offer Functionality
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
from models.ebay.inventory import UpdateOfferRequest, OfferDetails, OfferResponse
from models.mcp_tools import UpdateOfferParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, is_token_error

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def update_offer_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def update_offer(offer_id: str, sku: str, marketplace_id: str = "EBAY_GB", price: float = None, available_quantity: int = None) -> str:
        """Update an existing offer with new price and/or quantity.
        
        Args:
            offer_id: The unique identifier of the offer to update.
            sku: The seller-defined SKU (Stock Keeping Unit) of the offer.
            marketplace_id: The eBay marketplace ID (default: EBAY_GB).
            price: New price for the offer (optional).
            available_quantity: New quantity for the offer (optional).
        """
        logger.info(f"Executing update_offer MCP tool with offer_id='{offer_id}', sku='{sku}'")
        
        # Validate parameters using Pydantic model
        try:
            params = UpdateOfferParams(
                offer_id=offer_id,
                sku=sku,
                marketplace_id=marketplace_id,
                price=price,
                available_quantity=available_quantity
            )
            
            # Check if at least one update field is specified
            if params.price is None and params.available_quantity is None:
                return "Error: At least one of price or available_quantity must be specified."

            async def _api_call(access_token: str, client: httpx.AsyncClient):
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-EBAY-C-MARKETPLACE-ID": params.marketplace_id,
                    "Accept-Language": "en-GB"
                }
                
                # First, get the current offer details to ensure we have all required fields
                get_url = f"https://api.ebay.com/sell/inventory/v1/offer/{params.offer_id}"
                logger.debug(f"update_offer: Getting current offer details from: {get_url}")
                
                get_response = await client.get(get_url, headers=headers)
                get_response.raise_for_status()  # This will be caught by _execute_ebay_api_call if there's an error
                
                current_offer = get_response.json()
                logger.debug(f"update_offer: Successfully retrieved current offer details for {params.sku}")
                
                # Create an update request based on the current offer
                update_request = UpdateOfferRequest(
                    offer_id=params.offer_id,
                    sku=params.sku,
                    marketplace_id=params.marketplace_id,
                    format=current_offer.get('format', 'FIXED_PRICE'),
                    available_quantity=params.available_quantity if params.available_quantity is not None else current_offer.get('availableQuantity'),
                    category_id=current_offer.get('categoryId', ''),
                    listing_policies=current_offer.get('listingPolicies', {}),
                    merchant_location_key=current_offer.get('merchantLocationKey', ''),
                )
                
                # Update price if provided
                if params.price is not None:
                    current_price = current_offer.get('price', {})
                    update_request.price = {
                        'currency': current_price.get('currency', 'GBP'),
                        'value': str(params.price)
                    }
                else:
                    update_request.price = current_offer.get('price', {})
                
                # Convert to dict for JSON serialization
                update_data = update_request.dict(exclude_none=True)
                logger.debug(f"update_offer: Prepared update request data: {update_data}")
                
                # Send update request
                update_url = f"https://api.ebay.com/sell/inventory/v1/offer/{params.offer_id}"
                logger.info(f"update_offer: Sending update request to {update_url}")
                
                update_response = await client.put(update_url, headers=headers, json=update_data)
                update_response.raise_for_status()  # This will be caught by _execute_ebay_api_call if there's an error
                
                logger.info(f"update_offer: Successfully updated offer {params.offer_id} for SKU {params.sku}")
                return update_response.text
            
            async with httpx.AsyncClient() as client:
                result = await execute_ebay_api_call("update_offer", client, _api_call)
                return result
        except Exception as e:
            logger.error(f"Error in update_offer: {str(e)}")
            return f"Error updating offer: {str(e)}"
