"""Read-only seller analytics, promotion and order-line MCP tools."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from ebay_mcp.insights.client import SellerInsightsClient
from ebay_mcp.insights.service import (
    fetch_ad_report as fetch_ad_report_data,
    get_key_order_lines as fetch_key_order_lines,
    get_promotion_inventory,
    get_traffic_report as fetch_traffic_report,
    start_ad_report,
)


class TrafficReportInput(BaseModel):
    start_date: date
    end_date: date
    dimension: Literal["LISTING", "DAY"] = "LISTING"
    listing_ids: list[str] = Field(default_factory=list, max_length=50)


class KeyOrderLinesInput(BaseModel):
    start_date: date
    end_date: date
    listing_ids: list[str] = Field(min_length=1, max_length=100)


class PromotionPerformanceInput(BaseModel):
    stage: Literal["inventory", "start_ad_report", "fetch_ad_report"] = "inventory"
    listing_ids: list[str] = Field(min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    campaign_ids: list[str] = Field(default_factory=list)
    funding_model: Literal["COST_PER_SALE", "COST_PER_CLICK"] = "COST_PER_SALE"
    report_task_id: str | None = None


insights_mcp = FastMCP("eBay seller performance reads")


@insights_mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
async def get_traffic_report(input: TrafficReportInput) -> dict:
    """Read eBay UK listing-level or account-day traffic; never infer variation-level views."""
    async with SellerInsightsClient() as client:
        return await fetch_traffic_report(
            client, start=input.start_date, end=input.end_date,
            dimension=input.dimension, listing_ids=input.listing_ids,
        )


@insights_mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
async def get_key_order_lines(input: KeyOrderLinesInput) -> dict:
    """Read only matching key-listing order lines; omit buyers, addresses and payment details."""
    async with SellerInsightsClient() as client:
        return await fetch_key_order_lines(
            client, start=input.start_date, end=input.end_date, listing_ids=input.listing_ids,
        )


@insights_mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})
async def get_promotion_performance(input: PromotionPerformanceInput) -> dict:
    """Inspect ad/discount coverage or create/fetch a reporting-only Promoted Listings report.

    First use inventory to identify campaign IDs and paid versus buyer-facing
    discounts. For ad results, start_ad_report creates an eBay report task, then
    fetch_ad_report retrieves the completed task. No listing or campaign is changed.
    """
    async with SellerInsightsClient() as client:
        if input.stage == "inventory":
            return await get_promotion_inventory(client, listing_ids=input.listing_ids)
        if input.stage == "start_ad_report":
            if input.start_date is None or input.end_date is None:
                raise ValueError("start_ad_report requires start_date and end_date.")
            return await start_ad_report(
                client, start=input.start_date, end=input.end_date,
                listing_ids=input.listing_ids, campaign_ids=input.campaign_ids,
                funding_model=input.funding_model,
            )
        if not input.report_task_id:
            raise ValueError("fetch_ad_report requires report_task_id.")
        return await fetch_ad_report_data(
            client, task_id=input.report_task_id, listing_ids=input.listing_ids,
        )
