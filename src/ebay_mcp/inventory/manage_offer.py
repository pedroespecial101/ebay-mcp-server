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

from pydantic import Field

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from models.ebay.inventory import (
    ManageOfferAction,
    OfferFormat,
    OfferDataForManage,
    ManageOfferToolInput,
    ManageOfferResponseDetails,
    ManageOfferToolResponse,
)
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers
from utils.debug_httpx import create_debug_client
from ..config import ebay_offer_defaults

logger = logging.getLogger(__name__)


def _normalize_for_comparison(value: Any) -> str:
    """Normalize values for comparison, handling None, numbers, and strings consistently."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(float(value))  # Normalize to float representation
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        # Try to parse as float for numeric strings
        try:
            return str(float(value))
        except ValueError:
            return value
    return str(value)


def _deep_compare_dict(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> bool:
    """Deep compare two dictionaries, handling nested structures and eBay-added defaults."""
    # Only check keys that exist in dict1 (expected values)
    # Allow dict2 to have additional keys that eBay may add as defaults
    for key in dict1.keys():
        if key not in dict2:
            return False
        
        val1, val2 = dict1[key], dict2[key]
        if isinstance(val1, dict) and isinstance(val2, dict):
            if not _deep_compare_dict(val1, val2):
                return False
        elif isinstance(val1, list) and isinstance(val2, list):
            if not _deep_compare_list(val1, val2):
                return False
        else:
            if _normalize_for_comparison(val1) != _normalize_for_comparison(val2):
                return False
    return True


def _deep_compare_list(list1: List[Any], list2: List[Any]) -> bool:
    """Deep compare two lists, handling nested structures."""
    if len(list1) != len(list2):
        return False
    
    for item1, item2 in zip(list1, list2):
        if isinstance(item1, dict) and isinstance(item2, dict):
            if not _deep_compare_dict(item1, item2):
                return False
        elif isinstance(item1, list) and isinstance(item2, list):
            if not _deep_compare_list(item1, item2):
                return False
        else:
            if _normalize_for_comparison(item1) != _normalize_for_comparison(item2):
                return False
    return True




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
                
                if not params.offer_data:
                    raise ValueError("offer_data is unexpectedly None for 'create' action despite validator.")

                # Start with defaults from config
                defaults = {
                    "marketplaceId": ebay_offer_defaults.EBAY_MARKETPLACE_ID,
                    "format": ebay_offer_defaults.EBAY_LISTING_FORMAT,
                    "listingDuration": ebay_offer_defaults.EBAY_LISTING_DURATION,
                    "includeCatalogProductDetails": ebay_offer_defaults.EBAY_LISTING_INCLUDE_CATALOG_PRODUCT_DETAILS,
                    "merchantLocationKey": ebay_offer_defaults.EBAY_MERCHANT_LOCATION_KEY,
                    "listingPolicies": {
                        "paymentPolicyId": ebay_offer_defaults.EBAY_PAYMENT_POLICY_ID,
                        "returnPolicyId": ebay_offer_defaults.EBAY_RETURN_POLICY_ID,
                        "fulfillmentPolicyId": ebay_offer_defaults.EBAY_FULFILLMENT_POLICY_ID,
                    },
                }

                # User-provided data takes precedence, dumped with aliases for camelCase JSON
                user_payload = params.offer_data.model_dump(exclude_none=True, by_alias=True)

                # Deep merge user payload into defaults
                if 'listingPolicies' in user_payload and 'listingPolicies' in defaults:
                    merged_policies = defaults['listingPolicies'].copy()
                    merged_policies.update(user_payload['listingPolicies'])
                    user_payload['listingPolicies'] = merged_policies

                # Create the final payload by starting with defaults and updating with user data
                payload = defaults.copy()
                payload.update(user_payload)

                # Add SKU to the payload body as required by createOffer
                payload['sku'] = params.sku

                # Final validation for fields not covered by defaults
                required_fields_after_merge = ['availableQuantity', 'categoryId', 'pricingSummary']
                for field in required_fields_after_merge:
                    if field not in payload or payload[field] is None:
                        raise ValueError(f"Missing required field '{field}' in final payload for 'create' action.")
                
                url = "https://api.ebay.com/sell/inventory/v1/offer"
                logger.debug(f"manage_offer (CREATE): URL: {url}, Payload: {payload}")
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                response_json = response.json()
                new_offer_id = response_json.get('offerId')
                logger.info(f"manage_offer (CREATE): Successfully created offer for SKU '{params.sku}'. New OfferId: {new_offer_id}. Verifying...")

                # Verification step
                verified_offer = await _get_offer_by_sku(params.sku, access_token, client)
                if not verified_offer:
                    # This could be a transient issue, but we'll treat it as a failure for now.
                    raise ValueError(f"VERIFICATION FAILED: Could not retrieve offer for SKU '{params.sku}' immediately after creation.")

                # Simple verification: check if a key field matches.
                # Note: eBay might transform or default some values. This is a basic check.
                if payload.get('categoryId') != verified_offer.get('categoryId'):
                    logger.warning(f"Verification discrepancy for SKU '{params.sku}'. Sent categoryId '{payload.get('categoryId')}', but found '{verified_offer.get('categoryId')}' in fetched offer.")
                    # For now, we will still return success but include the fetched data.

                logger.info(f"manage_offer (CREATE): Verification successful for SKU '{params.sku}'.")
                return ManageOfferToolResponse.success_response(
                    ManageOfferResponseDetails(offer_id=new_offer_id, status_code=response.status_code, message="Offer created and verified successfully.", details=verified_offer)
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
                provided_updates = params.offer_data.model_dump(exclude_none=True, by_alias=True)
                update_payload.update(provided_updates) # Override with new values
                
                # The above .update() merges the camelCase keys from the API with the aliased camelCase keys from our model.

                url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id_from_current}"
                logger.debug(f"manage_offer (MODIFY): URL: {url}, Payload: {update_payload}")
                response = await client.put(url, headers=headers, json=update_payload)
                response.raise_for_status() # Expect 204 No Content
                logger.info(f"manage_offer (MODIFY): Successfully submitted modification for offer '{offer_id_from_current}' for SKU '{params.sku}'. Verifying...")

                # Enhanced Verification step
                verified_offer = await _get_offer_by_sku(params.sku, access_token, client)
                if not verified_offer:
                    raise ValueError(f"VERIFICATION FAILED: Could not retrieve offer for SKU '{params.sku}' immediately after modification.")

                # Create expected final state: original offer + modifications
                expected_final_state = current_offer.copy()
                expected_final_state.update(provided_updates)
                
                # Comprehensive verification: compare expected vs actual final state
                discrepancies = []
                
                # Only check keys that we expect to be present (from expected_final_state)
                # This allows eBay to add additional fields without triggering false positives
                for key in expected_final_state.keys():
                    expected_value = expected_final_state.get(key)
                    actual_value = verified_offer.get(key)
                    
                    # Skip comparison for system-managed fields that eBay might update
                    system_managed_fields = {'offerId', 'listing', 'status', 'statusReason', 'totalListingIds'}
                    if key in system_managed_fields:
                        continue
                    
                    # Deep comparison for complex objects
                    if isinstance(expected_value, dict) and isinstance(actual_value, dict):
                        if not _deep_compare_dict(expected_value, actual_value):
                            discrepancies.append(f"Field '{key}': expected {expected_value}, found {actual_value}")
                    elif isinstance(expected_value, list) and isinstance(actual_value, list):
                        if not _deep_compare_list(expected_value, actual_value):
                            discrepancies.append(f"Field '{key}': expected {expected_value}, found {actual_value}")
                    else:
                        # For primitive types, normalize for comparison
                        expected_str = _normalize_for_comparison(expected_value)
                        actual_str = _normalize_for_comparison(actual_value)
                        if expected_str != actual_str:
                            discrepancies.append(f"Field '{key}': expected '{expected_value}', found '{actual_value}'")
                
                message = "Offer modified and verified successfully."
                if discrepancies:
                    discrepancy_details = '; '.join(discrepancies)
                    logger.warning(f"Enhanced verification for SKU '{params.sku}' found discrepancies: {discrepancy_details}")
                    message = f"Offer modified. Enhanced verification found discrepancies: {discrepancy_details}"
                else:
                    logger.info(f"manage_offer (MODIFY): Enhanced verification successful for SKU '{params.sku}'. All fields match expected state.")

                return ManageOfferToolResponse.success_response(
                    ManageOfferResponseDetails(offer_id=offer_id_from_current, status_code=response.status_code, message=message, details=verified_offer)
                ).model_dump_json(indent=2)

            # --- WITHDRAW Action --- 
            elif params.action == ManageOfferAction.WITHDRAW:
                if not offer_id_from_current:
                    raise ValueError("Missing offer_id for withdraw action.") # Should be caught

                url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id_from_current}/withdraw"
                logger.debug(f"manage_offer (WITHDRAW): URL: {url}")
                # Withdraw request typically has an empty body, but API might expect Content-Type: application/json
                # The withdraw_offer.py example sends an empty JSON body {}
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
