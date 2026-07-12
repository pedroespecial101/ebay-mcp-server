from __future__ import annotations

from fastmcp import FastMCP

from .client import EbayClient
from .models import (
    BuyingOption,
    ImageSearchRequest,
    ItemDetail,
    SearchRequest,
    SearchResponse,
    SortOrder,
    VehicleCompatibility,
)

SERVER_INSTRUCTIONS = """
Read-only research access to live eBay listings, defaulting to ebay.co.uk.
Prices are current asking prices or auction bids. They are not completed-sale
prices and must not be described as sold comparables. Use search_items to find
listings and get_item for full details. search_by_image finds visually similar
live listings for an unidentified part; it does not display image pixels.
Vehicle compatibility reflects eBay's EXACT or POSSIBLE result and should not
be overstated.
""".strip()


def create_server(client: EbayClient | None = None) -> FastMCP:
    ebay = client or EbayClient()
    server = FastMCP(
        "eBay UK Browse",
        instructions=SERVER_INSTRUCTIONS,
    )

    @server.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True}
    )
    async def search_items(
        query: str | None = None,
        gtin: str | None = None,
        category_ids: list[str] | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        condition_ids: list[str] | None = None,
        buying_options: list[BuyingOption] | None = None,
        item_location_country: str | None = None,
        search_in_description: bool = False,
        aspect_filters: dict[str, list[str]] | None = None,
        vehicle: VehicleCompatibility | None = None,
        sort: SortOrder = SortOrder.BEST_MATCH,
        include_refinements: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """Search live eBay listings and asking prices, not completed/sold items.

        Supply exactly one of query or GTIN. Category, aspect, vehicle-fitment,
        price, condition, buying-format, location, sorting, and pagination filters
        are supported. An aspect or vehicle search requires exactly one category ID.
        """
        request = SearchRequest(
            query=query,
            gtin=gtin,
            category_ids=category_ids or [],
            min_price=min_price,
            max_price=max_price,
            condition_ids=condition_ids or [],
            buying_options=buying_options or [],
            item_location_country=item_location_country,
            search_in_description=search_in_description,
            aspect_filters=aspect_filters or {},
            vehicle=vehicle,
            sort=sort,
            include_refinements=include_refinements,
            limit=limit,
            offset=offset,
        )
        return await ebay.search_items(request)

    @server.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True}
    )
    async def get_item(item_id: str) -> ItemDetail:
        """Get compact details for one live eBay item; this is not sold-history data."""
        return await ebay.get_item(item_id)

    @server.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True}
    )
    async def search_by_image(
        image_url: str,
        category_id: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        condition_ids: list[str] | None = None,
        buying_options: list[BuyingOption] | None = None,
        item_location_country: str | None = None,
        aspect_filters: dict[str, list[str]] | None = None,
        include_refinements: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """Find visually similar live listings from a public HTTPS image URL.

        This sends the supplied image to eBay's visual-search service and returns
        matching listing data. It does not return image pixels for model vision,
        and it is not a sold-comparables search.
        """
        request = ImageSearchRequest(
            image_url=image_url,
            category_id=category_id,
            min_price=min_price,
            max_price=max_price,
            condition_ids=condition_ids or [],
            buying_options=buying_options or [],
            item_location_country=item_location_country,
            aspect_filters=aspect_filters or {},
            include_refinements=include_refinements,
            limit=limit,
            offset=offset,
        )
        return await ebay.search_by_image(request)

    return server


research_mcp = create_server()
