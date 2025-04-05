from fastmcp import FastMCP
import httpx
from dotenv import load_dotenv
from ebay_service import get_ebay_access_token

load_dotenv()

# Create an MCP server
mcp = FastMCP("Ebay API")


# Add an addition tool
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
