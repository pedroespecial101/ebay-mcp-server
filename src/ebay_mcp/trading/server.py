"""MCP tools for active-listing takeover and direct Trading listings."""

from fastmcp import FastMCP

from ebay_mcp.trading.service import (
    add_fixed_price_item as add_listing,
    get_item as fetch_item,
    get_recent_seller_listings as fetch_recent,
    revise_fixed_price_item as revise_listing,
    upload_listing_pictures as upload_pictures,
    verify_add_fixed_price_item as verify_listing,
)
from models.ebay.trading import (
    AddFixedPriceItemInput, AddFixedPriceItemResult, EditableSellerListing,
    GetSellerItemInput, RecentSellerListingsInput, RecentSellerListingsResult,
    ReviseFixedPriceItemInput, ReviseFixedPriceItemResult, UploadListingPicturesInput,
    UploadedListingPicture, VerifyAddFixedPriceItemInput, VerifyAddFixedPriceItemResult,
)

trading_mcp = FastMCP("eBay narrow Trading API")


@trading_mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
async def get_recent_seller_listings(input: RecentSellerListingsInput) -> RecentSellerListingsResult:
    """Find recently started active, quantity-one fixed-price seller listings suitable for takeover."""
    return await fetch_recent(input)


@trading_mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
async def get_item(input: GetSellerItemInput) -> EditableSellerListing:
    """Inspect one seller listing and return its editable state plus a concurrency revision token."""
    return await fetch_item(input.item_id)


@trading_mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True})
async def revise_fixed_price_item(input: ReviseFixedPriceItemInput) -> ReviseFixedPriceItemResult:
    """Revise an active UK quantity-one fixed-price listing after the human reviews the proposed diff."""
    return await revise_listing(input)


@trading_mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})
async def upload_listing_pictures(input: UploadListingPicturesInput) -> list[UploadedListingPicture]:
    """Upload privately staged images to EPS with the Media API; image bytes never enter model context."""
    return await upload_pictures(input.image_refs)


@trading_mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
async def verify_add_fixed_price_item(input: VerifyAddFixedPriceItemInput) -> VerifyAddFixedPriceItemResult:
    """Validate a quantity-one UK fixed-price proposal and estimate fees without creating a listing."""
    return await verify_listing(input.proposal)


@trading_mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True})
async def add_fixed_price_item(input: AddFixedPriceItemInput) -> AddFixedPriceItemResult:
    """Publish an unchanged verified proposal within its explicit listing-fee ceiling."""
    return await add_listing(input)
