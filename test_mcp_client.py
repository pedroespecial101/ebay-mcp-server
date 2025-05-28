import asyncio
import json
import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCPClient

async def test_get_offer_by_sku():
    # Create an MCP client
    client = FastMCPClient("Ebay API Client")
    
    try:
        # Test get_offer_by_sku
        print("Testing get_offer_by_sku with SKU: Tank-5")
        result = await client.call("get_offer_by_sku", sku="Tank-5")
        print("Result:", json.dumps(json.loads(result), indent=2))
        
    finally:
        # Close the client
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_get_offer_by_sku())
