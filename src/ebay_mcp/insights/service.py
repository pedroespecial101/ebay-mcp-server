"""Minimal, read-only projections of eBay seller reporting data."""

from __future__ import annotations

import csv
import gzip
import io
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from ebay_mcp.insights.client import SellerInsightsClient, SellerInsightsError

LONDON = ZoneInfo("Europe/London")
TRAFFIC_METRICS = (
    "LISTING_IMPRESSION_SEARCH_RESULTS_PAGE",
    "LISTING_VIEWS_SOURCE_SEARCH_RESULTS_PAGE",
    "LISTING_VIEWS_TOTAL",
    "TRANSACTION",
    "CLICK_THROUGH_RATE",
    "SALES_CONVERSION_RATE",
    "TOTAL_IMPRESSION_TOTAL",
)


def validate_window(start: date, end: date, *, max_days: int = 90) -> None:
    if end < start or end >= datetime.now(LONDON).date():
        raise ValueError("Use a completed date range ending before today.")
    if (end - start).days + 1 > max_days:
        raise ValueError(f"The requested range must be at most {max_days} days.")


def local_range(start: date, end: date) -> str:
    """Explicit UK offsets keep Seller Hub comparisons aligned across BST/GMT."""
    left = datetime.combine(start, time.min, LONDON).isoformat(timespec="milliseconds")
    right = datetime.combine(end, time(23, 59, 59, 999000), LONDON).isoformat(timespec="milliseconds")
    return f"[{left}..{right}]"


def utc_bounds(start: date, end: date) -> tuple[str, str]:
    left = datetime.combine(start, time.min, LONDON).astimezone(timezone.utc)
    right = datetime.combine(end + timedelta(days=1), time.min, LONDON).astimezone(timezone.utc)
    def fmt(value: datetime) -> str:
        return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return fmt(left), fmt(right)


async def get_traffic_report(
    client: SellerInsightsClient, *, start: date, end: date, dimension: str,
    listing_ids: list[str],
) -> dict[str, Any]:
    validate_window(start, end)
    if dimension not in {"LISTING", "DAY"}:
        raise ValueError("dimension must be LISTING or DAY.")
    if dimension == "LISTING" and not listing_ids:
        raise ValueError("LISTING reports require listing_ids.")
    if dimension == "DAY" and listing_ids:
        raise ValueError("DAY reports are account-level; omit listing_ids.")
    if len(listing_ids) > 50 or any(not item.isdecimal() for item in listing_ids):
        raise ValueError("Provide at most 50 numeric eBay listing IDs.")
    filters = ["marketplace_ids:{EBAY_GB}", f"date_range:{local_range(start, end)}"]
    if listing_ids:
        filters.insert(1, "listing_ids:{" + "|".join(dict.fromkeys(listing_ids)) + "}")
    payload = await client.get_json(
        "/sell/analytics/v1/traffic_report",
        params={"dimension": dimension, "filter": ",".join(filters), "metric": ",".join(TRAFFIC_METRICS)},
    )
    header = payload.get("header") or {}
    metric_keys = [metric.get("key") for metric in header.get("metrics", []) if isinstance(metric, dict)]
    records = []
    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue
        dimensions = record.get("dimensionValues") or []
        values = record.get("metricValues") or []
        records.append({
            "dimension": dimensions[0].get("value") if dimensions and isinstance(dimensions[0], dict) else None,
            "metrics": {
                key: {"value": value.get("value"), "applicable": value.get("applicable")}
                for key, value in zip(metric_keys, values)
                if key and isinstance(value, dict)
            },
        })
    return {
        "source": "eBay Sell Analytics traffic_report", "dimension": dimension,
        "marketplace_id": "EBAY_GB", "timezone": "Europe/London",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "listing_ids_requested": listing_ids, "last_updated_at": payload.get("lastUpdatedDate"),
        "coverage": {"returned_records": len(records), "requested_ids": len(set(listing_ids)),
                     "missing_listing_ids": sorted(set(listing_ids) - {
                         str(row["dimension"]) for row in records if row["dimension"] is not None
                     }) if dimension == "LISTING" else []},
        "records": records,
        "note": "Listing traffic is parent-level, not variation-level; search visits and ad clicks have different denominators.",
    }


