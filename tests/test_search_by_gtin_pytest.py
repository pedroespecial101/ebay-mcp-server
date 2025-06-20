"""
Tests for the eBay Catalog search_by_gtin MCP tool.
"""
import pytest
import pytest_asyncio
import json
from fastmcp import Client

test_gtin = "8000070052628"

@pytest_asyncio.fixture
async def mcp_client():
    """Fixture to provide MCP client connection"""
    async with Client("src/main_server.py") as client:
        yield client

def is_error_response(response_text):
    """Check if the response indicates an error"""
    try:
        json_data = json.loads(response_text)
        return not json_data.get("success", True)
    except json.JSONDecodeError:
        return any(term in response_text.lower() for term in ["error", "validation", "invalid"])

@pytest.mark.asyncio
async def test_search_by_gtin_valid(mcp_client):
    """Test search by GTIN with a valid GTIN number (ISBN for 'To Kill a Mockingbird')"""
    # Call the catalogAPI_search_by_gtin tool
    result = await mcp_client.call_tool("catalogAPI_search_by_gtin", {
        "gtin": test_gtin
    })
    
    # Parse the response
    response_text = result[0].text
    
    # Check if the response is an error
    assert not is_error_response(response_text), f"Expected successful response, got error: {response_text}"
    
    # Parse as JSON
    json_data = json.loads(response_text)
    
    # Assert the response structure
    assert isinstance(json_data, dict), "Response should be a JSON object"
    assert json_data.get("success") is True, "Response should indicate success"
    assert "message" in json_data, "Response should contain a 'message'"
    assert "status_code" in json_data, "Response should contain a 'status_code'"
    
    # If product data is returned (not guaranteed if no matching products)
    if "productData" in json_data and json_data["productData"]:
        product_data = json_data["productData"]
        
        # Verify product data structure if products were found
        if "productSummaries" in product_data and product_data["productSummaries"]:
            product = product_data["productSummaries"][0]
            assert "epid" in product, "Product should have an 'epid'"
            assert "title" in product, "Product should have a 'title'"
            
            # Check for expected GTIN in returned data
            if "gtin" in product and product["gtin"]:
                # The GTIN we searched for should be in the returned GTINs
                # Note: eBay might normalize or convert the GTIN format
                assert any(test_gtin in gtin for gtin in product["gtin"]), \
                    f"Searched GTIN '{test_gtin}' not found in returned GTINs: {product['gtin']}"

@pytest.mark.asyncio
async def test_search_by_gtin_no_results(mcp_client):
    """Test search by GTIN with a valid but non-existent GTIN that should return no results"""
    # Use a GTIN format that's valid but unlikely to exist
    fake_gtin = "0000000000001"
    
    # Call the catalogAPI_search_by_gtin tool
    result = await mcp_client.call_tool("catalogAPI_search_by_gtin", {
        "gtin": fake_gtin
    })
    
    # Parse the response
    response_text = result[0].text
    
    # The response should still be successful even with no results
    json_data = json.loads(response_text)
    
    # Assert the response indicates success (API call worked)
    assert json_data.get("success") is True, "Response should indicate success"
    
    # Check that the message indicates no products were found
    assert "no product" in json_data.get("message", "").lower() or \
           "no matching" in json_data.get("message", "").lower() or \
           "0 product" in json_data.get("message", "").lower(), \
        f"Message should indicate no products found, got: {json_data.get('message')}"
    
    # Product data should either be missing, null, or have empty productSummaries
    if "productData" in json_data and json_data["productData"]:
        product_data = json_data["productData"]
        if "productSummaries" in product_data:
            assert len(product_data["productSummaries"]) == 0, \
                "Product summaries should be empty for non-existent GTIN"

@pytest.mark.asyncio
async def test_search_by_gtin_invalid_empty(mcp_client):
    """Test search with an empty GTIN should return an error"""
    result = await mcp_client.call_tool("catalogAPI_search_by_gtin", {
        "gtin": ""
    })
    
    # Parse the response
    response_text = result[0].text
    
    # Check that the response indicates an error
    assert is_error_response(response_text), \
        f"Expected error response for empty GTIN, got: {response_text}"
    
    # Parse as JSON
    json_data = json.loads(response_text)
    
    # Assert that success is False for an error response
    assert json_data.get("success") is False, "Response should indicate failure"
    
    # Check for appropriate error message
    assert any(term in json_data.get("message", "").lower() for term in [
        "empty", "invalid", "gtin cannot be empty"
    ]), f"Expected validation error message for empty GTIN, got: {json_data.get('message')}"

@pytest.mark.asyncio
async def test_search_by_gtin_invalid_format(mcp_client):
    """Test search with an invalid GTIN format should return an error"""
    # Use a GTIN with invalid characters
    result = await mcp_client.call_tool("catalogAPI_search_by_gtin", {
        "gtin": "ABC123XYZ"  # Invalid format with letters
    })
    
    # Parse the response
    response_text = result[0].text
    json_data = json.loads(response_text)
    
    # For invalid format, we might get either a validation error or an API error
    # Regardless, the response should indicate some kind of issue
    
    # Either the request fails validation, or the API returns an error
    assert is_error_response(response_text) or \
           "invalid" in json_data.get("message", "").lower() or \
           "error" in json_data.get("message", "").lower(), \
        f"Expected error or warning for invalid GTIN format, got: {json_data.get('message')}"
