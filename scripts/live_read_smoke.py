"""Read-only production smoke test for seller OAuth and UK inventory access."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ebay_service import get_ebay_access_token  # noqa: E402
from utils.api_utils import get_standard_ebay_headers, is_token_error  # noqa: E402


async def main() -> None:
    if os.getenv("EBAY_MARKETPLACE_ID", "EBAY_GB") != "EBAY_GB":
        raise SystemExit("Refusing smoke test because EBAY_MARKETPLACE_ID is not EBAY_GB.")

    token = await get_ebay_access_token()
    if is_token_error(token):
        raise SystemExit("Seller OAuth token acquisition failed.")

    url = "https://api.ebay.com/sell/inventory/v1/inventory_item"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            url,
            headers=get_standard_ebay_headers(token),
            params={"limit": 1},
        )
        response.raise_for_status()

    payload = response.json()
    print(
        "Read-only eBay GB seller smoke passed: "
        f"HTTP {response.status_code}, total inventory items {payload.get('total', 'unknown')}."
    )


if __name__ == "__main__":
    asyncio.run(main())
