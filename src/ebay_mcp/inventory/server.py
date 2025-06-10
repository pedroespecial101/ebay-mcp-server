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

# Import inventory-related models
from models.ebay.inventory import OfferRequest, OfferDetails, OfferResponse
from models.ebay.inventory import UpdateOfferRequest, WithdrawOfferRequest, ListingFeeRequest, ListingFeeResponse
from models.mcp_tools import OfferBySkuParams, UpdateOfferParams, WithdrawOfferParams, ListingFeesParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, is_token_error
from utils.debug_httpx import create_debug_client

# Load environment variables
load_dotenv()

# Determine if we're in DEBUG mode
DEBUG_MODE = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper() == 'DEBUG'

# Import tool modules
from ebay_mcp.inventory.update_offer import update_offer_tool
from ebay_mcp.inventory.withdraw_offer import withdraw_offer_tool
from ebay_mcp.inventory.manage_offer import manage_offer_tool
from ebay_mcp.inventory.listing_fees import listing_fees_tool
from ebay_mcp.inventory.get_inventory_item_by_sku import get_inventory_item_by_sku_tool
from ebay_mcp.inventory.get_inventory_items import get_inventory_items_tool
from ebay_mcp.inventory.delete_inventory_item import delete_inventory_item_tool
from ebay_mcp.inventory.create_or_replace_inventory_item import create_or_replace_inventory_item_tool

# Get logger
logger = logging.getLogger(__name__)

# Create Inventory MCP server
inventory_mcp = FastMCP("eBay Inventory API")

# Register tools from modules
async def register_all_tools():
    await update_offer_tool(inventory_mcp)
    await withdraw_offer_tool(inventory_mcp)
    await manage_offer_tool(inventory_mcp)  
    await listing_fees_tool(inventory_mcp)
    await get_inventory_item_by_sku_tool(inventory_mcp)
    await get_inventory_items_tool(inventory_mcp)
    await delete_inventory_item_tool(inventory_mcp)
    await create_or_replace_inventory_item_tool(inventory_mcp)

# Run the async registration function
loop = asyncio.get_event_loop()
loop.run_until_complete(register_all_tools())

