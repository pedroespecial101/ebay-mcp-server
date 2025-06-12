import logging
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Create the MCP server instance for prompts
prompts_mcp = FastMCP(
    name="CustomPrompts",
    title="Custom Prompts Server",
    description="A server hosting custom prompts for interacting with the eBay MCP system.",
    version="0.1.0"
)

logger.info("CustomPrompts MCP server instance created.")

@prompts_mcp.prompt
def guide_create_and_publish_item() -> str:
    """
    Provides a guide on the 3-step process to create an inventory item and publish it as an offer on eBay.
    Also includes tips for handling missing data.
    """
    logger.info("Executing guide_create_and_publish_item prompt.")
    guidance = """
    To create a new inventory item and publish it as an offer on eBay, follow this 3-step process:

    Step 1: Create the Inventory Item
    ---------------------------------
    Use the 'inventoryAPI.manage_inventory_item' tool with action 'create'.
    You'll need to provide essential details like SKU, product information (title, description, image URLs),
    package weight and dimensions, and availability (ship-to-home quantity).
    Example:
    inventoryAPI.manage_inventory_item(
        sku=\"YOUR_UNIQUE_SKU\",
        action=\"create\",
        item_data={
            \"product\": {
                \"title\": \"Example Product Title\",
                \"description\": \"Detailed description of the product.\",
                \"imageUrls\": [\"https://example.com/image1.jpg\"]
            },
            \"packageWeightAndDimensions\": {
                \"weight\": {\"unit\": \"KILOGRAM\", \"value\": 1.5},
                \"dimensions\": {\"unit\": \"CENTIMETER\", \"length\": 30, \"width\": 20, \"height\": 10}
            },
            \"availability\": {
                \"shipToLocationAvailability\": {\"quantity\": 10}
            }
        }
    )

    Step 2: Create an Offer for the Inventory Item
    ---------------------------------------------
    Once the inventory item is created (Step 1), use the 'inventoryAPI.manage_offer' tool with action 'create'.
    This links the inventory item (by SKU) to a marketplace listing.
    You'll need to provide the SKU, marketplace ID (e.g., 'EBAY_GB' for UK), format (usually 'FIXED_PRICE'),
    the eBay category ID for the item, and pricing details.
    To find the correct category ID, you can use the 'taxonomyAPI.get_category_suggestions' tool.
    Example:
    inventoryAPI.manage_offer(
        sku=\"YOUR_UNIQUE_SKU\",
        action=\"create\",
        offer_data={
            \"sku\": \"YOUR_UNIQUE_SKU\",
            \"marketplaceId\": \"EBAY_GB\",
            \"format\": \"FIXED_PRICE\",
            \"availableQuantity\": 10, # Should match inventory item availability
            \"categoryId\": \"YOUR_EBAY_CATEGORY_ID\", # Get this from taxonomyAPI
            \"listingDescription\": \"Same or similar to product description.\",
            \"pricingSummary\": {
                \"price\": {\"currency\": \"GBP\", \"value\": \"29.99\"}
            },
            \"merchantLocationKey\": \"DEFAULT\" # Or your specific location key
        }
    )

    Step 3: Publish the Offer
    -------------------------
    After creating the offer (Step 2), use the 'inventoryAPI.manage_offer' tool again, this time with action 'publish'.
    This makes the listing live on eBay. You'll typically need the offer ID returned when you created the offer.
    Example:
    inventoryAPI.manage_offer(
        sku=\"YOUR_UNIQUE_SKU\", # Can be useful for context, but offerId is key
        action=\"publish\",
        offer_data={ 
            \"offerId\": \"THE_OFFER_ID_FROM_STEP_2\"
        }
    )

    Guidance for Missing Data:
    --------------------------
    - Category ID: Use `taxonomyAPI.get_category_suggestions(query=\"your item type\")` to find suitable eBay category IDs.
    - Item Specifics (Aspects): Once you have a category ID, use `taxonomyAPI.get_item_aspects_for_category(category_id=\"THE_CATEGORY_ID\")`
      to find required and recommended item specifics. Add these to the `product.aspects` field in Step 1.
      Example for `product.aspects` in Step 1:
      \"aspects\": {
          \"Brand\": [\"Unbranded\"],
          \"Type\": [\"Specific Type\"],
          # ... other aspects
      }
    - Condition: Ensure `condition` (e.g., \"NEW\", \"USED_EXCELLENT\") is set in `item_data` for Step 1.
    - Policies: Listing policies (payment, return, fulfillment) are usually set in your eBay account.
      If you need to specify them per listing, include `listingPolicies` in the offer data (Step 2).

    Remember to replace placeholders like 'YOUR_UNIQUE_SKU', 'YOUR_EBAY_CATEGORY_ID', and 'THE_OFFER_ID_FROM_STEP_2' with actual values.
    """
    return guidance
