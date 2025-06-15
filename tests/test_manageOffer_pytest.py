import pytest
import pytest_asyncio
import json
from fastmcp import Client

# --- Test Configuration ---
TEST_SKU = "TT-01"
TEST_CATEGORY_ID = "39630" # Example Category ID, replace if needed

# Data for creating the base inventory item if it doesn't exist
TEST_INVENTORY_ITEM_DATA = {
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
                    ]   
    },
    "condition": "USED_EXCELLENT",
    "conditionDescription": "Used condition with staining and minor chips around the rims.",
    "availability": {"shipToLocationAvailability": {"quantity": 1}},
}

# Data for the initial offer creation
INITIAL_OFFER_DATA = {
    "marketplaceId": "EBAY_GB",
    "format": "FIXED_PRICE",
    "availableQuantity": 5,
    "categoryId": TEST_CATEGORY_ID,
    "pricingSummary": {
        "price": {
            "value": "19.99",
            "currency": "GBP"
        }
    },
}

# Data for modifying the offer
MODIFIED_OFFER_DATA = {
    "availableQuantity": 3,
    "pricingSummary": {
        "price": {
            "value": "30.11",
            "currency": "GBP"
        }
    }
}

# --- Fixtures ---
@pytest_asyncio.fixture
async def mcp_client():
    """Fixture to provide MCP client connection"""
    async with Client("src/main_server.py") as client:
        yield client

# --- Helper to get offer details ---
async def _get_offer_details(mcp_client, sku):
    try:
        result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
            "params": {"sku": sku, "action": "get"}
        })
        response_text = result[0].text
        json_data = json.loads(response_text)
        if json_data.get('success') and json_data.get('data', {}).get('details'):
            return json_data['data']['details'] # This is the raw offer data from eBay
    except Exception as e:
        print(f"Error getting offer details for {sku}: {e}\nResponse: {response_text if 'response_text' in locals() else 'N/A'}")
    return None

# --- Test Functions ---

@pytest.mark.asyncio
async def test_01_cleanup_prepare_offer(mcp_client):
    """Ensures inventory item exists and no offer is currently published."""
    # 1a. Check Inventory Item Exists, create if not
    try:
        inv_item_result = await mcp_client.call_tool("inventoryAPI_manage_inventory_item", {
            "params": {"sku": TEST_SKU, "action": "get"}
        })
        inv_item_json = json.loads(inv_item_result[0].text)
        if not (inv_item_json.get('success') and inv_item_json.get('data', {}).get('details')):
            print(f"Inventory item {TEST_SKU} not found, creating...")
            create_inv_result = await mcp_client.call_tool("inventoryAPI_manage_inventory_item", {
                "params": {
                    "sku": TEST_SKU,
                    "action": "create",
                    "item_data": TEST_INVENTORY_ITEM_DATA
                }
            })
            create_inv_json = json.loads(create_inv_result[0].text)
            assert create_inv_json.get('success'), f"Failed to create inventory item {TEST_SKU}: {create_inv_json.get('error')}"
            print(f"Inventory item {TEST_SKU} created.")
        else:
            print(f"Inventory item {TEST_SKU} already exists.")
    except Exception as e:
        pytest.fail(f"Error during inventory item check/create for {TEST_SKU}: {e}")

    # 1b. Check if Offer is published, withdraw if so
    offer_details = await _get_offer_details(mcp_client, TEST_SKU)
    if offer_details:
        # eBay API typically returns offerState or listing.listingStatus for published status
        # For simplicity, we'll check for 'PUBLISHED' in a common field, or if a listingId exists
        # Adjust this logic based on the actual structure of your 'get offer' response
        is_published = offer_details.get('offerState') == 'PUBLISHED' or \
                       (offer_details.get('listing') and offer_details['listing'].get('listingId'))

        if is_published:
            print(f"Offer for {TEST_SKU} is published (Offer ID: {offer_details.get('offerId')}). Withdrawing...")
            withdraw_result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
                "params": {"sku": TEST_SKU, "action": "withdraw"}
            })
            withdraw_json = json.loads(withdraw_result[0].text)
            assert withdraw_json.get('success'), f"Failed to withdraw offer for {TEST_SKU}: {withdraw_json.get('error')}"
            print(f"Offer for {TEST_SKU} withdrawn.")
        else:
            # If an offer exists but isn't published, it might be in a 'CREATED' or 'UNPUBLISHED' state.
            # For a clean slate for test_02_create_offer, we should delete it.
            # However, the 'manage_offer' tool doesn't have a 'delete' action for non-published offers.
            # We'll proceed, and test_02_create_offer might fail if an unpublished offer already exists
            # and the API doesn't allow creating another one for the same SKU.
            # A more robust cleanup would involve deleting the inventory item and recreating it if an offer exists.
            print(f"Offer for {TEST_SKU} exists but is not published (Offer ID: {offer_details.get('offerId')}, State: {offer_details.get('offerState')}). Test will proceed.")
    else:
        print(f"No existing offer found for {TEST_SKU}. Ready for creation.")

@pytest.mark.asyncio
async def test_02_create_offer(mcp_client):
    """Creates a new offer for the SKU."""
    print(f"Attempting to create offer for {TEST_SKU}...")
    result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {
            "sku": TEST_SKU,
            "action": "create",
            "offer_data": INITIAL_OFFER_DATA
        }
    })
    json_data = json.loads(result[0].text)
    assert json_data.get('success'), f"test_02_create_offer: Failed - {json_data.get('error', {}).get('message', 'Unknown error')}"
    assert 'offer_id' in json_data.get('data', {}), "test_02_create_offer: Failed - No offer_id in response"
    print(f"test_02_create_offer: Passed. Offer ID: {json_data['data']['offer_id']}")

