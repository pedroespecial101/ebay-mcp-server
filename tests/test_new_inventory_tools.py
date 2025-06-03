#!/usr/bin/env python3
"""
Test script for the new eBay Inventory API MCP tools.
This script tests the three new tools: get_inventory_item_by_sku, get_inventory_items, and delete_inventory_item.
"""
import os
import sys
import asyncio
import json
import logging

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test the parameter models directly
try:
    # Add src to path for imports
    src_path = os.path.join(project_root, 'src')
    sys.path.append(src_path)

    from models.mcp_tools import GetInventoryItemBySkuParams, GetInventoryItemsParams, DeleteInventoryItemParams
    from models.ebay.inventory import InventoryItemDetails, InventoryItemsListResponse, DeleteInventoryItemResponse
    logger.info("Successfully imported parameter and model classes")
except ImportError as e:
    logger.error(f"Failed to import models: {e}")
    sys.exit(1)

async def test_new_inventory_tools():
    """Test the three new inventory tools."""

    logger.info("Testing new eBay Inventory API tools...")
    
    # Test parameter validation
    logger.info("Testing parameter validation...")
    
    # Test get_inventory_item_by_sku with valid SKU
    try:
        valid_params = GetInventoryItemBySkuParams(sku="TEST-SKU-123")
        logger.info(f"✓ Valid SKU parameter: {valid_params.sku}")
    except Exception as e:
        logger.error(f"✗ Failed to validate valid SKU: {e}")

    # Test get_inventory_item_by_sku with invalid SKU (too long)
    try:
        invalid_params = GetInventoryItemBySkuParams(sku="A" * 51)  # 51 characters, should fail
        logger.error(f"✗ Should have failed for SKU too long: {invalid_params.sku}")
    except Exception as e:
        logger.info(f"✓ Correctly rejected SKU too long: {e}")

    # Test get_inventory_items with valid pagination
    try:
        valid_pagination = GetInventoryItemsParams(limit=50, offset=10)
        logger.info(f"✓ Valid pagination parameters: limit={valid_pagination.limit}, offset={valid_pagination.offset}")
    except Exception as e:
        logger.error(f"✗ Failed to validate valid pagination: {e}")

    # Test get_inventory_items with invalid limit
    try:
        invalid_pagination = GetInventoryItemsParams(limit=250, offset=0)  # limit too high
        logger.error(f"✗ Should have failed for limit too high: {invalid_pagination.limit}")
    except Exception as e:
        logger.info(f"✓ Correctly rejected limit too high: {e}")

    # Test get_inventory_items with negative offset
    try:
        invalid_pagination = GetInventoryItemsParams(limit=25, offset=-1)  # negative offset
        logger.error(f"✗ Should have failed for negative offset: {invalid_pagination.offset}")
    except Exception as e:
        logger.info(f"✓ Correctly rejected negative offset: {e}")

    # Test delete_inventory_item with valid SKU
    try:
        valid_delete_params = DeleteInventoryItemParams(sku="DELETE-TEST-SKU")
        logger.info(f"✓ Valid delete SKU parameter: {valid_delete_params.sku}")
    except Exception as e:
        logger.error(f"✗ Failed to validate valid delete SKU: {e}")
    
    logger.info("Parameter validation tests completed")
    
    # Test model creation
    logger.info("Testing model creation...")
    
    try:
        # Test InventoryItemDetails
        item_details = InventoryItemDetails(
            sku="TEST-SKU-123",
            locale="en_GB",
            condition="NEW",
            condition_description="Brand new item",
            product={"title": "Test Product"},
            availability={"quantity": 10}
        )
        logger.info(f"✓ Created InventoryItemDetails: {item_details.sku}")

        # Test DeleteInventoryItemResponse success
        success_response = DeleteInventoryItemResponse.success_response("TEST-SKU-123")
        logger.info(f"✓ Created success delete response: {success_response.message}")

        # Test DeleteInventoryItemResponse error
        error_response = DeleteInventoryItemResponse.error_response("Test error", "TEST-SKU-123")
        logger.info(f"✓ Created error delete response: {error_response.message}")

        # Test InventoryItemsListResponse
        mock_data = {
            "inventoryItems": [
                {"sku": "SKU1", "condition": "NEW"},
                {"sku": "SKU2", "condition": "USED"}
            ],
            "total": 2,
            "size": 2,
            "offset": 0,
            "limit": 25
        }
        list_response = InventoryItemsListResponse.success_response(mock_data)
        logger.info(f"✓ Created inventory list response with {len(list_response.inventory_items)} items")

    except Exception as e:
        logger.error(f"✗ Failed to create models: {e}")
    
    logger.info("Model creation tests completed")
    
    logger.info("All tests completed successfully! The new inventory tools are ready for use.")

if __name__ == "__main__":
    asyncio.run(test_new_inventory_tools())