def _safe_amount(value: Any) -> dict[str, str | None] | None:
    if not isinstance(value, dict):
        return None
    amount = value.get("value")
    currency = value.get("currency")
    if amount is None:
        return None
    return {"value": str(amount), "currency": str(currency) if currency else None}


def _unit_item_price(line: dict[str, Any]) -> dict[str, str | None] | None:
    """Discount-adjusted item cost per unit, excluding postage and tax."""
    cost = _safe_amount(line.get("discountedLineItemCost") or line.get("lineItemCost"))
    quantity = line.get("quantity")
    if not cost or not isinstance(quantity, int) or quantity <= 0:
        return None
    try:
        value = Decimal(cost["value"]) / Decimal(quantity)
    except (InvalidOperation, ZeroDivisionError):
        return None
    return {"value": str(value.quantize(Decimal("0.01"))), "currency": cost["currency"]}


async def get_key_order_lines(
    client: SellerInsightsClient, *, start: date, end: date, listing_ids: list[str],
) -> dict[str, Any]:
    validate_window(start, end)
    if not listing_ids or len(listing_ids) > 100 or any(not value.isdecimal() for value in listing_ids):
        raise ValueError("Provide 1-100 numeric listing IDs.")
    wanted = set(listing_ids)
    from_utc, to_utc = utc_bounds(start, end)
    rows: list[dict[str, Any]] = []
    offset = 0
    scanned = 0
    total: int | None = None
    last_page_full = False
    while offset < 2000:
        page = await client.get_json(
            "/sell/fulfillment/v1/order",
            params={"filter": f"creationdate:[{from_utc}..{to_utc}]", "limit": 200, "offset": offset},
        )
        orders = page.get("orders") or []
        raw_total = page.get("total", total)
        total = int(raw_total) if isinstance(raw_total, (int, str)) and str(raw_total).isdecimal() else None
        if not isinstance(orders, list):
            raise SellerInsightsError("eBay returned an unexpected order page.")
        scanned += len(orders)
        last_page_full = len(orders) == 200
        for order in orders:
            if not isinstance(order, dict):
                continue
            for line in order.get("lineItems") or []:
                if not isinstance(line, dict):
                    continue
                item_id = str(line.get("legacyItemId") or "")
                if item_id not in wanted:
                    continue
                selectors = line.get("variationAspects") or []
                rows.append({
                    "order_date": order.get("creationDate"),
                    "item_id": item_id,
                    "variation_sku": line.get("sku"),
                    "legacy_variation_id": line.get("legacyVariationId"),
                    "variation_selectors": [
                        {"name": aspect.get("name"), "value": aspect.get("value")}
                        for aspect in selectors if isinstance(aspect, dict)
                    ],
                    "units": line.get("quantity"),
                    "realised_item_price_per_unit": _unit_item_price(line),
                    "cancellation_state": (order.get("cancelStatus") or {}).get("cancelState"),
                    "refunds": [
                        {"amount": _safe_amount(refund.get("amount")),
                         "date": refund.get("refundDate")}
                        for refund in (line.get("refunds") or []) if isinstance(refund, dict)
                    ],
                    "order_level_refund_present": bool((order.get("paymentSummary") or {}).get("refunds")),
                })
        offset += len(orders)
        if not orders or len(orders) < 200 or (isinstance(total, int) and offset >= total):
            break
    return {
        "source": "eBay Sell Fulfillment getOrders", "marketplace_id": "EBAY_GB",
        "timezone": "Europe/London", "start_date": start.isoformat(), "end_date": end.isoformat(),
        "listing_ids_requested": listing_ids, "orders_scanned": scanned,
        "truncated": bool((total is not None and offset < total) or (offset >= 2000 and last_page_full)),
        "lines": rows,
        "note": "Only completed-checkout orders are returned. Item price is discount-adjusted line cost divided by units, excluding postage and tax. No buyer, address, or payment details leave this tool.",
    }


async def _paged(client: SellerInsightsClient, path: str, key: str | tuple[str, ...], *, params: dict[str, Any] | None = None,
                 max_pages: int = 5) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    base = dict(params or {})
    total = None
    for index in range(max_pages):
        payload = await client.get_json(path, params={**base, "limit": 200, "offset": index * 200})
        keys = (key,) if isinstance(key, str) else key
        found = next((name for name in keys if name in payload), None)
        if found is None:
            raise SellerInsightsError("eBay returned a Marketing page without the expected collection; coverage is unknown.")
        page = payload[found]
        if not isinstance(page, list):
            raise SellerInsightsError("eBay returned an unexpected Marketing API page.")
        rows.extend(item for item in page if isinstance(item, dict))
        total = payload.get("total", total)
        if len(page) < 200 or (isinstance(total, int) and len(rows) >= total):
            return rows, False
    return rows, True


