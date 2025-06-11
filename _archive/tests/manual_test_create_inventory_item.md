# Manual Testing Guide for create_or_replace_inventory_item

## Overview
This guide provides instructions for manually testing the `create_or_replace_inventory_item` MCP tool through the web interface.

## Access the MCP Test UI
1. Start the MCP Test UI: `./start_mcp_test_ui.sh`
2. Open browser to: http://127.0.0.1:8000/mcp/
3. Look for the tool: `inventoryAPI_create_or_replace_inventory_item`

## Test Case 1: Create New Inventory Item (Minimal Required Fields)

### Required Parameters:
- **sku**: `TEST-ITEM-001`
- **condition**: `NEW`
- **product_title**: `Test Product - Wireless Bluetooth Headphones`
- **product_description**: `High-quality wireless Bluetooth headphones with noise cancellation. Perfect for music lovers and professionals.`
- **quantity**: `5`

### Expected Result:
- Success response with status code 201 (created)
- JSON response showing the item was created successfully

## Test Case 2: Create Inventory Item with Full Details

### Required Parameters:
- **sku**: `TEST-ITEM-002`
- **condition**: `NEW`
- **product_title**: `Premium Wireless Headphones - Full Featured`
- **product_description**: `Premium wireless Bluetooth headphones with advanced noise cancellation, premium materials, and extended battery life.`
- **quantity**: `10`

### Optional Parameters:
- **product_brand**: `TestBrand`
- **product_mpn**: `TB-WBH-002`
- **product_aspects**: `{"Brand": "TestBrand", "Model": "TB-WBH-002", "Color": "Black", "Connectivity": "Bluetooth", "Features": "Noise Cancellation"}`
- **product_imageUrls**: `["https://example.com/images/headphones-main.jpg", "https://example.com/images/headphones-side.jpg"]`
- **condition_description**: `Brand new in original packaging`
- **package_weight_value**: `0.5`
- **package_weight_unit**: `KILOGRAM`
- **package_dimensions_length**: `20.0`
- **package_dimensions_width**: `15.0`
- **package_dimensions_height**: `8.0`
- **package_dimensions_unit**: `CENTIMETER`

### Expected Result:
- Success response with status code 201 (created)
- JSON response showing the item was created with all details

## Test Case 3: Update Existing Inventory Item

### Use the same SKU from Test Case 1:
- **sku**: `TEST-ITEM-001`
- **condition**: `NEW`
- **product_title**: `Test Product - Wireless Bluetooth Headphones (Updated)`
- **product_description**: `Updated description: High-quality wireless Bluetooth headphones with enhanced noise cancellation.`
- **quantity**: `15` (changed from 5)

### Expected Result:
- Success response with status code 204 (updated)
- JSON response showing the item was updated successfully

## Test Case 4: Validation Testing

### Test Invalid Condition:
- **sku**: `TEST-VALIDATION-001`
- **condition**: `INVALID_CONDITION`
- **product_title**: `Test Product`
- **product_description**: `Test Description`

### Expected Result:
- Validation error mentioning allowed condition values

### Test Invalid SKU (too long):
- **sku**: `THIS_IS_A_VERY_LONG_SKU_THAT_EXCEEDS_THE_FIFTY_CHARACTER_LIMIT_AND_SHOULD_FAIL`
- **condition**: `NEW`
- **product_title**: `Test Product`
- **product_description**: `Test Description`

### Expected Result:
- Validation error about SKU length

### Test Invalid URL:
- **sku**: `TEST-URL-001`
- **condition**: `NEW`
- **product_title**: `Test Product`
- **product_description**: `Test Description`
- **product_imageUrls**: `["not-a-valid-url", "also-invalid"]`

### Expected Result:
- Validation error about invalid URL format

## Condition Values Reference
Valid condition values for testing:
- `NEW`
- `LIKE_NEW`
- `NEW_OTHER`
- `NEW_WITH_DEFECTS`
- `MANUFACTURER_REFURBISHED`
- `CERTIFIED_REFURBISHED`
- `EXCELLENT_REFURBISHED`
- `VERY_GOOD_REFURBISHED`
- `GOOD_REFURBISHED`
- `SELLER_REFURBISHED`
- `USED_EXCELLENT`
- `USED_VERY_GOOD`
- `USED_GOOD`
- `USED_ACCEPTABLE`
- `FOR_PARTS_OR_NOT_WORKING`
- `PRE_OWNED_EXCELLENT`
- `PRE_OWNED_FAIR`

## Weight Units Reference
Valid weight units:
- `POUND`
- `KILOGRAM`
- `OUNCE`
- `GRAM`

## Dimension Units Reference
Valid dimension units:
- `INCH`
- `FEET`
- `CENTIMETER`
- `METER`

## Notes
- The tool supports both creating new items (201 response) and updating existing items (204 response)
- All validation is performed before making the API call to eBay
- The tool uses the existing authentication system and will handle token refresh automatically
- Complex JSON objects for product_aspects should be properly formatted JSON strings
- Arrays like product_imageUrls should be properly formatted JSON arrays

## Troubleshooting
- If you get authentication errors, run the `auth_test_auth` tool first
- If validation errors occur, check the parameter values against the reference lists above
- If the tool is not found, ensure the MCP server has restarted after adding the new tool
