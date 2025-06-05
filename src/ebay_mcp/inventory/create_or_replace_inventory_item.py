"""
eBay Inventory MCP Server - Create or Replace Inventory Item Functionality
"""
import logging
import os
import sys
import httpx
from fastmcp import FastMCP
import json
from typing import Any, Dict, List, Optional

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import inventory-related models
from models.ebay.inventory import CreateOrReplaceInventoryItemRequest, CreateOrReplaceInventoryItemResponse
from models.mcp_tools import CreateOrReplaceInventoryItemParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, is_token_error
from utils.debug_httpx import create_debug_client

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def create_or_replace_inventory_item_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def create_or_replace_inventory_item(
        sku: str,
        condition: str,
        product_title: str,
        product_description: str,
        quantity: int = 1,
        product_aspects: Optional[Dict[str, Any]] = None,
        product_imageUrls: Optional[List[str]] = None,
        product_brand: Optional[str] = None,
        product_mpn: Optional[str] = None,
        product_ean: Optional[List[str]] = None,
        product_upc: Optional[List[str]] = None,
        product_isbn: Optional[List[str]] = None,
        product_epid: Optional[str] = None,
        product_subtitle: Optional[str] = None,
        product_videoIds: Optional[List[str]] = None,
        condition_description: Optional[str] = None,
        condition_descriptors: Optional[List[Dict[str, Any]]] = None,
        package_weight_value: Optional[float] = None,
        package_weight_unit: Optional[str] = None,
        package_dimensions_length: Optional[float] = None,
        package_dimensions_width: Optional[float] = None,
        package_dimensions_height: Optional[float] = None,
        package_dimensions_unit: Optional[str] = None,
        package_type: Optional[str] = None,
        package_shipping_irregular: Optional[bool] = None,
        availability_distributions: Optional[List[Dict[str, Any]]] = None,
        pickup_availability: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Create or replace an inventory item using the eBay Sell Inventory API.
        
        This tool creates a new inventory item or replaces an existing one with the specified SKU.
        The API will return 201 for new items and 204 for updated items.
        
        Args:
            sku: The seller-defined SKU (Stock Keeping Unit) of the inventory item (max 50 characters).
            condition: The condition of the inventory item (e.g., NEW, USED_EXCELLENT, etc.).
            product_title: The title of the product (required).
            product_description: The description of the product (required).
            quantity: The quantity available for the inventory item (default: 1).
            product_aspects: Product aspects as key-value pairs (optional).
            product_imageUrls: List of image URLs for the product (optional).
            product_brand: The brand of the product (optional).
            product_mpn: The manufacturer part number (optional).
            product_ean: List of EAN codes (optional).
            product_upc: List of UPC codes (optional).
            product_isbn: List of ISBN codes (optional).
            product_epid: The eBay product identifier (optional).
            product_subtitle: The subtitle of the product (optional).
            product_videoIds: List of video IDs for the product (optional).
            condition_description: Additional description of the item condition (optional).
            condition_descriptors: List of condition descriptors (optional).
            package_weight_value: The weight value of the package (optional).
            package_weight_unit: The weight unit (POUND, KILOGRAM, OUNCE, GRAM) (optional).
            package_dimensions_length: The length of the package (optional).
            package_dimensions_width: The width of the package (optional).
            package_dimensions_height: The height of the package (optional).
            package_dimensions_unit: The dimension unit (INCH, FEET, CENTIMETER, METER) (optional).
            package_type: The package type (optional).
            package_shipping_irregular: Whether the package has irregular shipping (optional).
            availability_distributions: Availability distributions (optional).
            pickup_availability: Pickup availability information (optional).
        """
        logger.info(f"Executing create_or_replace_inventory_item MCP tool with SKU='{sku}'.")
        
        # Validate parameters using Pydantic model
        try:
            params = CreateOrReplaceInventoryItemParams(
                sku=sku,
                condition=condition,
                product_title=product_title,
                product_description=product_description,
                quantity=quantity,
                product_aspects=product_aspects,
                product_imageUrls=product_imageUrls,
                product_brand=product_brand,
                product_mpn=product_mpn,
                product_ean=product_ean,
                product_upc=product_upc,
                product_isbn=product_isbn,
                product_epid=product_epid,
                product_subtitle=product_subtitle,
                product_videoIds=product_videoIds,
                condition_description=condition_description,
                condition_descriptors=condition_descriptors,
                package_weight_value=package_weight_value,
                package_weight_unit=package_weight_unit,
                package_dimensions_length=package_dimensions_length,
                package_dimensions_width=package_dimensions_width,
                package_dimensions_height=package_dimensions_height,
                package_dimensions_unit=package_dimensions_unit,
                package_type=package_type,
                package_shipping_irregular=package_shipping_irregular,
                availability_distributions=availability_distributions,
                pickup_availability=pickup_availability
            )
            
            # Create request model from validated parameters
            request_data = CreateOrReplaceInventoryItemRequest.from_params(params)
            
            async def _api_call(access_token: str, client: httpx.AsyncClient):
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
                    "Content-Language": "en-US",
                }
                
                # Build the API URL with SKU as path parameter
                base_url = "https://api.ebay.com/sell/inventory/v1/inventory_item"
                url = f"{base_url}/{params.sku}"
                
                log_headers = headers.copy()
                log_headers['Authorization'] = f"Bearer {access_token[:20]}...<truncated>"
                logger.debug(f"create_or_replace_inventory_item: Headers for API call: {log_headers}")
                logger.debug(f"create_or_replace_inventory_item: Request URL: {url}")
                logger.debug(f"create_or_replace_inventory_item: Request body: {request_data.model_dump(exclude_none=True)}")
                
                # Make the PUT request
                response = await client.put(
                    url,
                    headers=headers,
                    json=request_data.model_dump(exclude_none=True)
                )
                
                logger.debug(f"create_or_replace_inventory_item: Response status: {response.status_code}")
                logger.debug(f"create_or_replace_inventory_item: Response headers: {dict(response.headers)}")
                
                # Handle successful responses (201 for created, 204 for updated)
                if response.status_code in [201, 204]:
                    logger.info(f"create_or_replace_inventory_item: Successfully processed inventory item with SKU '{params.sku}' (status: {response.status_code})")
                    
                    # Create success response
                    success_response = CreateOrReplaceInventoryItemResponse.success_response(
                        sku=params.sku,
                        status_code=response.status_code
                    )
                    return success_response.model_dump_json(indent=2)
                else:
                    # Raise HTTPStatusError for non-success status codes
                    response.raise_for_status()
                    
            # Execute the API call using the common utility
            async with create_debug_client() as client:
                result = await execute_ebay_api_call(
                    tool_name="create_or_replace_inventory_item",
                    client=client,
                    api_call_logic=_api_call
                )
                
            return result
            
        except Exception as e:
            logger.error(f"Error in create_or_replace_inventory_item: {str(e)}")
            error_response = CreateOrReplaceInventoryItemResponse.error_response(
                error_message=str(e),
                sku=sku if 'sku' in locals() else None
            )
            return error_response.model_dump_json(indent=2)
