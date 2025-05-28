import asyncio
import os
import sys

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ebay_service import get_ebay_access_token

async def test_get_offer_by_sku(sku):
    from src.server import get_offer_by_sku
    print(f"Testing get_offer_by_sku with SKU: {sku}")
    result = await get_offer_by_sku(sku)
    print("Result:", result)
    return result

if __name__ == "__main__":
    import sys
    sku = sys.argv[1] if len(sys.argv) > 1 else "Tank-5"
    asyncio.run(test_get_offer_by_sku(sku))
