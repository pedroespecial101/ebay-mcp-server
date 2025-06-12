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

from pydantic import BaseModel, Field, model_validator

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from models.base import EbayBaseModel, EbayResponse
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


class ManageInventoryItemAction(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    GET = "get"
    DELETE = "delete"


# ---------------------------------------------------------------------------
# NESTED MODELS FOR INVENTORY ITEM PAYLOAD (limited-field version)
# ---------------------------------------------------------------------------

class ShipToLocationAvailability(EbayBaseModel):
    """Quantity available for ship-to-home orders.
    Based on the Inventory API docs – this container specifies how many items can
    be purchased on the marketplace. "quantity" must be a non-negative integer.
    """
    quantity: int = Field(
        ...,
        ge=0,
        title="Available Quantity",
        description=(
            "Total purchasable quantity of the inventory item for ship-to-home "
            "fulfilment. Must be greater than or equal to 0."
        ),
        examples=[10],
    )


class AvailabilityData(EbayBaseModel):
    """Top-level availability container (limited to shipToLocationAvailability)."""

    shipToLocationAvailability: ShipToLocationAvailability = Field(
        ...,
        title="Ship-To-Location Availability",
        description="Container for quantity available for domestic fulfilment instructions.",
    )


class ProductDataForInventoryItem(EbayBaseModel):
    """Product details container (limited-field version).
    The structure follows the Create/Replace Inventory Item schema but only
    exposes the keys required/allowed by InventoryItemRequired_Limited.json.
    """

    title: str = Field(
        ...,
        max_length=80,
        title="Title",
        description="Title of the item exactly as it will appear on the eBay listing (max 80 characters).",
        examples=["Apple iPhone 15 Pro 256GB Natural Titanium"],
    )
    description: str = Field(
        ...,
        max_length=4000,
        title="Description",
        description="Full description of the product or lot in HTML or plain text (max 4000 characters).",
    )
    aspects: Optional[Dict[str, List[str]]] = Field(
        None,
        title="Aspects",
        description="Dictionary mapping aspect names (e.g. Colour, Size) to arrays of values. Must match category-specific allowed aspect names. Use the get_item_aspects_for_category MCP tool to retrieve the allowed and required aspect names for a specific category.",
        examples=[{"Colour": ["Black"], "Size": ["XL"]}],
    )
    brand: Optional[str] = Field(
        None,
        title="Brand",
        description="Brand or manufacturer of the item. If you know this, you can provide it, otherwise leave it out.",
        examples=["Apple"],
    )
    mpn: Optional[str] = Field(
        None,
        title="Manufacturer Part Number (MPN)",
        description="Manufacturer Part Number identifying the product.",
    )
    ean: Optional[List[str]] = Field(
        None,
        title="EAN List",
        description="Array of European Article Numbers associated with the product.",
        examples=[["190199098702"]],
    )
    upc: Optional[List[str]] = Field(
        None,
        title="UPC List",
        description="Array of Universal Product Codes associated with the product.",
        examples=[["190199098719"]],
    )
    isbn: Optional[List[str]] = Field(
        None,
        title="ISBN List",
        description="Array of International Standard Book Numbers associated with the product (books/media only).",
    )
    imageUrls: Optional[List[str]] = Field(
        None,
        title="Image URLs",
        description="Array of fully-qualified image URLs. First image is treated as the primary gallery image. If no image is provided use https://ebayimages.s3.us-east-005.backblazeb2.com/ebay_images/awaiting_image_holding.png. Warn the user that this image will be used if no image is provided.",
        examples=[
            [
                "https://example.com/image1.jpg",
                "https://example.com/image2.jpg",
                "https://example.com/image3.jpg",
            ]
        ],
    )

    class Config:
        allow_population_by_field_name = True


# ---------------------------------------------------------------------------
# MAIN DATA MODEL (limited-field version)
# ---------------------------------------------------------------------------

class ConditionEnum(str, Enum):
    """Enumeration of eBay item conditions.

    The numeric values correspond to eBay *conditionId*s used across the
    Inventory, Browse and Trading APIs.

    Source: `_archive/eBayConditionEnums.md`.

    | Name                       | ID   | Notes |
    |----------------------------|------|-------|
    | NEW                        | 1000 | Brand-new, unopened item in original packaging |
    | LIKE_NEW                   | 2750 | Opened but very lightly used (e.g. books/DVDs). For trading cards: *Graded* |
    | NEW_OTHER                  | 1500 | New, unused but may be missing original packaging or not sealed |
    | NEW_WITH_DEFECTS           | 1750 | New, unused but has defects (e.g. scuffs, missing buttons) |
    | USED_EXCELLENT             | 3000 | Used but in excellent condition. For apparel: *Pre-owned – Good* |
    | USED_VERY_GOOD             | 4000 | Used but in very good condition. For trading cards: *Ungraded* |
    | USED_GOOD                  | 5000 | Used but in good condition |
    | USED_ACCEPTABLE            | 6000 | Acceptable condition |
    | FOR_PARTS_OR_NOT_WORKING   | 7000 | Not fully functioning; suitable for repair or parts |
    | PRE_OWNED_EXCELLENT        | 2990 | Apparel categories only |
    | PRE_OWNED_FAIR             | 3010 | Apparel categories only |
    """

    NEW = "NEW"
    LIKE_NEW = "LIKE_NEW"
    NEW_OTHER = "NEW_OTHER"
    NEW_WITH_DEFECTS = "NEW_WITH_DEFECTS"
    USED_EXCELLENT = "USED_EXCELLENT"
    USED_VERY_GOOD = "USED_VERY_GOOD"
    USED_GOOD = "USED_GOOD"
    USED_ACCEPTABLE = "USED_ACCEPTABLE"
    FOR_PARTS_OR_NOT_WORKING = "FOR_PARTS_OR_NOT_WORKING"
    PRE_OWNED_EXCELLENT = "PRE_OWNED_EXCELLENT"
    PRE_OWNED_FAIR = "PRE_OWNED_FAIR"

class InventoryItemDataForManage(EbayBaseModel):
    """Data payload for creating or modifying an inventory item.

    This limited-field version only includes the keys defined in
    `_archive/InventoryItemRequired_Limited.json`, but each is richly decorated
    with field metadata sourced from the *eBay Sell Inventory v1 API Overview*.
    """

    product: Optional[ProductDataForInventoryItem] = Field(
        None,
        title="Product Details",
        description="Container for title, description, identifiers and images of the product.",
    )
    condition: Optional[ConditionEnum] = Field(
        None,
        title="Condition",
        description=(
            "Enumeration value indicating the condition of the item. Must be one of "
            "the values in the Inventory API ConditionEnum (e.g. NEW, USED_GOOD, "
            "MANUFACTURER_REFURBISHED)."
        ),
        examples=[ConditionEnum.NEW, ConditionEnum.USED_GOOD],
    )
    conditionDescription: Optional[str] = Field(
        None,
        title="Condition Description",
        description=(
            "More detailed, human-readable condition notes. Allowed for all "
            "conditions other than brand-new. Ignored by eBay if provided with a "
            "new condition."
        ),
    )
    availability: Optional[AvailabilityData] = Field(
        None,
        title="Availability",
        description="Container defining quantity available for purchase.",
    )

    class Config:
        allow_population_by_field_name = True


# This model will be used by FastMCP for schema generation and input validation
class ManageInventoryItemToolInput(EbayBaseModel):
    sku: str = Field(..., description="Inventory item SKU.", max_length=50)
    action: ManageInventoryItemAction = Field(..., description="Action to perform on the inventory item ('create', 'modify', 'get', 'delete').")
    item_data: Optional[InventoryItemDataForManage] = Field(None, description="Data for create/modify actions. See InventoryItemDataForManage schema.")

    @model_validator(mode='after')
    def check_item_data_for_action(self):
        action = self.action
        item_data = self.item_data
        if action in [ManageInventoryItemAction.CREATE, ManageInventoryItemAction.MODIFY] and item_data is None:
            raise ValueError("item_data is required for 'create' or 'modify' actions.")
        if action in [ManageInventoryItemAction.GET, ManageInventoryItemAction.DELETE] and item_data is not None:
            # For get/delete, we could also choose to silently ignore item_data if provided.
            # However, raising an error is stricter and makes the API contract clearer.
            raise ValueError(f"item_data must NOT be provided for '{action.value}' action.")
        return self


class ManageInventoryItemResponseDetails(EbayBaseModel):
    sku: Optional[str] = None
    status_code: Optional[int] = None
    message: str
    details: Optional[Any] = None # To store raw response from eBay if needed


class ManageInventoryItemToolResponse(EbayResponse[ManageInventoryItemResponseDetails]):
    pass


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
                
                # Specific field requirements for 'create' action within item_data
                required_fields_create = ['condition', 'product', 'availability']
                for field in required_fields_create:
                    if getattr(params.item_data, field, None) is None:
                        raise ValueError(f"Missing required field '{field}' in item_data for 'create' action.")

                product_model = params.item_data.product
                if not product_model:
                    raise ValueError("product must be supplied for 'create' action.")

                # Convert to dict for simple key checks
                product_dict = (
                    product_model.model_dump(exclude_none=True)
                    if hasattr(product_model, "model_dump")
                    else product_model
                )

                product_required_fields = ['title', 'description']
                for field in product_required_fields:
                    if not product_dict.get(field):
                        raise ValueError(
                            f"Missing required product field '{field}' in item_data for 'create' action."
                        )
                 
                availability_model = params.item_data.availability
                if not availability_model:
                    raise ValueError("availability must be provided for 'create' action.")

                avail_dict = (
                    availability_model.model_dump(exclude_none=True)
                    if hasattr(availability_model, "model_dump")
                    else availability_model
                )

                ship_to_location = avail_dict.get('shipToLocationAvailability')
                if not ship_to_location or ship_to_location.get('quantity') is None:
                    raise ValueError(
                        "availability.shipToLocationAvailability.quantity is required for 'create' action."
                    )

                payload = params.item_data.model_dump(exclude_none=True)
                
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
                provided_updates = params.item_data.model_dump(exclude_none=True)
                update_payload.update(provided_updates) # Override with new values
                
                # Remove eBay-managed fields that shouldn't be sent in updates
                ebay_managed_fields = ['sku', 'locale', 'groupIds']
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