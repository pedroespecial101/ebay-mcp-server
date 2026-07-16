"""Non-destructive smoke test for seller MCP tool discovery."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from fastmcp import Client


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {
    "auth_test_auth",
    "browseAPI_search_ebay_items",
    "browseAPI_search_by_image",
    "research_search_items",
    "research_get_item",
    "research_search_by_image",
    "research_search_by_staged_image",
    "taxonomyAPI_get_category_suggestions",
    "taxonomyAPI_get_item_aspects_for_category",
    "taxonomyAPI_get_item_condition_policies",
    "inventoryAPI_manage_offer",
    "inventoryAPI_manage_inventory_item",
    "catalogAPI_search_by_gtin",
    "media_open_image_uploader",
    "media_list_staged_images",
    "media_stage_images",
    "media_view_ebay_image",
    "listing_validate",
    "listing_create",
    "listing_publish",
    "listing_discard_draft",
    "trading_get_recent_seller_listings",
    "trading_get_item",
    "trading_view_item_images",
    "trading_revise_fixed_price_item",
    "trading_upload_listing_pictures",
    "trading_verify_add_fixed_price_item",
    "trading_add_fixed_price_item",
}
if os.getenv("EBAY_ENABLE_INTERACTIVE_AUTH", "1") == "1":
    EXPECTED_TOOLS.add("auth_trigger_ebay_login")

WRITE_TOOLS = {
    "inventoryAPI_manage_offer",
    "inventoryAPI_manage_inventory_item",
    "media_stage_images",
    "listing_create",
    "listing_publish",
    "listing_discard_draft",
    "trading_revise_fixed_price_item",
    "trading_add_fixed_price_item",
}


async def main() -> None:
    config = {
        "mcpServers": {
            "seller": {
                "command": sys.executable,
                "args": [str(ROOT / "src" / "main_server.py")],
                "env": dict(os.environ),
            }
        }
    }
    async with Client(config) as client:
        tools = await client.list_tools()

    discovered = {tool.name for tool in tools}

    missing = EXPECTED_TOOLS - discovered
    if missing:
        raise SystemExit(f"Missing expected seller MCP tools: {', '.join(sorted(missing))}")

    unexpected = discovered - EXPECTED_TOOLS
    if unexpected:
        raise SystemExit(f"Unexpected seller MCP tools: {', '.join(sorted(unexpected))}")

    for tool in tools:
        if tool.name in WRITE_TOOLS:
            if tool.annotations.readOnlyHint or not tool.annotations.destructiveHint:
                if tool.name != "media_stage_images":
                    raise SystemExit(f"Unsafe write annotations for {tool.name}")
                if tool.annotations.destructiveHint:
                    raise SystemExit(f"Unsafe staging annotations for {tool.name}")
        elif tool.name in {"media_open_image_uploader", "media_list_staged_images"}:
            continue
        elif tool.name == "trading_upload_listing_pictures":
            if tool.annotations.readOnlyHint or tool.annotations.destructiveHint:
                raise SystemExit("Unsafe Trading image-upload annotations")
        elif tool.name == "auth_trigger_ebay_login":
            if tool.annotations.readOnlyHint or tool.annotations.destructiveHint:
                raise SystemExit("Unsafe interactive-auth annotations")
        elif not tool.annotations.readOnlyHint:
            raise SystemExit(f"Missing read-only annotation for {tool.name}")

    print(f"Seller MCP discovery passed: {len(discovered)} tools available.")


if __name__ == "__main__":
    asyncio.run(main())
