"""
eBay Inventory MCP Server - Update Offer Functionality
"""
import logging
import os
import sys
import httpx

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import inventory-related models
from models.ebay.inventory import UpdateOfferRequest
from models.mcp_tools import UpdateOfferParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers

# Get logger
logger = logging.getLogger(__name__)

# Create a function to be imported by the inventory server
async def update_offer_tool(inventory_mcp):
    @inventory_mcp.tool()
    async def update_offer(
        offer_id: str,
        sku: str = None,
        marketplace_id: str = None,
        available_quantity: int = None,
        pricing_summary: dict = None,
        category_id: str = None,
        listing_description: str = None,
        listing_duration: str = None,
        listing_start_date: str = None,
        merchant_location_key: str = None,
        listing_policies: dict = None,
        secondary_category_id: str = None,
        store_category_names: list = None,
        quantity_limit_per_buyer: int = None,
        lot_size: int = None,
        hide_buyer_details: bool = None,
        include_catalog_product_details: bool = None,
        charity: dict = None,
        extended_producer_responsibility: dict = None,
        regulatory: dict = None,
        tax: dict = None,
        # Legacy parameter for backward compatibility
        price: float = None
    ) -> str:
        """Update an existing eBay offer with comprehensive field support.

        ⚠️  CRITICAL WARNING: This is a REPLACE operation! ⚠️

        The updateOffer API call performs a COMPLETE REPLACEMENT of the existing offer object.
        ALL current offer data will be overwritten with the provided values. Any fields not
        included in the update request will be cleared/reset to defaults.

        RECOMMENDED WORKFLOW:
        1. First call the Get Offer tool to retrieve current offer data
        2. Modify only the desired fields while preserving all other existing values
        3. Include ALL existing field values in the update request to prevent data loss

        Args:
            offer_id: The unique identifier of the offer to update (REQUIRED)
            sku: The seller-defined SKU. Max 50 chars. Required if not set in current offer.
            marketplace_id: eBay marketplace ID (e.g., EBAY_US, EBAY_GB). Required if not set.
            available_quantity: Quantity available for purchase. Must be 1+ for purchasable items.
            pricing_summary: Pricing container with price, MAP, strikethrough pricing. Required for published offers.
            category_id: Primary eBay category ID. Required before publishing.
            listing_description: Listing description (supports HTML). Required for published offers. Max 500,000 chars.
            listing_duration: Listing duration ('GTC' for fixed-price). Required before publishing.
            listing_start_date: Scheduled start time in UTC (YYYY-MM-DDTHH:MM:SSZ). Optional.
            merchant_location_key: Merchant inventory location ID. Required before publishing. Max 36 chars.
            listing_policies: Business policies (payment, return, fulfillment). Required for published offers.
            secondary_category_id: Secondary category ID for dual-category listings. Optional.
            store_category_names: eBay store category paths. Max 2. Format: ['/Category/Subcategory'].
            quantity_limit_per_buyer: Max quantity per buyer across transactions. Must be 1+.
            lot_size: Number of items in lot listing. For multi-item lots only.
            hide_buyer_details: True for private listings (obfuscated buyer IDs).
            include_catalog_product_details: Apply eBay catalog details. Defaults to true.
            charity: Charitable organization container with charityId and donationPercentage.
            extended_producer_responsibility: Eco-participation fee container. Required in some markets.
            regulatory: Regulatory information and compliance documents.
            tax: Tax configuration (sales tax, VAT, exceptions).
            price: Legacy parameter - use pricing_summary instead. Will be converted to pricing_summary format.

        Returns:
            Success message or error details.
        """
        logger.info(f"Executing update_offer MCP tool with offer_id='{offer_id}'")

        # Handle legacy price parameter by converting to pricing_summary
        if price is not None and pricing_summary is None:
            logger.info("Converting legacy price parameter to pricing_summary format")
            pricing_summary = {
                "price": {
                    "currency": "GBP",  # Default currency, will be updated from current offer
                    "value": str(price)
                }
            }

        # Validate parameters using Pydantic model
        try:
            params = UpdateOfferParams(
                offer_id=offer_id,
                sku=sku,
                marketplace_id=marketplace_id,
                available_quantity=available_quantity,
                pricing_summary=pricing_summary,
                category_id=category_id,
                listing_description=listing_description,
                listing_duration=listing_duration,
                listing_start_date=listing_start_date,
                merchant_location_key=merchant_location_key,
                listing_policies=listing_policies,
                secondary_category_id=secondary_category_id,
                store_category_names=store_category_names,
                quantity_limit_per_buyer=quantity_limit_per_buyer,
                lot_size=lot_size,
                hide_buyer_details=hide_buyer_details,
                include_catalog_product_details=include_catalog_product_details,
                charity=charity,
                extended_producer_responsibility=extended_producer_responsibility,
                regulatory=regulatory,
                tax=tax
            )

            # Count non-None parameters to check if any updates are specified
            update_fields = [
                params.sku, params.marketplace_id, params.available_quantity, params.pricing_summary,
                params.category_id, params.listing_description, params.listing_duration,
                params.listing_start_date, params.merchant_location_key, params.listing_policies,
                params.secondary_category_id, params.store_category_names, params.quantity_limit_per_buyer,
                params.lot_size, params.hide_buyer_details, params.include_catalog_product_details,
                params.charity, params.extended_producer_responsibility, params.regulatory, params.tax
            ]

            if all(field is None for field in update_fields):
                return "Error: At least one field must be specified for update. This is a REPLACE operation - provide ALL current values to preserve existing data."

            async def _api_call(access_token: str, client: httpx.AsyncClient):
                # Use standardized eBay API headers (includes Content-Language and Accept-Language)
                headers = get_standard_ebay_headers(access_token)
                
                # First, get the current offer details to ensure we have all required fields
                get_url = f"https://api.ebay.com/sell/inventory/v1/offer/{params.offer_id}"
                logger.debug(f"update_offer: Getting current offer details from: {get_url}")
                
                get_response = await client.get(get_url, headers=headers)
                get_response.raise_for_status()  # This will be caught by _execute_ebay_api_call if there's an error
                
                current_offer = get_response.json()
                logger.debug(f"update_offer: Successfully retrieved current offer details")

                # Build comprehensive update request, preserving current values where new ones aren't provided
                update_request_data = {
                    "offer_id": params.offer_id,
                    # Core fields - use provided values or preserve current ones
                    "sku": params.sku if params.sku is not None else current_offer.get('sku'),
                    "marketplace_id": params.marketplace_id if params.marketplace_id is not None else current_offer.get('marketplaceId', 'EBAY_GB'),
                    "format": current_offer.get('format', 'FIXED_PRICE'),  # Preserve format from current offer

                    # Inventory and availability
                    "available_quantity": params.available_quantity if params.available_quantity is not None else current_offer.get('availableQuantity'),

                    # Pricing - handle both new pricing_summary and legacy price conversion
                    "pricing_summary": params.pricing_summary if params.pricing_summary is not None else current_offer.get('pricingSummary'),

                    # Categories
                    "category_id": params.category_id if params.category_id is not None else current_offer.get('categoryId'),
                    "secondary_category_id": params.secondary_category_id if params.secondary_category_id is not None else current_offer.get('secondaryCategoryId'),

                    # Listing content
                    "listing_description": params.listing_description if params.listing_description is not None else current_offer.get('listingDescription'),
                    "listing_duration": params.listing_duration if params.listing_duration is not None else current_offer.get('listingDuration'),
                    "listing_start_date": params.listing_start_date if params.listing_start_date is not None else current_offer.get('listingStartDate'),

                    # Location and policies
                    "merchant_location_key": params.merchant_location_key if params.merchant_location_key is not None else current_offer.get('merchantLocationKey'),
                    "listing_policies": params.listing_policies if params.listing_policies is not None else current_offer.get('listingPolicies'),

                    # Store integration
                    "store_category_names": params.store_category_names if params.store_category_names is not None else current_offer.get('storeCategoryNames'),

                    # Purchase restrictions and features
                    "quantity_limit_per_buyer": params.quantity_limit_per_buyer if params.quantity_limit_per_buyer is not None else current_offer.get('quantityLimitPerBuyer'),
                    "lot_size": params.lot_size if params.lot_size is not None else current_offer.get('lotSize'),
                    "hide_buyer_details": params.hide_buyer_details if params.hide_buyer_details is not None else current_offer.get('hideBuyerDetails'),
                    "include_catalog_product_details": params.include_catalog_product_details if params.include_catalog_product_details is not None else current_offer.get('includeCatalogProductDetails'),

                    # Compliance and special features
                    "charity": params.charity if params.charity is not None else current_offer.get('charity'),
                    "extended_producer_responsibility": params.extended_producer_responsibility if params.extended_producer_responsibility is not None else current_offer.get('extendedProducerResponsibility'),
                    "regulatory": params.regulatory if params.regulatory is not None else current_offer.get('regulatory'),
                    "tax": params.tax if params.tax is not None else current_offer.get('tax'),
                }

                # Create UpdateOfferRequest instance for validation
                update_request = UpdateOfferRequest(**{k: v for k, v in update_request_data.items() if v is not None})

                # Convert to dict for JSON serialization (using model_dump for Pydantic v2)
                update_data = update_request.model_dump(exclude_none=True)
                logger.debug(f"update_offer: Prepared update request data: {update_data}")
                
                # Send update request
                update_url = f"https://api.ebay.com/sell/inventory/v1/offer/{params.offer_id}"
                logger.info(f"update_offer: Sending update request to {update_url}")
                
                # Use data instead of json to avoid httpx adding automatic headers
                import json
                update_response = await client.put(update_url, headers=headers, data=json.dumps(update_data))
                update_response.raise_for_status()  # This will be caught by _execute_ebay_api_call if there's an error

                # Count updated fields for success message
                updated_fields = [k for k, v in update_data.items() if k != 'offer_id' and v is not None]

                logger.info(f"update_offer: Successfully updated offer {params.offer_id}")
                return f"Successfully updated offer {params.offer_id}. Updated fields: {', '.join(updated_fields)}. Response: {update_response.text if update_response.text else 'No response body (success)'}"
            
            async with httpx.AsyncClient() as client:
                result = await execute_ebay_api_call("update_offer", client, _api_call)
                return result
        except Exception as e:
            logger.error(f"Error in update_offer: {str(e)}")
            return f"Error updating offer: {str(e)}"
