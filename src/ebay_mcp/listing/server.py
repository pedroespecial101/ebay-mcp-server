"""High-level listing MCP tools."""

from fastmcp import FastMCP

from ebay_mcp.listing.workflow import create_listing, discard_draft, publish_listing, validate_listing
from models.ebay.listing_workflow import DiscardDraftInput, ListingValidationResult, ListingWorkflowResult, PublishListingInput, SimpleListingInput

listing_mcp = FastMCP("eBay streamlined listing workflow")


@listing_mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
async def validate(input: SimpleListingInput) -> ListingValidationResult:
    """Validate category, condition, aspects and staged images without changing eBay."""
    return await validate_listing(input)


@listing_mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True})
async def create(input: SimpleListingInput) -> ListingWorkflowResult:
    """Create or resume a verified eBay UK draft, optionally publishing only when estimated fees are zero."""
    return await create_listing(input)


@listing_mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True})
async def publish(input: PublishListingInput) -> ListingWorkflowResult:
    """Publish one verified draft when its estimated fee does not exceed the explicit ceiling."""
    return await publish_listing(input)


@listing_mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True})
async def discard_draft(input: DiscardDraftInput) -> ListingWorkflowResult:
    """Delete an unpublished offer then its inventory item; refuse published or ambiguous states."""
    return await discard_draft(input)
