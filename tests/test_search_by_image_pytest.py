import pytest
import pytest_asyncio
import json
from fastmcp import Client

@pytest_asyncio.fixture
async def mcp_client():
    """Fixture to provide MCP client connection"""
    async with Client("src/main_server.py") as client:
        yield client

def is_error_response(response_text):
    """Check if the response indicates an error"""
    return any(term in response_text.lower() for term in ["error", "validation", "invalid", "failed"])

@pytest.mark.asyncio
async def test_search_by_image_basic(mcp_client):
    """Test basic search_by_image functionality with a sample image URL"""
    # Call the browseAPI_search_by_image tool with a test image URL
    result = await mcp_client.call_tool("browseAPI_search_by_image", {
        "params": {
            "image_url": "https://ebayimages.s3.us-east-005.backblazeb2.com/ebay_images/IMAGE-TEST01/IMAGE-TEST01-1_251.jpg",
            "limit": 5
        }
    })
    
    # Print the response for debugging
    response_text = result.content[0].text
    print(f"Response from search_by_image: {response_text}")
    
    # Check if the response is an error
    assert not is_error_response(response_text), f"Expected successful response, got error: {response_text}"
    
    # Try to parse as JSON (may fail if response is not valid JSON)
    try:
        json_data = json.loads(response_text)
        
        # Assert the response structure
        assert isinstance(json_data, dict), "Response should be a JSON object"
        assert "itemSummaries" in json_data, "Response should contain 'itemSummaries'"
        assert isinstance(json_data["itemSummaries"], list), "'itemSummaries' should be a list"
        
        # Verify we got some results (could be 0 or more)
        assert len(json_data["itemSummaries"]) <= 5, "Should return no more than the limit of 5 items"
        
        # If we have results, verify they contain expected fields
        if json_data["itemSummaries"]:
            item = json_data["itemSummaries"][0]
            assert "itemId" in item, "Item should have an 'itemId'"
            assert "title" in item, "Item should have a 'title'"
            assert "price" in item, "Item should have a 'price'"
            assert "itemWebUrl" in item, "Item should have a 'itemWebUrl'"
    except json.JSONDecodeError:
        # If response is not JSON, it's likely an error message
        assert False, f"Response is not valid JSON: {response_text}"

@pytest.mark.asyncio
async def test_search_by_image_invalid_url(mcp_client):
    """Test search_by_image with an invalid image URL"""
    # Call the browseAPI_search_by_image tool with an invalid URL
    result = await mcp_client.call_tool("browseAPI_search_by_image", {
        "image_url": "not_a_valid_url",
        "limit": 5
    })
    
    # Print the response for debugging
    response_text = result.content[0].text
    print(f"Response from search_by_image with invalid URL: {response_text}")
    
    # Check that the response indicates an error
    assert is_error_response(response_text), f"Expected error response for invalid URL, got: {response_text}"

@pytest.mark.asyncio
async def test_search_by_image_non_image_url(mcp_client):
    """Test search_by_image with a URL that doesn't point to an image"""
    # Call the browseAPI_search_by_image tool with a non-image URL
    result = await mcp_client.call_tool("browseAPI_search_by_image", {
        "image_url": "https://www.ebay.com",
        "limit": 5
    })
    
    # Print the response for debugging
    response_text = result.content[0].text
    print(f"Response from search_by_image with non-image URL: {response_text}")
    
    # Check that the response indicates an error
    assert is_error_response(response_text), f"Expected error response for non-image URL, got: {response_text}"

@pytest.mark.asyncio
async def test_search_by_image_with_category(mcp_client):
    """Test search_by_image with category filtering"""
    # Use a valid electronics category ID for testing
    category_id = "9355" # Example category ID for electronics
    
    # Call the browseAPI_search_by_image tool with category filtering
    result = await mcp_client.call_tool("browseAPI_search_by_image", {
        "image_url": "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/TXA036TT/TXA036TT-1_250.jpg",
        "category_ids": category_id,
        "limit": 5
    })
    
    # Print the response for debugging
    response_text = result.content[0].text
    print(f"Response from search_by_image with category: {response_text}")
    
    # Check if the response is an error
    assert not is_error_response(response_text), f"Expected successful response, got error: {response_text}"
    
    try:
        # Parse as JSON
        json_data = json.loads(response_text)
        
        # Basic validation of response structure
        assert isinstance(json_data, dict), "Response should be a JSON object"
        assert "itemSummaries" in json_data, "Response should contain 'itemSummaries'"
        
    except json.JSONDecodeError:
        assert False, f"Response is not valid JSON: {response_text}"