async def get_promotion_inventory(
    client: SellerInsightsClient, *, listing_ids: list[str],
) -> dict[str, Any]:
    if not listing_ids or len(listing_ids) > 100 or any(not value.isdecimal() for value in listing_ids):
        raise ValueError("Provide 1-100 numeric listing IDs.")
    wanted = set(listing_ids)
    campaigns, campaign_cap = await _paged(client, "/sell/marketing/v1/ad_campaign", "campaigns")
    ads: list[dict[str, Any]] = []
    skipped_offsite: list[str] = []
    campaign_failures: list[dict[str, str]] = []
    for campaign in campaigns:
        campaign_id = str(campaign.get("campaignId") or "")
        if not campaign_id.isdecimal():
            continue
        funding_strategy = campaign.get("fundingStrategy")
        channels = campaign.get("channels") or []
        if any(str(channel).upper() == "OFF_SITE" for channel in channels) or str(campaign.get("campaignType") or "").upper() == "PROMOTED_OFFSITE":
            skipped_offsite.append(campaign_id)
            continue
        try:
            campaign_ads, ad_cap = await _paged(
                client, f"/sell/marketing/v1/ad_campaign/{campaign_id}/ad", "ads",
                params={"listing_ids": ",".join(listing_ids)}, max_pages=5,
            )
        except SellerInsightsError as exc:
            campaign_failures.append({"campaign_id": campaign_id, "reason": str(exc)})
            campaign_cap = True
            continue
        for ad in campaign_ads:
            if str(ad.get("listingId") or "") in wanted:
                ads.append({
                    "listing_id": str(ad.get("listingId")), "campaign_id": campaign_id,
                    "campaign_name": campaign.get("campaignName"),
                    "campaign_status": campaign.get("campaignStatus"),
                    "campaign_start_date": campaign.get("startDate"),
                    "campaign_end_date": campaign.get("endDate"),
                    "funding_model": funding_strategy.get("fundingModel") if isinstance(funding_strategy, dict) else funding_strategy,
                    "ad_id": ad.get("adId"), "ad_status": ad.get("adStatus"),
                    "bid_percentage": ad.get("bidPercentage"),
                    "ad_rate_strategy": funding_strategy.get("adRateStrategy") if isinstance(funding_strategy, dict) else None,
                })
        campaign_cap = campaign_cap or ad_cap
    promotion_error = None
    try:
        promotions, promotion_cap = await _paged(
            client, "/sell/marketing/v1/promotion", "promotions", params={"marketplace_id": "EBAY_GB"},
        )
    except SellerInsightsError as exc:
        promotions, promotion_cap = [], True
        promotion_error = str(exc)
    discounts: list[dict[str, Any]] = []
    for promotion in promotions:
        promotion_id = str(promotion.get("promotionId") or "")
        if not promotion_id.isdecimal():
            continue
        try:
            members, member_cap = await _paged(
                client, f"/sell/marketing/v1/promotion/{promotion_id}/get_listing_set", ("items", "listings"),
                max_pages=5,
            )
        except SellerInsightsError as exc:
            promotion_cap = True
            promotion_error = str(exc)
            continue
        matched = [str(item.get("listingId")) for item in members if str(item.get("listingId") or "") in wanted]
        if matched:
            discounts.append({
                "promotion_id": promotion_id, "listing_ids": matched,
                "promotion_type": promotion.get("promotionType"),
                "promotion_status": promotion.get("promotionStatus"),
                "start_date": promotion.get("startDate"), "end_date": promotion.get("endDate"),
                "discount_rules": promotion.get("discountRules"),
                "listing_set_truncated": member_cap,
            })
        promotion_cap = promotion_cap or member_cap
    return {
        "source": "eBay Sell Marketing campaigns and Discounts Manager",
        "marketplace_id": "EBAY_GB", "listing_ids_requested": listing_ids,
        "paid_ads": ads, "discounts": discounts,
        "coverage": {"campaign_scan_truncated": campaign_cap, "promotion_scan_truncated": promotion_cap,
                     "skipped_offsite_campaign_ids": skipped_offsite,
                     "campaign_ad_failures": campaign_failures,
                     "discount_coverage_error": promotion_error},
        "note": "A paid ad rate is a seller fee percentage; a markdown is a buyer-facing price reduction.",
    }


