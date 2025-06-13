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
    return any(term in response_text.lower() for term in ["error", "validation", "invalid"])

@pytest.mark.asyncio
async def test_search_items_basic(mcp_client):
    """Test basic search functionality with 'trainers' query"""
    # Call the browseAPI_search_ebay_items tool
    result = await mcp_client.call_tool("browseAPI_search_ebay_items", {
        "query": "trainers",
        "limit": 5
    })
    
    # Parse the response
    response_text = result[0].text
    
    # Check if the response is an error
    assert not is_error_response(response_text), f"Expected successful response, got error: {response_text}"
    
    # Parse as JSON
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

@pytest.mark.asyncio
async def test_search_items_custom_limit(mcp_client):
    """Test search with a custom limit"""
    # Call the browseAPI_search_ebay_items tool with custom limit
    result = await mcp_client.call_tool("browseAPI_search_ebay_items", {
        "query": "trainers",
        "limit": 3
    })
    
    # Parse the response
    response_text = result[0].text
    
    # Check if the response is an error
    assert not is_error_response(response_text), f"Expected successful response, got error: {response_text}"
    
    # Parse as JSON
    json_data = json.loads(response_text)
    
    # Verify the number of results doesn't exceed the limit
    assert len(json_data.get("itemSummaries", [])) <= 3, "Should return no more than 3 items"

@pytest.mark.asyncio
async def test_search_items_empty_query(mcp_client):
    """Test search with an empty query should return an error"""
    result = await mcp_client.call_tool("browseAPI_search_ebay_items", {
        "query": "",
        "limit": 5
    })
    
    # Check that the response indicates an error
    response_text = result[0].text
    assert is_error_response(response_text), f"Expected error response for empty query, got: {response_text}"
    
    # Check for either the Pydantic validation error or the eBay API error
    assert any(term in response_text.lower() for term in [
        "validation", "invalid", "empty", 
        "must have a valid 'q'", "query parameter"
    ]), f"Expected validation error or eBay API error for empty query, got: {response_text}"

@pytest.mark.asyncio
async def test_search_items_invalid_limit(mcp_client):
    """Test search with invalid limit should return an error"""
    result = await mcp_client.call_tool("browseAPI_search_ebay_items", {
        "query": "trainers",
        "limit": 0
    })
    
    # Check that the response indicates an error
    response_text = result[0].text
    assert is_error_response(response_text), f"Expected error response for invalid limit, got: {response_text}"
    
    # Check that the error message contains validation-related text
    assert any(term in response_text.lower() for term in ["validation", "invalid", "positive"]), \
        f"Expected validation error for invalid limit, got: {response_text}"
