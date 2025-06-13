import pytest
import pytest_asyncio
import json
from fastmcp import Client

TEST_SKU = "TT-01"

# Basic inventory item data used when creating the item
DEFAULT_ITEM_DATA = {
    "product": {
        "title": "Copeland Spode Queen Elizabeth II 1953 Coronation Cup and Saucer",
        "description": "This is a Copeland Spode cup and saucer commemorating the coronation of Queen Elizabeth II on June 2nd, 1953.",
        "imageUrls": [
            "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_81.jpg",
            "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_78.jpg",
            "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_80.jpg",
            "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_82.jpg",
            "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_79.jpg",
            "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_77.jpg"
        ],
    },
    "condition": "USED_GOOD",
    "conditionDescription": "Used condition with staining and minor chips around the rims.",
    "availability": {"shipToLocationAvailability": {"quantity": 1}},
}

@pytest_asyncio.fixture
async def mcp_client():
    """Fixture to provide MCP client connection"""
    async with Client("src/main_server.py") as client:
        yield client

@pytest_asyncio.fixture
async def test_item(mcp_client):
    """Ensure inventory item exists; create if missing"""
    # Attempt to get existing item
    try:
        result = await mcp_client.call_tool(
            "inventoryAPI_manage_inventory_item",
            {"params": {"sku": TEST_SKU, "action": "get"}},
        )
        json_data = json.loads(result[0].text)
        if json_data.get("success"):
            return json_data["data"]  # existing item data
    except Exception:
        pass

    # Create item since it does not exist
    result = await mcp_client.call_tool(
        "inventoryAPI_manage_inventory_item",
        {
            "params": {
                "sku": TEST_SKU,
                "action": "create",
                "item_data": DEFAULT_ITEM_DATA,
            }
        },
    )
    json_data = json.loads(result[0].text)
    assert json_data.get("success"), f"Failed to create test inventory item: {json_data.get('error')}"
    return json_data["data"]


@pytest.mark.asyncio
async def test_get_inventory_item(mcp_client, test_item):
    """Test getting an existing inventory item"""
    result = await mcp_client.call_tool(
        "inventoryAPI_manage_inventory_item",
        {"params": {"sku": TEST_SKU, "action": "get"}},
    )

    json_data = json.loads(result[0].text)
    assert json_data.get("success"), f"Get inventory item failed: {json_data.get('error')}"
    assert json_data["data"]["sku"] == TEST_SKU


@pytest.mark.asyncio
async def test_modify_inventory_item(mcp_client, test_item):
    """Test modifying an inventory item"""
    modified_data = {
        "product": {
            "title": "Copeland Spode Coronation Cup and Saucer - MODIFIED",
            "description": "MODIFIED description for test purposes.",
        },
        "condition": "USED_EXCELLENT",
        "availability": {"shipToLocationAvailability": {"quantity": 2}},
    }

    result = await mcp_client.call_tool(
        "inventoryAPI_manage_inventory_item",
        {
            "params": {
                "sku": TEST_SKU,
                "action": "modify",
                "item_data": modified_data,
            }
        },
    )

    json_data = json.loads(result[0].text)
    assert json_data.get("success"), f"Modify inventory item failed: {json_data.get('error')}"


@pytest.mark.asyncio
async def test_delete_inventory_item(mcp_client, test_item):
    """Test deleting an inventory item"""
    result = await mcp_client.call_tool(
        "inventoryAPI_manage_inventory_item",
        {"params": {"sku": TEST_SKU, "action": "delete"}},
    )

    json_data = json.loads(result[0].text)
    assert json_data.get("success"), f"Delete inventory item failed: {json_data.get('error')}"  