async def start_ad_report(
    client: SellerInsightsClient, *, start: date, end: date, listing_ids: list[str],
    campaign_ids: list[str], funding_model: str,
) -> dict[str, Any]:
    validate_window(start, end)
    if not listing_ids or any(not value.isdecimal() for value in listing_ids):
        raise ValueError("Numeric listing IDs are required for the ad report.")
    if not campaign_ids or any(not value.isdecimal() for value in campaign_ids):
        raise ValueError("Numeric campaign IDs are required for the ad report.")
    if funding_model not in {"COST_PER_SALE", "COST_PER_CLICK"}:
        raise ValueError("funding_model must be COST_PER_SALE or COST_PER_CLICK.")
    from_utc, to_utc = utc_bounds(start, end)
    dimensions = [{"dimensionKey": "campaign_id"}, {"dimensionKey": "listing_id"}]
    if funding_model == "COST_PER_CLICK":
        dimensions.insert(0, {"dimensionKey": "ad_group_id"})
        metrics = ["cpc_impressions", "cpc_clicks", "cpc_attributed_sales", "cpc_ad_fees_listingsite_currency"]
    else:
        metrics = ["impressions", "clicks", "sales", "ad_fees", "sale_amount"]
    response = await client.request("POST", "/sell/marketing/v1/ad_report_task", json={
        "dateFrom": from_utc, "dateTo": to_utc, "marketplaceId": "EBAY_GB",
        "reportType": "LISTING_PERFORMANCE_REPORT", "reportFormat": "TSV_GZIP",
        "fundingModels": [funding_model], "dimensions": dimensions,
        "metricKeys": metrics, "campaignIds": campaign_ids, "listingIds": listing_ids,
    })
    location = response.headers.get("Location", "")
    task_id = location.rstrip("/").split("/")[-1]
    if not task_id.isdecimal():
        raise SellerInsightsError("eBay created a report but returned no usable task ID.")
    return {"status": "PENDING", "report_task_id": task_id, "source": "eBay Sell Marketing ad report task",
            "funding_model": funding_model, "listing_ids_requested": listing_ids,
            "start_date": start.isoformat(), "end_date": end.isoformat()}


async def fetch_ad_report(client: SellerInsightsClient, *, task_id: str,
                          listing_ids: list[str]) -> dict[str, Any]:
    if not task_id.isdecimal() or not listing_ids or any(not item.isdecimal() for item in listing_ids):
        raise ValueError("A numeric task ID and listing IDs are required.")
    task = await client.get_json(f"/sell/marketing/v1/ad_report_task/{task_id}")
    status = task.get("reportTaskStatus")
    result: dict[str, Any] = {"source": "eBay Sell Marketing listing performance report",
                              "report_task_id": task_id, "status": status,
                              "listing_ids_requested": listing_ids,
                              "start_date": task.get("dateFrom"), "end_date": task.get("dateTo")}
    if status != "SUCCESS":
        return result
    report_id = str(task.get("reportId") or "")
    if not report_id.isdecimal():
        raise SellerInsightsError("Completed eBay report has no usable report ID.")
    response = await client.request("GET", f"/sell/marketing/v1/ad_report/{report_id}")
    with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as archive:
        data = archive.read(5_000_001)
    if len(data) > 5_000_000:
        raise SellerInsightsError("eBay report exceeds the bounded 5 MB read limit.")
    wanted = set(listing_ids)
    rows = []
    for row in csv.DictReader(io.StringIO(data.decode("utf-8-sig")), delimiter="\t"):
        item_id = row.get("listing_id") or row.get("Listing ID")
        if item_id in wanted:
            rows.append(row)
        if len(rows) > 2000:
            raise SellerInsightsError("eBay report exceeds the bounded 2,000-row result limit.")
    result.update({"report_id": report_id, "rows": rows, "row_count": len(rows),
                   "note": "Attributed ad sales may mature for 30 days after a click; recent rows are provisional."})
    return result
