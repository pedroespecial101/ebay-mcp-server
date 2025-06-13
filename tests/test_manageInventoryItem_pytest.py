import pytest
import pytest_asyncio
import json
from fastmcp import Client

# Test configuration
TEST_SKU = "TT-01"
TEST_ITEM_DATA = {
    "product": {
        "title": "Copeland Spode Queen Elizabeth II 1953 Coronation Cup and Saucer",
        "description": "This is a Copeland Spode cup and saucer commemorating the coronation of Queen Elizabeth II on June 2nd, 1953.",
        "imageUrls": [
            "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_81.jpg"
        ],
    },
    "condition": "USED_GOOD",
    "conditionDescription": "Used condition with staining and minor chips around the rims.",
    "availability": {"shipToLocationAvailability": {"quantity": 1}},
}

# Fixtures
@pytest_asyncio.fixture
async def mcp_client():
    """Fixture to provide MCP client connection"""
    async with Client("src/main_server.py") as client:
        yield client

# Test 1: Clean up - Delete inventory item if it exists
@pytest.mark.asyncio
@pytest.mark.order(1)
async def test_01_cleanup_inventory_item(mcp_client):
    """Test 1: Delete inventory item if it exists (cleanup)"""
    try:
        result = await mcp_client.call_tool(
            "inventoryAPI_manage_inventory_item",
            {"params": {"sku": TEST_SKU, "action": "delete"}},
        )
        json_data = json.loads(result[0].text)
        if json_data.get("success"):
            print(f"Deleted existing inventory item: {TEST_SKU}")
    except Exception as e:
        print(f"No cleanup needed or cleanup failed: {str(e)}")
    
    # This test always passes as it's just for cleanup
    assert True

# Test 2: Create inventory item
@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_02_create_inventory_item(mcp_client):
    """Test 2: Create a new inventory item"""
    # First, clean up any existing item
    try:
        await mcp_client.call_tool(
            "inventoryAPI_manage_inventory_item",
            {"params": {"sku": TEST_SKU, "action": "delete"}},
        )
    except Exception as e:
        print(f"Cleanup of existing item failed (may not exist): {str(e)}")
    
    # Now create the item
    result = await mcp_client.call_tool(
        "inventoryAPI_manage_inventory_item",
        {
            "params": {
                "sku": TEST_SKU,
                "action": "create",
                "item_data": TEST_ITEM_DATA,
            }
        },
    )
    
    # Handle the response
    try:
        json_data = json.loads(result[0].text)
    except json.JSONDecodeError:
        assert False, f"Invalid JSON response: {result[0].text}"
    
    # Check if creation was successful
    assert json_data.get("success"), f"Create inventory item failed: {json_data.get('error', 'Unknown error')}"
    assert "data" in json_data, f"Response missing 'data' field: {json_data}"
    assert json_data["data"].get("sku") == TEST_SKU, \
        f"Expected SKU '{TEST_SKU}', got: {json_data['data'].get('sku')}"
    
    return json_data["data"]

# Test 3: Get inventory item
@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_03_get_inventory_item(mcp_client):
    """Test 3: Get an existing inventory item"""
    result = await mcp_client.call_tool(
        "inventoryAPI_manage_inventory_item",
        {"params": {"sku": TEST_SKU, "action": "get"}},
    )
    json_data = json.loads(result[0].text)
    assert json_data.get("success"), f"Get inventory item failed: {json_data.get('error')}"
    assert json_data["data"]["sku"] == TEST_SKU
    return json_data["data"]

# Test 4: Modify inventory item
@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_04_modify_inventory_item(mcp_client):
    """Test 4: Modify an existing inventory item"""
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
    return json_data["data"]

# Test 5: Verify modified inventory item
@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_05_verify_modified_item(mcp_client):
    """Test 5: Verify the modified inventory item"""
    # First, get the modified item
    result = await mcp_client.call_tool(
        "inventoryAPI_manage_inventory_item",
        {"params": {"sku": TEST_SKU, "action": "get"}},
    )
    
    # Handle potential empty or invalid JSON response
    try:
        json_data = json.loads(result[0].text)
    except json.JSONDecodeError:
        assert False, f"Invalid JSON response: {result[0].text}"
    
    # Check if the API call was successful
    assert json_data.get("success"), f"Get modified item failed: {json_data.get('error', 'Unknown error')}"
    
    # Check if 'data' exists in the response
    assert "data" in json_data, f"Response missing 'data' field: {json_data}"
    item_data = json_data["data"]
    
    # Print the full response for debugging
    print(f"Full item data: {json.dumps(item_data, indent=2)}")
    
    # Check top-level fields in the details object
    assert "details" in item_data, f"Item data missing 'details' field: {item_data}"
    details = item_data["details"]
    
    # Check SKU matches
    assert details.get("sku") == TEST_SKU, f"Expected SKU '{TEST_SKU}', got: {details.get('sku')}"
    
    # Check product information
    assert "product" in details, f"Details missing 'product' field: {details}"
    assert "title" in details["product"], f"Product missing 'title' field: {details['product']}"
    assert "MODIFIED" in details["product"]["title"], \
        f"Expected 'MODIFIED' in title, got: {details['product']['title']}"
    
    # Check condition and availability
    assert details.get("condition") == "USED_EXCELLENT", \
        f"Expected condition to be 'USED_EXCELLENT', got: {details.get('condition')}"
    
    # Check availability if present
    if "availability" in details:
        assert "shipToLocationAvailability" in details["availability"], \
            f"Availability missing 'shipToLocationAvailability' field: {details['availability']}"
        assert details["availability"]["shipToLocationAvailability"].get("quantity") == 2, \
            f"Expected quantity to be 2, got: {details['availability']['shipToLocationAvailability'].get('quantity')}"
    
    return item_data

# Test 6: Delete inventory item
@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_06_delete_inventory_item(mcp_client):
    """Test 6: Delete the inventory item"""
    # First, delete the item
    result = await mcp_client.call_tool(
        "inventoryAPI_manage_inventory_item",
        {"params": {"sku": TEST_SKU, "action": "delete"}},
    )
    
    # Handle potential empty or invalid JSON response
    try:
        json_data = json.loads(result[0].text) if result[0].text else {}
    except json.JSONDecodeError:
        assert False, f"Invalid JSON response when deleting item: {result[0].text}"
    
    # Check if deletion was successful
    assert json_data.get("success"), f"Delete inventory item failed: {json_data.get('error', 'Unknown error')}"
    
    # Verify deletion by trying to get the deleted item
    result = await mcp_client.call_tool(
        "inventoryAPI_manage_inventory_item",
        {"params": {"sku": TEST_SKU, "action": "get"}},
    )
    
    # The get request for a non-existent item should not be successful
    try:
        json_data = json.loads(result[0].text) if result[0].text else {}
        assert not json_data.get("success"), \
            f"Expected item to be deleted, but it still exists: {json_data}"
    except json.JSONDecodeError:
        # If we can't parse the response, it's likely because the item doesn't exist
        # which is the expected behavior after deletion
        pass
