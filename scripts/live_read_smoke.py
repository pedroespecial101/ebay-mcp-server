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
from ebay_mcp.trading.client import TradingClient  # noqa: E402
from ebay_mcp.trading.service import get_item, get_recent_seller_listings  # noqa: E402
from models.ebay.trading import RecentSellerListingsInput  # noqa: E402
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

        trading = TradingClient(client=client, access_token=token)
        recent = await get_recent_seller_listings(
            RecentSellerListingsInput(lookback_days=7, page_size=5, page_number=1),
            trading,
        )
        inspected = await get_item(recent.listings[0].item_id, trading) if recent.listings else None
        if inspected and not inspected.supported_for_revision:
            raise SystemExit(
                "Recent-listing discovery returned a candidate that GetItem rejected: "
                + ", ".join(inspected.restrictions)
            )

    payload = response.json()
    print(
        "Read-only eBay GB seller smoke passed: "
        f"HTTP {response.status_code}, total inventory items {payload.get('total', 'unknown')}, "
        f"recent Trading takeover candidates {len(recent.listings)}, "
        f"GetItem inspection {'passed' if inspected and inspected.revision_token else 'not applicable'}."
    )


if __name__ == "__main__":
    asyncio.run(main())
