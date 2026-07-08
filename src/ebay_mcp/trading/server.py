"""MCP tools for active-listing takeover and direct Trading listings."""

from fastmcp import FastMCP
from fastmcp.tools.base import ToolResult
from fastmcp.utilities.types import Image
from mcp.types import TextContent

from ebay_mcp.trading.service import (
    add_fixed_price_item as add_listing,
    get_item as fetch_item,
    get_recent_seller_listings as fetch_recent,
    revise_fixed_price_item as revise_listing,
    upload_listing_pictures as upload_pictures,
    verify_add_fixed_price_item as verify_listing,
    view_item_images as fetch_item_images,
)
from models.ebay.trading import (
    AddFixedPriceItemInput, AddFixedPriceItemResult, EditableSellerListing,
    GetSellerItemInput, RecentSellerListingsInput, RecentSellerListingsResult,
    ReviseFixedPriceItemInput, ReviseFixedPriceItemResult, UploadListingPicturesInput,
    UploadedListingPicture, VerifyAddFixedPriceItemInput, VerifyAddFixedPriceItemResult,
    ViewItemImagesInput,
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


@trading_mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
async def view_item_images(input: ViewItemImagesInput) -> ToolResult:
    """Return seller-listing photographs as vision-readable MCP images for identification and condition review."""
    result = await fetch_item_images(input)
    next_index = result.start_index + len(result.images)
    metadata = {
        "item_id": result.item_id,
        "title": result.title,
        "total_images": result.total_images,
        "start_index": result.start_index,
        "returned_count": len(result.images),
        "next_start_index": next_index if next_index < result.total_images else None,
        "has_more": next_index < result.total_images,
        "images": [
            {"index": image.index, "url": image.url, "width": image.width, "height": image.height}
            for image in result.images
        ],
    }
    content = [TextContent(
        type="text",
        text=f"{result.title} — showing photographs {result.start_index + 1}-{next_index} of {result.total_images}.",
    )]
    for image in result.images:
        content.append(TextContent(
            type="text",
            text=f"Photograph {image.index + 1} of {result.total_images}: {image.url}",
        ))
        content.append(Image(data=image.data, format="jpeg").to_image_content())
    return ToolResult(content=content, structured_content=metadata)


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
