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
    """Inspect seller-listing photographs as safe MCP images.

    Returns one image by default and at most three per response. All listing
    photographs remain available: follow has_more and next_start_index with
    repeated calls until the complete ordered set has been reviewed. Use
    max_px=768 first and retry max_px=512 if a client blocks an image.
    """
    result = await fetch_item_images(input)
    next_index = result.start_index + len(result.images)
    successful = [image for image in result.images if image.data is not None]
    metadata = {
        "item_id": result.item_id,
        "total_images": result.total_images,
        "start_index": result.start_index,
        "attempted_count": len(result.images),
        "returned_count": len(successful),
        "next_start_index": next_index if next_index < result.total_images else None,
        "has_more": next_index < result.total_images,
        "images": [
            {
                "index": image.index,
                "status": "ok" if image.data is not None else "failed",
                "width": image.width,
                "height": image.height,
                "error_code": image.error_code,
            }
            for image in result.images
        ],
    }
    content = [TextContent(
        type="text",
        text=f"Listing photographs {result.start_index + 1}-{next_index} of {result.total_images}.",
    )]
    for image in result.images:
        if image.data is None:
            content.append(TextContent(
                type="text",
                text=f"Photograph {image.index + 1} could not be prepared; continue with the remaining images.",
            ))
            continue
        content.append(TextContent(
            type="text",
            text=f"Photograph {image.index + 1} of {result.total_images}.",
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
