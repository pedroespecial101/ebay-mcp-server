import asyncio
import os
import sys

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ebay_service import get_ebay_access_token

async def test_auth():
    from src.server import test_auth
    print(f"Testing test_auth MCP tool.")
    result = await test_auth()
    print("Result:", result)
    return result

if __name__ == "__main__":
    import sys
    asyncio.run(test_auth())
