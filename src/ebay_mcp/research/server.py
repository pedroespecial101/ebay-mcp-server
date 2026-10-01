from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from fastmcp import FastMCP

from ebay_mcp.media.storage import get_staged_bytes
from ebay_mcp.research.key_cohort import compare_key_cohorts

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
    async def snapshot_key_cohort(
        series: str,
        exact_codes: list[str],
        maker: str | None = None,
        own_listing_ids: list[str] | None = None,
        per_query_limit: int = 30,
    ) -> dict:
        """Take a dated, parent-deduplicated snapshot of live UK key competitors.

        Exact-code matches are title/aspect candidates until a human verifies
        the physical key and variation. A live parent's cumulative sold count
        is only a historical signal, never same-code or recent sold evidence.
        """
        series = series.strip().upper()
        exact_codes = [code.strip().upper() for code in exact_codes]
        if not re.fullmatch(r"[A-Z]{1,5}", series):
            raise ValueError("series must be a short alphabetic key prefix.")
        if len(exact_codes) > 10 or any(not re.fullmatch(r"[A-Z]{1,5}[0-9]{1,5}", code) for code in exact_codes):
            raise ValueError("Provide at most ten exact alphanumeric key codes.")
        if not 1 <= per_query_limit <= 50:
            raise ValueError("per_query_limit must be 1-50.")
        normalized_maker = maker.strip() if maker and maker.strip() else None
        normalized_own = sorted({str(item).strip() for item in (own_listing_ids or []) if str(item).strip()})
        own = set(normalized_own)
        queries = [f"{series} classic car key"] + [
            f"{code} {normalized_maker or ''} original key".strip() for code in exact_codes
        ]
        query_log = []
        parents = {}
        for query in queries:
            response = await ebay.search_items(SearchRequest(
                query=query, item_location_country="GB", limit=per_query_limit,
            ))
            query_log.append({"query": query, "result_total": response.total,
                              "returned": len(response.items),
                              "capped": response.total > len(response.items)})
            for item in response.items:
                parent_id = item.legacy_item_id or item.item_id
                if parent_id in own:
                    continue
                if parent_id not in parents:
                    parents[parent_id] = {"parent_item_id": parent_id,
                                          "browse_item_id": item.item_id,
                                          "matched_queries": [], "title": item.title,
                                          "asking_price": item.price.model_dump() if item.price else None,
                                          "item_creation_date": item.item_creation_date,
                                          "quantity_sold": None}
                parents[parent_id]["matched_queries"].append(query)
        enrichment_failures = []
        for parent in list(parents.values())[:25]:
            try:
                detail = await ebay.get_item(parent["browse_item_id"])
            except Exception:
                enrichment_failures.append(parent["parent_item_id"])
                continue
            parent["quantity_sold"] = detail.quantity_sold
            parent["shipping"] = [entry.model_dump() for entry in detail.shipping]
            parent["condition"] = detail.condition
            parent["seller"] = detail.seller.username if detail.seller else None
            parent["item_creation_date"] = detail.item_creation_date or parent["item_creation_date"]
            parent["url"] = detail.url
            searchable = " ".join([detail.title, detail.description or ""] + [
                str(value) for values in detail.aspects.values() for value in values
            ]).upper()
            parent["possible_exact_codes"] = [
                code for code in exact_codes if re.search(rf"(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])", searchable)
            ]
        return {
            "source": "eBay Browse active UK listings", "captured_at": datetime.now(timezone.utc).isoformat(),
            "series": series, "exact_codes_requested": exact_codes, "maker": normalized_maker,
            "search_config": {
                "series": series,
                "exact_codes": sorted(set(exact_codes)),
                "maker": normalized_maker.casefold() if normalized_maker else None,
                "excluded_own_listing_ids": normalized_own,
                "per_query_limit": per_query_limit,
            },
            "query_log": query_log, "parent_count": len(parents),
            "parents": list(parents.values()), "enrichment_failures": enrichment_failures,
            "enrichment_cap": 25,
            "limitations": [
                "Asking prices are not realised sale prices.",
                "quantity_sold is cumulative for a live parent, not recent or variation-level sales.",
                "A possible exact-code match requires human review of variation and physical form.",
            ],
        }

    @server.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True}
    )
    async def compare_key_cohort_snapshots(previous: dict, current: dict) -> dict:
        """Compare two dated snapshots; cumulative-sold growth is an activity proxy only."""
        return compare_key_cohorts(previous, current)

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

    @server.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True}
    )
    async def search_by_staged_image(
        image_ref: str,
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
        """Find live visual matches from a private media staging reference.

        The trusted server reads the private staged bytes and sends them directly
        to eBay Browse. No public source-image URL is created and no image bytes
        are returned to the MCP caller.
        """
        image, _ = await asyncio.to_thread(get_staged_bytes, image_ref)
        request = ImageSearchRequest(
            image_url="https://private-staged-image.invalid/source.jpg",
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
        return await ebay.search_by_image_bytes(request, image)

    return server


research_mcp = create_server()
