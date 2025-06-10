"""
eBay Inventory MCP Server - Update Offer Functionality
"""
import logging
import os
import sys
import httpx
from typing import Optional, Dict, List, Any

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
async def update_offer_safe_tool(inventory_mcp: Any):
    @inventory_mcp.tool()
    async def update_offer_safe(
        offer_id: Optional[str] = None, # Made optional, logic below handles SKU lookup if offer_id is None
        sku: Optional[str] = None,
        marketplace_id: Optional[str] = None,
        available_quantity: Optional[int] = None,
        pricing_summary: Optional[Dict[str, Any]] = None,
        category_id: Optional[str] = None,
        listing_description: Optional[str] = None,
        listing_duration: Optional[str] = None,
        listing_start_date: Optional[str] = None,
        merchant_location_key: Optional[str] = None,
        listing_policies: Optional[Dict[str, Any]] = None,
        secondary_category_id: Optional[str] = None,
        store_category_names: Optional[List[str]] = None,
        quantity_limit_per_buyer: Optional[int] = None,
        lot_size: Optional[int] = None,
        hide_buyer_details: Optional[bool] = None,
        include_catalog_product_details: Optional[bool] = None,
        charity: Optional[Dict[str, Any]] = None,
        extended_producer_responsibility: Optional[Dict[str, Any]] = None,
        regulatory: Optional[Dict[str, Any]] = None,
        tax: Optional[Dict[str, Any]] = None,
        # Legacy parameter for backward compatibility
        price: Optional[float] = None
    ) -> str:
        """Update an existing eBay offer with comprehensive field support.

        This tool performs a "safe" update by first fetching the current offer data,
        merging the provided changes, and then submitting the complete offer object.
        This prevents accidental data loss due to the eBay API's full replacement behavior.

        You MUST provide either 'offer_id' or 'sku' to identify the offer.

        Args:
            offer_id: The unique identifier of the offer. Provide EITHER this OR sku.
            sku: The seller-defined SKU. Provide EITHER this OR offer_id. Max 50 chars.
            marketplace_id: eBay marketplace ID (e.g., EBAY_US, EBAY_GB).
            available_quantity: Quantity available for purchase.
            pricing_summary: Pricing container (price, MAP, strikethrough).
            category_id: Primary eBay category ID.
            listing_description: Listing description (HTML supported). Max 500,000 chars.
            listing_duration: Listing duration ('GTC' for fixed-price).
            listing_start_date: Scheduled start time in UTC (YYYY-MM-DDTHH:MM:SSZ).
            merchant_location_key: Merchant inventory location ID. Max 36 chars.
            listing_policies: Business policies (payment, return, fulfillment).
            secondary_category_id: Secondary category ID for dual-category listings.
            store_category_names: eBay store category paths (max 2).
            quantity_limit_per_buyer: Max quantity per buyer.
            lot_size: Number of items in lot listing.
            hide_buyer_details: True for private listings.
            include_catalog_product_details: Apply eBay catalog details (defaults to true).
            charity: Charitable organization container.
            extended_producer_responsibility: Eco-participation fee container.
            regulatory: Regulatory information and compliance documents.
            tax: Tax configuration.
            price: Legacy parameter - use pricing_summary instead.

        Returns:
            A string indicating success or failure of the offer update.
        """
        logger.info(f"Attempting to safely update offer. Provided Offer ID: {offer_id}, SKU: {sku}")

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
                tax=tax,
                price=price,
            )
        except ValueError as e:
            logger.error(f"Validation error for update_offer_safe: {e}")
            return f"Error: {e}"

        headers = get_standard_ebay_headers(inventory_mcp.ebay_mcp_server.access_token)
        base_url = inventory_mcp.ebay_mcp_server.ebay_api_url
        current_offer = None
        effective_offer_id = params.offer_id # Will be populated by SKU lookup if needed

        async with httpx.AsyncClient() as client:
            try:
                if not params.offer_id and params.sku:
                    # Offer ID not provided, SKU is present. Fetch offer by SKU.
                    marketplace_to_use = params.marketplace_id or inventory_mcp.ebay_mcp_server.default_marketplace_id
                    sku_get_url = f"{base_url}/offer?sku={params.sku}&marketplace_id={marketplace_to_use}"
                    logger.info(
                        f"Offer ID not provided. Fetching offer by SKU: {params.sku} "
                        f"from marketplace {marketplace_to_use} via URL: {sku_get_url}"
                    )
                    get_response = await client.get(sku_get_url, headers=headers)
                    get_response.raise_for_status()
                    sku_offers_data = get_response.json()
                    
                    if sku_offers_data.get("total", 0) == 1 and sku_offers_data.get("offers"):
                        current_offer = sku_offers_data["offers"][0]
                        effective_offer_id = current_offer.get("offerId")
                        if not effective_offer_id:
                            err_msg = f"Error: SKU {params.sku} found, but offerId is missing in the response."
                            logger.error(err_msg)
                            return err_msg
                        logger.info(f"Successfully fetched offer by SKU. Offer ID: {effective_offer_id}")
                        # Update params.offer_id for downstream consistency if it was originally None
                        params.offer_id = effective_offer_id 
                    elif sku_offers_data.get("total", 0) > 1:
                        err_msg = f"Error: Multiple offers found for SKU {params.sku}. Cannot determine which to update."
                        logger.error(err_msg)
                        return err_msg
                    else:
                        err_msg = f"Error: No offer found for SKU {params.sku}."
                        logger.error(err_msg)
                        return err_msg
                elif params.offer_id:
                    # Offer ID is provided, fetch by Offer ID as before
                    get_url = f"{base_url}/offer/{params.offer_id}"
                    logger.info(f"Fetching current offer by Offer ID: {params.offer_id} from {get_url}")
                    get_response = await client.get(get_url, headers=headers)
                    get_response.raise_for_status()
                    current_offer = get_response.json()
                    effective_offer_id = params.offer_id # Already known
                    logger.info(f"Successfully fetched current offer data for Offer ID: {effective_offer_id}")
                else:
                    # This case should not be reached due to Pydantic validation, but as a safeguard:
                    err_msg = "Error: Neither Offer ID nor SKU was effectively provided after validation."
                    logger.error(err_msg)
                    return err_msg

                logger.debug(f"Current offer data after fetch (ID: {effective_offer_id}): {current_offer}")

            except httpx.HTTPStatusError as e:
                error_message = (
                    f"Error fetching offer details for '{params.sku or params.offer_id}': "
                    f"{e.response.status_code} - {e.response.text}"
                )
                logger.error(error_message)
                return error_message
            except httpx.RequestError as e:
                error_message = f"Request error fetching offer details for '{params.sku or params.offer_id}': {e}"
                logger.error(error_message)
                return error_message
            except Exception as e:
                error_message = f"Unexpected error fetching offer details for '{params.sku or params.offer_id}': {str(e)}"
                logger.error(error_message, exc_info=True)
                return error_message
        
        if not current_offer or not effective_offer_id:
            return f"Error: Could not retrieve current offer details for '{params.sku or params.offer_id}'. Update aborted."

        # Merge fields, preserving existing values if not provided in the update
        update_request_data = {
            "offerId": effective_offer_id,
            "sku": params.sku if params.sku is not None else current_offer.get('sku'),
            "marketplaceId": (
                params.marketplace_id
                if params.marketplace_id is not None
                else current_offer.get(
                    'marketplaceId', inventory_mcp.ebay_mcp_server.default_marketplace_id
                )
            ),
            "format": current_offer.get('format', 'FIXED_PRICE'),  # Preserve format
            "availableQuantity": params.available_quantity if params.available_quantity is not None else current_offer.get('availableQuantity'),
            "pricingSummary": params.pricing_summary if params.pricing_summary is not None else current_offer.get('pricingSummary'),
            "categoryId": params.category_id if params.category_id is not None else current_offer.get('categoryId'),
            "listingDescription": params.listing_description if params.listing_description is not None else current_offer.get('listingDescription'),
            "listingDuration": params.listing_duration if params.listing_duration is not None else current_offer.get('listingDuration'),
            "listingStartDate": params.listing_start_date if params.listing_start_date is not None else current_offer.get('listingStartDate'),
            "merchantLocationKey": params.merchant_location_key if params.merchant_location_key is not None else current_offer.get('merchantLocationKey'),
            "listingPolicies": params.listing_policies if params.listing_policies is not None else current_offer.get('listingPolicies'),
            "secondaryCategoryId": params.secondary_category_id if params.secondary_category_id is not None else current_offer.get('secondaryCategoryId'),
            "storeCategoryNames": params.store_category_names if params.store_category_names is not None else current_offer.get('storeCategoryNames'),
            "quantityLimitPerBuyer": params.quantity_limit_per_buyer if params.quantity_limit_per_buyer is not None else current_offer.get('quantityLimitPerBuyer'),
            "lotSize": params.lot_size if params.lot_size is not None else current_offer.get('lotSize'),
            "hideBuyerDetails": params.hide_buyer_details if params.hide_buyer_details is not None else current_offer.get('hideBuyerDetails'),
            "includeCatalogProductDetails": params.include_catalog_product_details if params.include_catalog_product_details is not None else current_offer.get('includeCatalogProductDetails'),
            "charity": params.charity if params.charity is not None else current_offer.get('charity'),
            "extendedProducerResponsibility": params.extended_producer_responsibility if params.extended_producer_responsibility is not None else current_offer.get('extendedProducerResponsibility'),
            "regulatory": params.regulatory if params.regulatory is not None else current_offer.get('regulatory'),
            "tax": params.tax if params.tax is not None else current_offer.get('tax'),
        }

        # Filter out None values before passing to UpdateOfferRequest for validation
        # Pydantic models expect actual values or absence, not explicit None for optional fields unless Union[..., None]
        validated_update_data = {k: v for k, v in update_request_data.items() if v is not None}
        
        try:
            # Create UpdateOfferRequest instance for validation against eBay's model structure
            # This step is crucial if UpdateOfferRequest has its own complex validation rules or structure
            # that differs from the simple dictionary we've built.
            # Assuming UpdateOfferRequest is a Pydantic model defined elsewhere that mirrors eBay's expected structure.
            # If UpdateOfferRequest is not defined or needed, this can be simplified.
            # For now, we'll assume it's a direct pass-through if not strictly defined.
            # update_request_validated_model = UpdateOfferRequest(**validated_update_data)
            # final_payload = update_request_validated_model.model_dump(exclude_none=True)
            # For now, directly use validated_update_data as Pydantic model for UpdateOfferParams already did input validation.
            final_payload = validated_update_data
            logger.debug(f"update_offer_safe: Prepared update payload: {final_payload}")

            # Send update request using the existing client session
            # Ensure effective_offer_id is used in the URL
            update_url = f"{base_url}/offer/{effective_offer_id}"
            logger.info(f"update_offer_safe: Sending PUT request to {update_url}")
            
            put_headers = get_standard_ebay_headers(inventory_mcp.ebay_mcp_server.access_token)
            import json # Ensure json is imported if not already at top level
            update_response = await client.put(update_url, headers=put_headers, content=json.dumps(final_payload))
            update_response.raise_for_status()

            updated_fields_count = len([k for k, v in final_payload.items() if k not in ['offerId', 'marketplaceId', 'format'] and params.__dict__.get(k) is not None])

            logger.info(f"Successfully updated offer {effective_offer_id}. {updated_fields_count} fields were part of the update request.")
            response_text = update_response.text
            # eBay often returns 204 No Content on successful PUT/DELETE. If so, provide a generic success message.
            if update_response.status_code == 204:
                return f"Successfully updated offer {effective_offer_id}. {updated_fields_count} fields updated. (Status: 204 No Content)"
            return f"Successfully updated offer {effective_offer_id}. {updated_fields_count} fields updated. Response: {response_text if response_text else '(No response body)'}"

        except httpx.HTTPStatusError as e:
            error_message = f"Error updating offer {effective_offer_id}: {e.response.status_code} - {e.response.text}"
            logger.error(error_message)
            return error_message
        except httpx.RequestError as e:
            error_message = f"Request error updating offer {effective_offer_id}: {e}"
            logger.error(error_message)
            return error_message
        except Exception as e: # Catch other unexpected errors during update
            error_message = f"Unexpected error during offer update for {effective_offer_id}: {str(e)}"
            logger.error(error_message, exc_info=True)
            return error_message

    # This outer try-except catches errors from initial Pydantic validation or other setup issues.
    except Exception as e:
        logger.error(f"Critical error in update_offer_safe setup or pre-API call phase: {str(e)}", exc_info=True)
        return f"Critical error: {str(e)}"
