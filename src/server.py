from fastmcp import FastMCP
import httpx
from dotenv import load_dotenv
from ebay_service import get_ebay_access_token

load_dotenv()

# Create an MCP server
mcp = FastMCP("Ebay API")


# Add an addition tool
@mcp.tool()
async def test_auth() -> str:
    """Test authentication and token retrieval"""
    token = await get_ebay_access_token()
    if token == "No access token found":
        return "No access token found. Please check your credentials."
    
    # Return first 50 chars of token and the length
    return f"Token found (first 50 chars): {token[:50]}\nToken length: {len(token)}"

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a tool to search eBay items using Browse API
@mcp.tool()
async def search_ebay_items(query: str, limit: int = 10) -> str:
    """Search items on eBay using Browse API"""
    async with httpx.AsyncClient() as client:
        token = await get_ebay_access_token()
        if token == "No access token found":
            return "Failed to get access token. Please check your credentials."

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {"q": query, "limit": limit}
        try:
            response = await client.get(
                "https://api.ebay.com/buy/browse/v1/item_summary/search",
                headers=headers,
                params=params,
            )
            if response.status_code != 200:
                return f"eBay API request failed with status code {response.status_code}: {response.text}"
            return response.text
        except Exception as e:
            return f"Error occured when eBay API request: {e}"

@mcp.tool()
async def get_category_suggestions(query: str) -> str:
    """Get category suggestions from eBay Taxonomy API for the UK catalogue."""
    async with httpx.AsyncClient() as client:
        token = await get_ebay_access_token()
        if token == "No access token found":
            return "Failed to get access token. Please check your credentials."

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {"q": query}
        try:
            response = await client.get(
                "https://api.ebay.com/commerce/taxonomy/v1/category_tree/3/get_category_suggestions",
                headers=headers,
                params=params,
            )
            if response.status_code != 200:
                return f"eBay Taxonomy API request failed with status code {response.status_code}: {response.text}"
            return response.text
        except Exception as e:
            return f"Error occurred when eBay Taxonomy API request: {e}"

@mcp.tool()
async def get_item_aspects_for_category(category_id: str) -> str:
    """Get item aspects for a specific category from eBay Taxonomy API.
    
    Args:
        category_id: The eBay category ID to get aspects for.
    """
    async with httpx.AsyncClient() as client:
        token = await get_ebay_access_token()
        if token == "No access token found":
            return "Failed to get access token. Please check your credentials."

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            response = await client.get(
                f"https://api.ebay.com/commerce/taxonomy/v1/category_tree/3/get_item_aspects_for_category",
                headers=headers,
                params={"category_id": category_id},
            )
            if response.status_code != 200:
                return f"eBay Taxonomy API request failed with status code {response.status_code}: {response.text}"
            return response.text
        except Exception as e:
            return f"Error occurred when fetching category aspects: {e}"

@mcp.tool()
async def get_offer_by_sku(sku: str) -> str:
    """Get offer details for a specific SKU from eBay Sell Inventory API.
    
    Args:
        sku: The seller-defined SKU (Stock Keeping Unit) of the offer.
    """
    async with httpx.AsyncClient() as client:
        token = await get_ebay_access_token()
        if token == "No access token found":
            return "Failed to get access token. Please check your credentials."

        # Get the app ID from environment variables
        app_id = os.getenv("EBAY_APP_ID", "")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",  # UK marketplace
            "X-EBAY-C-ENDUSERCTX": f"affiliateCampaignId=<e9e5b23f2c3d4f8a9f5c6d7e8f9a0b1>,affiliateReferenceId=<123456789>",
        }
        
        # For debugging
        print(f"Using token: {token[:20]}...")
        print(f"Using app ID: {app_id}")
        print(f"Full headers: {headers}")
        print(f"Request URL: https://api.ebay.com/sell/inventory/v1/offer?sku={sku}")
        
        try:
            # First, try with the SKU in the query parameters
            print("Attempting direct offer lookup by SKU...")
            response = await client.get(
                "https://api.ebay.com/sell/inventory/v1/offer",
                headers=headers,
                params={"sku": sku},
            )
            
            print(f"Direct lookup status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            # If that fails, try getting the offer ID first
            if response.status_code == 403:
                print("Trying alternative approach with offer ID lookup...")
                offers_response = await client.get(
                    "https://api.ebay.com/sell/inventory/v1/offer",
                    headers=headers,
                    params={"sku": sku, "limit": 1},
                )
                
                print(f"Offer list status: {offers_response.status_code}")
                print(f"Offer list response: {offers_response.text[:500]}...")  # First 500 chars
                
                if offers_response.status_code == 200:
                    offers = offers_response.json()
                    print(f"Parsed offers: {offers}")
                    
                    if offers.get('offers') and len(offers['offers']) > 0:
                        offer_id = offers['offers'][0]['offerId']
                        print(f"Found offer ID: {offer_id}")
                        
                        # Now get the offer details with the offer ID
                        response = await client.get(
                            f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}",
                            headers=headers,
                        )
                        print(f"Offer details status: {response.status_code}")
                        print(f"Offer details response: {response.text[:500]}...")
                    else:
                        print("No offers found in the response")
                        return "No offers found for the specified SKU"
                else:
                    print(f"Failed to list offers: {offers_response.text}")
            
            if response.status_code != 200:
                error_msg = f"eBay Sell Inventory API request failed with status code {response.status_code}: {response.text}"
                print(error_msg)
                return error_msg
                
            return response.text
            
        except Exception as e:
            return f"Error occurred when fetching offer by SKU: {str(e)}"


if __name__ == "__main__":
    print("Starting FastMCP server with stdio transport...")
    print("To test authentication, use the MCP client to call the 'test_auth' function")
    mcp.run()
