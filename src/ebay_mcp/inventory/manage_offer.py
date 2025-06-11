"""
eBay Inventory MCP Server - Manage Offer Functionality (Create, Modify, Withdraw, Publish)
"""
import logging
import os
import sys
import httpx
import json
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, root_validator

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from models.base import EbayBaseModel, EbayResponse
# Re-using UpdateOfferRequest fields for OfferDataForManage structure
from models.ebay.inventory import UpdateOfferRequest 
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers
from utils.debug_httpx import create_debug_client

logger = logging.getLogger(__name__)

class ManageOfferAction(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    WITHDRAW = "withdraw"
    PUBLISH = "publish"
    GET = "get"


class OfferDataForManage(EbayBaseModel):
    """Data payload for creating or modifying an offer. Fields are based on UpdateOfferRequest excluding offer_id and sku."""
    marketplace_id: Optional[str] = Field(None, description="The eBay marketplace ID (e.g., EBAY_US, EBAY_GB).")
    format: Optional[str] = Field(None, description="The listing format (FIXED_PRICE or AUCTION).")
    available_quantity: Optional[int] = Field(None, ge=0, description="Quantity available for purchase.")
    pricing_summary: Optional[Dict[str, Any]] = Field(None, description="Pricing container.")
    category_id: Optional[str] = Field(None, description="Primary eBay category ID.")
    listing_description: Optional[str] = Field(None, max_length=500000, description="Listing description.")
    listing_duration: Optional[str] = Field(None, description="Listing duration.")
    listing_start_date: Optional[str] = Field(None, description="Scheduled start time in UTC.")
    merchant_location_key: Optional[str] = Field(None, max_length=36, description="Merchant inventory location ID.")
    listing_policies: Optional[Dict[str, Any]] = Field(None, description="Business policies container.")
    secondary_category_id: Optional[str] = Field(None, description="Secondary category ID.")
    store_category_names: Optional[List[str]] = Field(None, max_items=2, description="eBay store category paths.")
    quantity_limit_per_buyer: Optional[int] = Field(None, ge=1, description="Max quantity per buyer.")
    lot_size: Optional[int] = Field(None, ge=1, description="Number of items in lot listing.")
    hide_buyer_details: Optional[bool] = Field(None, description="True for private listings.")
    include_catalog_product_details: Optional[bool] = Field(None, description="Apply eBay catalog product details.")
    charity: Optional[Dict[str, Any]] = Field(None, description="Charitable organization container.")
    extended_producer_responsibility: Optional[Dict[str, Any]] = Field(None, description="Eco-participation fee container.")
    regulatory: Optional[Dict[str, Any]] = Field(None, description="Regulatory information container.")
    tax: Optional[Dict[str, Any]] = Field(None, description="Tax configuration container.")


# This model will be used by FastMCP for schema generation and input validation
class ManageOfferToolInput(EbayBaseModel):
    sku: str = Field(..., description="Inventory item SKU.")
    action: ManageOfferAction = Field(..., description="Action to perform on the offer ('create', 'modify', 'withdraw', 'publish', 'get').")
    offer_data: Optional[OfferDataForManage] = Field(None, description="Data for create/modify actions. See OfferDataForManage schema.")

    @root_validator(skip_on_failure=True)
    def check_offer_data_for_action(cls, values):
        action = values.get('action')
        offer_data = values.get('offer_data')
        if action in [ManageOfferAction.CREATE, ManageOfferAction.MODIFY] and offer_data is None:
            raise ValueError("offer_data is required for 'create' or 'modify' actions.")
        if action in [ManageOfferAction.WITHDRAW, ManageOfferAction.PUBLISH, ManageOfferAction.GET] and offer_data is not None:
            # For withdraw/publish/get, we could also choose to silently ignore offer_data if provided.
            # However, raising an error is stricter and makes the API contract clearer.
            raise ValueError(f"offer_data must NOT be provided for '{action.value}' action.")
        return values


class ManageOfferResponseDetails(EbayBaseModel):
    offer_id: Optional[str] = None
    status_code: Optional[int] = None
    message: str
    details: Optional[Any] = None # To store raw response from eBay if needed

class ManageOfferToolResponse(EbayResponse[ManageOfferResponseDetails]):
    pass


async def _get_offer_by_sku(sku: str, access_token: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """Helper to fetch an offer by SKU. Returns the first offer object if found."""
    headers = get_standard_ebay_headers(access_token)
    headers['Accept'] = 'application/json' # Ensure JSON response
    url = f"https://api.ebay.com/sell/inventory/v1/offer?sku={sku}"
    logger.info(f"_get_offer_by_sku: Fetching offer for SKU '{sku}' from {url}")
    
    response = await client.get(url, headers=headers)
    log_headers = headers.copy()
    log_headers['Authorization'] = f"Bearer {access_token[:20]}...<truncated>"
    logger.debug(f"_get_offer_by_sku: Headers: {log_headers}, URL: {url}")
    logger.debug(f"_get_offer_by_sku: Response status: {response.status_code}, text: {response.text[:500]}...")

    if response.status_code == 200:
        response_data = response.json()
        offers = response_data.get("offers", [])
        if offers:
            logger.info(f"_get_offer_by_sku: Found offer for SKU '{sku}': {offers[0].get('offerId')}")
            return offers[0]
        else:
            logger.info(f"_get_offer_by_sku: No offer found for SKU '{sku}' (200 OK, but no offers array).")
            return None
    elif response.status_code == 404:
        logger.info(f"_get_offer_by_sku: No offer found for SKU '{sku}' (404 Not Found).")
        return None
    else:
        logger.error(f"_get_offer_by_sku: Error fetching offer for SKU '{sku}'. Status: {response.status_code}, Response: {response.text[:500]}")
        response.raise_for_status() # Let execute_ebay_api_call's wrapper handle it
        return None # Should not be reached


async def manage_offer_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def manage_offer(params: ManageOfferToolInput) -> str:
        """Manages eBay offers: create, modify, withdraw, or publish based on SKU.

        Uses Pydantic model ManageOfferToolInput for parameters, ensuring schema exposure.
        Args:
            params (ManageOfferToolInput): Container for SKU, action, and conditional offer_data.
        """
        # Parameters are now automatically validated by FastMCP against ManageOfferToolInput
        # Access them via params.sku, params.action, params.offer_data
        logger.info(f"Executing manage_offer MCP tool: SKU='{params.sku}', Action='{params.action.value}'")

        async def _api_call_logic(access_token: str, client: httpx.AsyncClient): # params is available in this scope
            headers = get_standard_ebay_headers(access_token)
            
            current_offer = None
            offer_id_from_current = None

            # For modify, withdraw, publish - first get the offer to get offerId and current state
            # The 'params' variable from the outer scope (manage_offer function) is used here.
            if params.action in [ManageOfferAction.MODIFY, ManageOfferAction.WITHDRAW, ManageOfferAction.PUBLISH, ManageOfferAction.GET]:
                current_offer = await _get_offer_by_sku(params.sku, access_token, client)
                if not current_offer:
                    raise ValueError(f"No existing offer found for SKU '{params.sku}' to perform '{params.action.value}'.")
                offer_id_from_current = current_offer.get('offerId')
                # For GET, we can proceed even without an offerId, but for others it's critical.
                if not offer_id_from_current and params.action not in [ManageOfferAction.GET]:
                    raise ValueError(f"Could not retrieve offerId for SKU '{params.sku}' to perform '{params.action.value}'.")

            # --- CREATE Action --- 
            if params.action == ManageOfferAction.CREATE:
                existing_offer_check = await _get_offer_by_sku(params.sku, access_token, client)
                if existing_offer_check:
                    raise ValueError(f"Offer for SKU '{params.sku}' already exists (OfferId: {existing_offer_check.get('offerId')}). Use 'modify' action to update.")

                # Validation for offer_data presence is now handled by ManageOfferToolInput's root_validator
                # if not params.offer_data: # This check is now redundant
                #     raise ValueError("offer_data is required for create action.")
                
                # Specific field requirements for 'create' action within offer_data
                if params.offer_data: # Should always be true due to validator, but good for type hinting
                    required_fields_create = ['marketplace_id', 'format', 'available_quantity', 'category_id', 'listing_policies', 'merchant_location_key', 'pricing_summary']
                    for field in required_fields_create:
                        if getattr(params.offer_data, field, None) is None:
                            raise ValueError(f"Missing required field '{field}' in offer_data for 'create' action.")
                else:
                    # This case should ideally be caught by the root_validator in ManageOfferToolInput
                    raise ValueError("offer_data is unexpectedly None for 'create' action despite validator.")

                payload = params.offer_data.dict(exclude_none=True)
                payload['sku'] = params.sku # Add SKU to the payload body as required by createOffer
                
                url = "https://api.ebay.com/sell/inventory/v1/offer"
                logger.debug(f"manage_offer (CREATE): URL: {url}, Payload: {payload}")
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                response_json = response.json()
                new_offer_id = response_json.get('offerId')
                logger.info(f"manage_offer (CREATE): Successfully created offer for SKU '{params.sku}'. New OfferId: {new_offer_id}")
                return ManageOfferToolResponse.success_response(
                    ManageOfferResponseDetails(offer_id=new_offer_id, status_code=response.status_code, message="Offer created successfully.", details=response_json)
                ).model_dump_json(indent=2)

            # --- MODIFY Action --- 
            elif params.action == ManageOfferAction.MODIFY:
                # Validation for offer_data presence is now handled by ManageOfferToolInput's root_validator
                # if not params.offer_data: # This check is now redundant
                #    raise ValueError("offer_data is required for modify action.")
                if not current_offer or not offer_id_from_current:
                     raise ValueError("Missing current_offer details for modify action.") # Should be caught by earlier checks
                if not params.offer_data: # Should be caught by validator, but defensive check
                    raise ValueError("offer_data is unexpectedly None for 'modify' action.")


                # Merge current_offer with new data. eBay's updateOffer is a full replacement.
                # Start with all fields from current_offer, then update with provided non-None fields.
                update_payload = current_offer.copy() # Start with all fields from the fetched offer
                provided_updates = params.offer_data.dict(exclude_none=True)
                update_payload.update(provided_updates) # Override with new values
                
                # Ensure critical fields are not accidentally wiped if not in provided_updates but were in current_offer
                # (The above .update() should handle this correctly by design of UpdateOfferRequest model)

                url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id_from_current}"
                logger.debug(f"manage_offer (MODIFY): URL: {url}, Payload: {update_payload}")
                response = await client.put(url, headers=headers, json=update_payload)
                response.raise_for_status() # Expect 204 No Content
                logger.info(f"manage_offer (MODIFY): Successfully modified offer '{offer_id_from_current}' for SKU '{params.sku}'.")
                return ManageOfferToolResponse.success_response(
                    ManageOfferResponseDetails(offer_id=offer_id_from_current, status_code=response.status_code, message="Offer modified successfully.")
                ).model_dump_json(indent=2)

            # --- WITHDRAW Action --- 
            elif params.action == ManageOfferAction.WITHDRAW:
                if not offer_id_from_current:
                    raise ValueError("Missing offer_id for withdraw action.") # Should be caught

                url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id_from_current}/withdraw"
                logger.debug(f"manage_offer (WITHDRAW): URL: {url}")
                # Withdraw request typically has an empty body, but API might expect Content-Type: application/json
                # The withdraw_offer.py example uses an empty WithdrawOfferRequest().dict()
                # Let's ensure Content-Type is set if sending json={} even if empty.
                headers_withdraw = headers.copy()
                headers_withdraw['Content-Type'] = 'application/json' # Often required even for empty body POSTs
                response = await client.post(url, headers=headers_withdraw, json={}) # Empty JSON body
                response.raise_for_status() # Expect 200 OK with potentially empty body
                logger.info(f"manage_offer (WITHDRAW): Successfully withdrew offer '{offer_id_from_current}' for SKU '{params.sku}'.")
                return ManageOfferToolResponse.success_response(
                    ManageOfferResponseDetails(offer_id=offer_id_from_current, status_code=response.status_code, message="Offer withdrawn successfully.", details=response.text or None)
                ).model_dump_json(indent=2)

            # --- PUBLISH Action --- 
            elif params.action == ManageOfferAction.PUBLISH:
                if not offer_id_from_current:
                    raise ValueError("Missing offer_id for publish action.") # Should be caught

                url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id_from_current}/publish"
                logger.debug(f"manage_offer (PUBLISH): URL: {url}")
                response = await client.post(url, headers=headers, json={}) # Empty JSON body for publish
                response.raise_for_status() # Expect 200 OK with listingId in body
                response_json = response.json() if response.text else {}
                listing_id = response_json.get('listingId')
                logger.info(f"manage_offer (PUBLISH): Successfully published offer '{offer_id_from_current}' for SKU '{params.sku}'. ListingId: {listing_id}")
                return ManageOfferToolResponse.success_response(
                    ManageOfferResponseDetails(offer_id=offer_id_from_current, status_code=response.status_code, message=f"Offer published successfully. ListingId: {listing_id}", details=response_json)
                ).model_dump_json(indent=2)

            # --- GET Action ---
            elif params.action == ManageOfferAction.GET:
                if not current_offer: # Should be caught by the check at the top of the function
                    raise ValueError(f"No offer found for SKU '{params.sku}'.")

                offer_id = current_offer.get('offerId')
                logger.info(f"manage_offer (GET): Successfully retrieved offer '{offer_id}' for SKU '{params.sku}'.")
                
                # The user wants the output to be like an OfferDataForManage payload.
                # We return the full offer dictionary from the API in the 'details' field.
                return ManageOfferToolResponse.success_response(
                    ManageOfferResponseDetails(
                        offer_id=offer_id,
                        status_code=200, # Assuming 200 OK as we have the offer
                        message=f"Offer details for SKU '{params.sku}' retrieved successfully.",
                        details=current_offer
                    )
                ).model_dump_json(indent=2)
            
            else:
                # Should not happen due to Enum validation
                raise ValueError(f"Unhandled action: {params.action.value}")

        try:
            async with create_debug_client() as client:
                # The execute_ebay_api_call handles token acquisition and basic error wrapping
                # It expects _api_call_logic to return the final JSON string or raise an error
                result_str = await execute_ebay_api_call(f"manage_offer_{params.action.value}", client, _api_call_logic)
                return result_str # result_str is already a JSON string from _api_call_logic
        except ValueError as ve: # Catch specific validation/logic errors from _api_call_logic
            logger.error(f"ValueError in manage_offer ({params.action.value}) for SKU '{params.sku}': {ve}")
            return ManageOfferToolResponse.error_response(str(ve)).model_dump_json(indent=2)
        except httpx.HTTPStatusError as hse:
            logger.error(f"HTTPStatusError in manage_offer ({params.action.value}) for SKU '{params.sku}': {hse.response.status_code} - {hse.response.text[:500]}")
            error_details = hse.response.text
            try:
                error_json = hse.response.json()
                error_details = error_json.get('errors', [{}])[0].get('message', hse.response.text)
            except Exception:
                pass # Keep raw text if not JSON
            return ManageOfferToolResponse.error_response(f"eBay API Error ({hse.response.status_code}): {error_details}").model_dump_json(indent=2)
        except Exception as e:
            logger.exception(f"Unexpected error in manage_offer ({params.action.value}) for SKU '{params.sku}': {e}")
            return ManageOfferToolResponse.error_response(f"Unexpected error: {str(e)}").model_dump_json(indent=2)
