import pytest
import pytest_asyncio
import json
from fastmcp import Client

TEST_SKU = "TT-01"
TEST_CATEGORY_ID = "39630"

@pytest_asyncio.fixture
async def mcp_client():
    """Fixture to provide MCP client connection"""
    async with Client("src/main_server.py") as client:
        yield client

@pytest_asyncio.fixture
async def test_offer(mcp_client):
    """Fixture to ensure we have a test offer to work with"""
    # Check if offer exists, create if not
    try:
        result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
            "params": {"sku": TEST_SKU, "action": "get"}
        })
        json_data = json.loads(result[0].text)
        if json_data.get('success') and 'offer_id' in json_data.get('data', {}):
            return json_data['data']['offer_id']
    except:
        pass
    
    # Create new offer
    result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {
            "sku": TEST_SKU,
            "action": "create",
            "offer_data": {
                "categoryId": TEST_CATEGORY_ID,
                "availableQuantity": 1,
                "pricingSummary": {"price": {"value": "9.99", "currency": "GBP"}},
                "listingDescription": "Test listing description"
            }
        }
    })
    json_data = json.loads(result[0].text)
    assert json_data.get('success'), f"Failed to create test offer: {json_data.get('error')}"
    return json_data['data']['offer_id']

@pytest.mark.asyncio
async def test_get_offer(mcp_client, test_offer):
    """Test getting an existing offer"""
    result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {"sku": TEST_SKU, "action": "get"}
    })
    
    json_data = json.loads(result[0].text)
    assert json_data.get('success'), f"Get offer failed: {json_data.get('error')}"
    assert json_data['data']['offer_id'] == test_offer

@pytest.mark.asyncio
async def test_modify_offer(mcp_client, test_offer):
    """Test modifying an offer"""
    result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {
            "sku": TEST_SKU,
            "action": "modify",
            "offer_data": {
                "availableQuantity": 2,
                "pricingSummary": {"price": {"value": "19.99", "currency": "GBP"}},
                "condition": "USED_GOOD"
            }
        }
    })
    
    json_data = json.loads(result[0].text)
    assert json_data.get('success'), f"Modify offer failed: {json_data.get('error')}"

@pytest.mark.asyncio
async def test_publish_offer(mcp_client, test_offer):
    """Test publishing an offer"""
    # First update with required fields
    await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {
            "sku": TEST_SKU,
            "action": "modify",
            "offer_data": {
                "condition": "USED_EXCELLENT",
                "conditionDescription": "Chips around edge",
                "categoryId": TEST_CATEGORY_ID,
            }
        }
    })
    
    # Then publish
    result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {"sku": TEST_SKU, "action": "publish"}
    })
    
    json_data = json.loads(result[0].text)
    assert json_data.get('success'), f"Publish offer failed: {json_data.get('error')}"

@pytest.mark.asyncio
async def test_withdraw_offer(mcp_client, test_offer):
    """Test withdrawing an offer"""
    result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {"sku": TEST_SKU, "action": "withdraw"}
    })
    
    json_data = json.loads(result[0].text)
    assert json_data.get('success'), f"Withdraw offer failed: {json_data.get('error')}"