@pytest.mark.asyncio
async def test_03_get_offer(mcp_client):
    """Checks to make sure the offer exists."""
    print(f"Attempting to get offer for {TEST_SKU}...")
    offer_details = await _get_offer_details(mcp_client, TEST_SKU)
    assert offer_details is not None, f"test_03_get_offer: Failed - Offer for {TEST_SKU} not found or error fetching."
    assert offer_details.get('sku') == TEST_SKU, "test_03_get_offer: Failed - SKU mismatch in fetched offer."
    print(f"test_03_get_offer: Passed. Offer ID: {offer_details.get('offerId')}")

@pytest.mark.asyncio
async def test_04_modify_offer(mcp_client):
    """Makes a modification to the offer."""
    print(f"Attempting to modify offer for {TEST_SKU}...")
    # First, ensure the offer exists to get its ID for the modify call if needed by API (though manage_offer uses SKU)
    current_offer = await _get_offer_details(mcp_client, TEST_SKU)
    assert current_offer, f"Cannot modify offer for {TEST_SKU}, it does not exist or could not be fetched."
    offer_id_to_modify = current_offer.get('offerId')

    result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {
            "sku": TEST_SKU, # manage_offer tool uses SKU to find the offer internally
            "action": "modify",
            "offer_data": MODIFIED_OFFER_DATA
        }
    })
    json_data = json.loads(result[0].text)
    assert json_data.get('success'), f"test_04_modify_offer: Failed - {json_data.get('error', {}).get('message', 'Unknown error')}"
    assert json_data.get('data', {}).get('offer_id') == offer_id_to_modify, "test_04_modify_offer: Modified offer ID does not match original."
    print(f"test_04_modify_offer: Passed. Offer ID: {json_data['data']['offer_id']}")

    # Verification: Get the offer again and check modified fields
    modified_offer_details = await _get_offer_details(mcp_client, TEST_SKU)
    assert modified_offer_details is not None, "test_04_modify_offer: Failed - Could not re-fetch offer after modification."
    assert modified_offer_details.get('availability', {}).get('shipToLocationAvailability', {}).get('quantity') == MODIFIED_OFFER_DATA['availableQuantity'], \
        "test_04_modify_offer: Failed - Available quantity was not modified as expected."
    print(f"test_04_modify_offer: Verification of modified fields passed.")

@pytest.mark.asyncio
async def test_05_publish_offer(mcp_client):
    """Publishes the offer."""
    print(f"Attempting to publish offer for {TEST_SKU}...")
    # Get offer_id first, as publish action in manage_offer requires it (or finds it via SKU)
    current_offer = await _get_offer_details(mcp_client, TEST_SKU)
    assert current_offer, f"Cannot publish offer for {TEST_SKU}, it does not exist or could not be fetched."
    offer_id_to_publish = current_offer.get('offerId')
    assert offer_id_to_publish, f"Could not retrieve offerId for {TEST_SKU} to publish."

    result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {"sku": TEST_SKU, "action": "publish"} # manage_offer tool can use SKU to find offerId
    })
    json_data = json.loads(result[0].text)
    assert json_data.get('success'), f"test_05_publish_offer: Failed - {json_data.get('error', {}).get('message', 'Unknown error')}"
    assert 'listingId' in json_data.get('data', {}).get('details', {}).get('listing', {}), "test_05_publish_offer: Failed - No listingId in response, offer may not be published."
    print(f"test_05_publish_offer: Passed. Listing ID: {json_data['data']['details']['listing']['listingId']}")

@pytest.mark.asyncio
async def test_06_withdraw_offer(mcp_client):
    """Withdraws the offer."""
    print(f"Attempting to withdraw offer for {TEST_SKU}...")
    # Get offer_id first, as withdraw action in manage_offer requires it (or finds it via SKU)
    current_offer = await _get_offer_details(mcp_client, TEST_SKU)
    assert current_offer, f"Cannot withdraw offer for {TEST_SKU}, it does not exist or could not be fetched."
    offer_id_to_withdraw = current_offer.get('offerId')
    assert offer_id_to_withdraw, f"Could not retrieve offerId for {TEST_SKU} to withdraw."

    result = await mcp_client.call_tool("inventoryAPI_manage_offer", {
        "params": {"sku": TEST_SKU, "action": "withdraw"} # manage_offer tool can use SKU to find offerId
    })
    json_data = json.loads(result[0].text)
    assert json_data.get('success'), f"test_06_withdraw_offer: Failed - {json_data.get('error', {}).get('message', 'Unknown error')}"
    print(f"test_06_withdraw_offer: Passed. Offer for {TEST_SKU} withdrawn.")

    # Verification: Try to get the offer again, it should ideally show as not published or have a different status
    withdrawn_offer_details = await _get_offer_details(mcp_client, TEST_SKU)
    assert withdrawn_offer_details is not None, "test_06_withdraw_offer: Failed - Could not re-fetch offer after withdrawal."
    # Check if listingId is gone or status changed (eBay specific)
    # This assertion depends on how eBay represents a withdrawn offer. It might still exist but be inactive.
    is_still_published = withdrawn_offer_details.get('offerState') == 'PUBLISHED' or \
                         (withdrawn_offer_details.get('listing') and withdrawn_offer_details['listing'].get('listingId'))
    assert not is_still_published, "test_06_withdraw_offer: Failed - Offer still appears to be published after withdrawal."
    print(f"test_06_withdraw_offer: Verification of withdrawal passed. Offer state: {withdrawn_offer_details.get('offerState')}")