@inventory_mcp.tool()
async def get_offer_by_sku(sku: str) -> str:
    """Get offer details for a specific SKU from eBay Sell Inventory API.
    
    Args:
        sku: The seller-defined SKU (Stock Keeping Unit) of the offer.
    """
    logger.info(f"Executing get_offer_by_sku MCP tool with SKU='{sku}'.")
    
    # Validate parameters using Pydantic model
    try:
        params = OfferBySkuParams(sku=sku)
        
        async def _api_call(access_token: str, client: httpx.AsyncClient):
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
                "Accept-Language": "en-GB",
            }
            base_url = "https://api.ebay.com/sell/inventory/v1/offer"
            
            log_headers = headers.copy()
            log_headers['Authorization'] = f"Bearer {access_token[:20]}...<truncated>"
            logger.debug(f"get_offer_by_sku: Headers for API call: {log_headers}")
            logger.debug(f"get_offer_by_sku: Request URL for direct SKU lookup: {base_url}?sku={params.sku} using token {access_token[:10]}...")
    
            # Initial attempt: Direct SKU lookup
            response = await client.get(base_url, headers=headers, params={"sku": params.sku})
            logger.info(f"get_offer_by_sku: Direct SKU lookup response status: {response.status_code}")
            response_text_snippet = response.text[:500] if response.text else "[Empty Response Body]"
            logger.debug(f"get_offer_by_sku: Direct SKU lookup response text (first 500 chars): {response_text_snippet}...")
    
            # If direct lookup fails with 403/404 (or other client error that's not 401, which is handled by _execute_ebay_api_call),
            # try the alternative approach of listing offers.
            # Note: response.raise_for_status() will be called *after* this block if status is still not 200.
            if response.status_code in [403, 404]: 
                logger.warning(f"get_offer_by_sku: Direct SKU lookup failed with {response.status_code}. Trying alternative approach (listing offers).")
                
                list_offers_params = {"sku": params.sku, "limit": 1}
                logger.debug(f"get_offer_by_sku: Listing offers with params: {list_offers_params}")
                offers_response = await client.get(base_url, headers=headers, params=list_offers_params)
                
                logger.info(f"get_offer_by_sku: Offer list response status: {offers_response.status_code}")
                offers_response_text_snippet = offers_response.text[:500] if offers_response.text else "[Empty Response Body]"
                logger.debug(f"get_offer_by_sku: Offer list response text (first 500 chars): {offers_response_text_snippet}...")
                
                if offers_response.status_code == 200:
                    offers_data = offers_response.json()
                    if offers_data.get('offers') and len(offers_data['offers']) > 0:
                        offer_id = offers_data['offers'][0].get('offerId')
                        if offer_id:
                            logger.info(f"get_offer_by_sku: Found offer ID: {offer_id} from listing. Fetching details.")
                            offer_detail_url = f"{base_url}/{offer_id}"
                            response = await client.get(offer_detail_url, headers=headers) # Re-assign response
                            logger.info(f"get_offer_by_sku: Offer details response status (after listing): {response.status_code}")
                            response_text_snippet_detail = response.text[:500] if response.text else "[Empty Response Body]"
                            logger.debug(f"get_offer_by_sku: Offer details response text (first 500 chars): {response_text_snippet_detail}...")
                        else:
                            logger.warning("get_offer_by_sku: 'offerId' not found in listed offer. Original direct lookup response will be used.")
                    else:
                        logger.warning(f"get_offer_by_sku: No offers found in the listing for SKU {params.sku}. Original direct lookup response will be used.")
                else:
                    logger.error(f"get_offer_by_sku: Failed to list offers (alternative approach), status: {offers_response.status_code}. Original direct lookup response will be used.")
            
            # After potential fallback, raise for status on the final 'response' object.
            # This allows _execute_ebay_api_call to handle 401s from either direct or fallback calls.
            response.raise_for_status()
            
            logger.info(f"get_offer_by_sku: Successfully fetched offer for SKU {params.sku}.")
            return response.text
        
        # Use the enhanced debug client
        async with create_debug_client() as client:
            result = await execute_ebay_api_call("get_offer_by_sku", client, _api_call)
            
            # Try to parse the response as an OfferResponse
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    result_json = json.loads(result)
                    
                    # Extract offer details from the response
                    if 'offers' in result_json and len(result_json['offers']) > 0:
                        offer_data = result_json['offers'][0]
                    else:
                        offer_data = result_json
                    
                    # Create Pydantic model for the offer
                    offer_details = OfferDetails(
                        offer_id=offer_data.get('offerId', ''),
                        sku=offer_data.get('sku', params.sku),
                        marketplace_id=offer_data.get('marketplaceId', 'EBAY_GB'),
                        format=offer_data.get('format', ''),
                        available_quantity=offer_data.get('availableQuantity', 0),
                        price=offer_data.get('price', {}),
                        listing_policies=offer_data.get('listingPolicies', {}),
                        listing_description=offer_data.get('listingDescription', ''),
                        listing_status=offer_data.get('listingStatus', ''),
                        tax=offer_data.get('tax', {}),
                        category_id=offer_data.get('categoryId', ''),
                        merchant_location_key=offer_data.get('merchantLocationKey', ''),
                        inventory_location=offer_data.get('inventoryLocation', ''),
                        listing_id=offer_data.get('listingId', '')
                    )
                    
                    offer_response = OfferResponse.success_response(offer_details)
                    logger.info(f"Parsed offer details for SKU {params.sku}: {offer_details.offer_id}")
                    # Return the original JSON for backward compatibility
                    return result
            except Exception as e:
                logger.warning(f"Failed to parse offer details: {str(e)}")
            
            return result
    except Exception as e:
        logger.error(f"Error in get_offer_by_sku: {str(e)}")
        return f"Error in offer parameters: {str(e)}"
