"""
eBay Inventory MCP Server - Manage Inventory Item Functionality (Create, Modify, Get, Delete)
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
    ShipToLocationAvailability,
    AvailabilityData,
    ProductDataForInventoryItem,
    ConditionEnum,
    InventoryItemDataForManage,
    ManageInventoryItemAction,
    ManageInventoryItemToolInput,
    ManageInventoryItemResponseDetails,
    ManageInventoryItemToolResponse,
)
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers
from utils.debug_httpx import create_debug_client

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

async def _get_inventory_item_by_sku(sku: str, access_token: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """Helper to fetch an inventory item by SKU."""
    headers = get_standard_ebay_headers(access_token)
    headers['Accept'] = 'application/json'  # Ensure JSON response
    url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
    logger.info(f"_get_inventory_item_by_sku: Fetching inventory item for SKU '{sku}' from {url}")
    
    response = await client.get(url, headers=headers)
    log_headers = headers.copy()
    log_headers['Authorization'] = f"Bearer {access_token[:20]}...<truncated>"
    logger.debug(f"_get_inventory_item_by_sku: Headers: {log_headers}, URL: {url}")
    logger.debug(f"_get_inventory_item_by_sku: Response status: {response.status_code}, text: {response.text[:500]}...")

    if response.status_code == 200:
        response_data = response.json()
        logger.info(f"_get_inventory_item_by_sku: Found inventory item for SKU '{sku}'")
        return response_data
    elif response.status_code == 404:
        logger.info(f"_get_inventory_item_by_sku: No inventory item found for SKU '{sku}' (404 Not Found).")
        return None
    else:
        logger.error(f"_get_inventory_item_by_sku: Error fetching inventory item for SKU '{sku}'. Status: {response.status_code}, Response: {response.text[:500]}")
        response.raise_for_status()  # Let execute_ebay_api_call's wrapper handle it
        return None  # Should not be reached


async def manage_inventory_item_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def manage_inventory_item(params: ManageInventoryItemToolInput) -> str:
        """Manages eBay inventory items: create, modify, get, or delete based on SKU.

        Uses Pydantic model ManageInventoryItemToolInput for parameters, ensuring schema exposure.
        Args:
            params (ManageInventoryItemToolInput): Container for SKU, action, and conditional item_data.
        """
        # Parameters are now automatically validated by FastMCP against ManageInventoryItemToolInput
        # Access them via params.sku, params.action, params.item_data
        logger.info(f"Executing manage_inventory_item MCP tool: SKU='{params.sku}', Action='{params.action.value}'")

        async def _api_call_logic(access_token: str, client: httpx.AsyncClient): # params is available in this scope
            headers = get_standard_ebay_headers(access_token)
            
            current_item = None

            # For modify, get - first get the item to get current state
            # The 'params' variable from the outer scope (manage_inventory_item function) is used here.
            if params.action in [ManageInventoryItemAction.MODIFY, ManageInventoryItemAction.GET]:
                current_item = await _get_inventory_item_by_sku(params.sku, access_token, client)
                if not current_item:
                    raise ValueError(f"No existing inventory item found for SKU '{params.sku}' to perform '{params.action.value}'.")

            # --- CREATE Action --- 
            if params.action == ManageInventoryItemAction.CREATE:
                existing_item_check = await _get_inventory_item_by_sku(params.sku, access_token, client)
                if existing_item_check:
                    raise ValueError(f"Inventory item for SKU '{params.sku}' already exists. Use 'modify' action to update.")

                # Validation for item_data presence is now handled by ManageInventoryItemToolInput's model_validator
                if not params.item_data:
                    raise ValueError("item_data is unexpectedly None for 'create' action despite validator.")
                
                # --- TEST: Temporarily disabled validation to test minimal API requirements (2025-06-16) ---
                # The following block was commented out to allow sending a create request with only an SKU.
                #
                # # Specific field requirements for 'create' action within item_data
                # required_fields_create = ['condition', 'product', 'availability']
                # for field in required_fields_create:
                #     if getattr(params.item_data, field, None) is None:
                #         raise ValueError(f"Missing required field '{field}' in item_data for 'create' action.")
                #
                # product_model = params.item_data.product
                # if not product_model:
                #     raise ValueError("product must be supplied for 'create' action.")
                #
                # # Convert to dict for simple key checks
                # product_dict = (
                #     product_model.model_dump(exclude_none=True)
                #     if hasattr(product_model, "model_dump")
                #     else product_model
                # )
                #
                # product_required_fields = ['title', 'description']
                # for field in product_required_fields:
                #     if not product_dict.get(field):
                #         raise ValueError(
                #             f"Missing required product field '{field}' in item_data for 'create' action."
                #         )
                #  
                # availability_model = params.item_data.availability
                # if not availability_model:
                #     raise ValueError("availability must be provided for 'create' action.")
                #
                # avail_dict = (
                #     availability_model.model_dump(exclude_none=True)
                #     if hasattr(availability_model, "model_dump")
                #     else availability_model
                # )
                #
                # ship_to_location = avail_dict.get('ship_to_location_availability') # Internal check uses snake_case
                # if not ship_to_location or ship_to_location.get('quantity') is None:
                #     raise ValueError(
                #         "availability.ship_to_location_availability.quantity is required for 'create' action."
                #     )
                # --- END of temporarily disabled validation ---

                payload = params.item_data.model_dump(exclude_none=True, by_alias=True) # API payload needs camelCase
                
                url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{params.sku}"
                logger.debug(f"manage_inventory_item (CREATE): URL: {url}, Payload: {payload}")
                response = await client.put(url, headers=headers, json=payload)
                response.raise_for_status()
                
                logger.info(f"manage_inventory_item (CREATE): Successfully created inventory item for SKU '{params.sku}'. Status: {response.status_code}. Verifying...")

                # Verification step
                verified_item = await _get_inventory_item_by_sku(params.sku, access_token, client)
                if not verified_item:
                    # This could be a transient issue, but we'll treat it as a failure for now.
                    raise ValueError(f"VERIFICATION FAILED: Could not retrieve inventory item for SKU '{params.sku}' immediately after creation.")

                logger.info(f"manage_inventory_item (CREATE): Verification successful for SKU '{params.sku}'.")
                return ManageInventoryItemToolResponse.success_response(
                    ManageInventoryItemResponseDetails(sku=params.sku, status_code=response.status_code, message="Inventory item created and verified successfully.", details=verified_item)
                ).model_dump_json(indent=2)

            # --- MODIFY Action --- 
            elif params.action == ManageInventoryItemAction.MODIFY:
                if not current_item:
                     raise ValueError("Missing current_item details for modify action.") # Should be caught by earlier checks
                if not params.item_data: # Should be caught by validator, but defensive check
                    raise ValueError("item_data is unexpectedly None for 'modify' action.")

                # Merge current_item with new data. eBay's PUT is a full replacement.
                # Start with all fields from current_item, then update with provided non-None fields.
                update_payload = current_item.copy() # Start with all fields from the fetched item
                provided_updates = params.item_data.model_dump(exclude_none=True, by_alias=True) # Get updates with camelCase keys
                update_payload.update(provided_updates) # Override with new values
                
                # Remove eBay-managed fields that shouldn't be sent in updates
                ebay_managed_fields = ['sku', 'locale', 'groupIds'] # These are camelCase as they come from current_item or provided_updates
                for field in ebay_managed_fields:
                    update_payload.pop(field, None)

                url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{params.sku}"
                logger.debug(f"manage_inventory_item (MODIFY): URL: {url}, Payload: {update_payload}")
                response = await client.put(url, headers=headers, json=update_payload)
                response.raise_for_status() # Expect 200 or 204
                logger.info(f"manage_inventory_item (MODIFY): Successfully submitted modification for inventory item '{params.sku}'. Verifying...")

                # Enhanced Verification step
                verified_item = await _get_inventory_item_by_sku(params.sku, access_token, client)
                if not verified_item:
                    raise ValueError(f"VERIFICATION FAILED: Could not retrieve inventory item for SKU '{params.sku}' immediately after modification.")

                # Create expected final state: original item + modifications
                expected_final_state = current_item.copy()
                expected_final_state.update(provided_updates)
                
                # Comprehensive verification: compare expected vs actual final state
                discrepancies = []
                
                # Only check keys that we expect to be present (from expected_final_state)
                # This allows eBay to add additional fields without triggering false positives
                for key in expected_final_state.keys():
                    expected_value = expected_final_state.get(key)
                    actual_value = verified_item.get(key)
                    
                    # Skip comparison for system-managed fields that eBay might update
                    system_managed_fields = {'sku', 'locale', 'groupIds'}
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
                
                message = "Inventory item modified and verified successfully."
                if discrepancies:
                    discrepancy_details = '; '.join(discrepancies)
                    logger.warning(f"Enhanced verification for SKU '{params.sku}' found discrepancies: {discrepancy_details}")
                    message = f"Inventory item modified. Enhanced verification found discrepancies: {discrepancy_details}"
                else:
                    logger.info(f"manage_inventory_item (MODIFY): Enhanced verification successful for SKU '{params.sku}'. All fields match expected state.")

                return ManageInventoryItemToolResponse.success_response(
                    ManageInventoryItemResponseDetails(sku=params.sku, status_code=response.status_code, message=message, details=verified_item)
                ).model_dump_json(indent=2)

            # --- GET Action ---
            elif params.action == ManageInventoryItemAction.GET:
                if not current_item: # Should be caught by the check at the top of the function
                    raise ValueError(f"No inventory item found for SKU '{params.sku}'.")

                logger.info(f"manage_inventory_item (GET): Successfully retrieved inventory item for SKU '{params.sku}'.")
                
                return ManageInventoryItemToolResponse.success_response(
                    ManageInventoryItemResponseDetails(
                        sku=params.sku,
                        status_code=200, # Assuming 200 OK as we have the item
                        message=f"Inventory item details for SKU '{params.sku}' retrieved successfully.",
                        details=current_item
                    )
                ).model_dump_json(indent=2)

            # --- DELETE Action --- 
            elif params.action == ManageInventoryItemAction.DELETE:
                url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{params.sku}"
                logger.debug(f"manage_inventory_item (DELETE): URL: {url}")
                response = await client.delete(url, headers=headers)
                response.raise_for_status() # Expect 204 No Content
                logger.info(f"manage_inventory_item (DELETE): Successfully deleted inventory item for SKU '{params.sku}'.")
                return ManageInventoryItemToolResponse.success_response(
                    ManageInventoryItemResponseDetails(sku=params.sku, status_code=response.status_code, message="Inventory item deleted successfully.", details=None)
                ).model_dump_json(indent=2)
            
            else:
                # Should not happen due to Enum validation
                raise ValueError(f"Unhandled action: {params.action.value}")

        try:
            async with create_debug_client() as client:
                # The execute_ebay_api_call handles token acquisition and basic error wrapping
                # It expects _api_call_logic to return the final JSON string or raise an error
                result_str = await execute_ebay_api_call(f"manage_inventory_item_{params.action.value}", client, _api_call_logic)
                return result_str # result_str is already a JSON string from _api_call_logic
        except ValueError as ve: # Catch specific validation/logic errors from _api_call_logic
            logger.error(f"ValueError in manage_inventory_item ({params.action.value}) for SKU '{params.sku}': {ve}")
            return ManageInventoryItemToolResponse.error_response(str(ve)).model_dump_json(indent=2)
        except httpx.HTTPStatusError as hse:
            logger.error(f"HTTPStatusError in manage_inventory_item ({params.action.value}) for SKU '{params.sku}': {hse.response.status_code} - {hse.response.text[:500]}")
            error_details = hse.response.text
            try:
                error_json = hse.response.json()
                error_details = error_json.get('errors', [{}])[0].get('message', hse.response.text)
            except Exception:
                pass # Keep raw text if not JSON
            return ManageInventoryItemToolResponse.error_response(f"eBay API Error ({hse.response.status_code}): {error_details}").model_dump_json(indent=2)
        except Exception as e:
            logger.exception(f"Unexpected error in manage_inventory_item ({params.action.value}) for SKU '{params.sku}': {e}")
            return ManageInventoryItemToolResponse.error_response(f"Unexpected error: {str(e)}").model_dump_json(indent=2)