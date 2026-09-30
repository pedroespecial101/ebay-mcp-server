"""Offline contract tests for read-only seller performance projections."""

import asyncio
import gzip
from datetime import date
from functools import wraps

import httpx
import pytest

from ebay_auth.ebay_auth import requested_scopes
from ebay_mcp.insights.client import SellerInsightsClient
from ebay_mcp.insights.service import (
    fetch_ad_report, get_key_order_lines, get_promotion_inventory,
    get_traffic_report, start_ad_report,
)
from ebay_mcp.research.key_cohort import compare_key_cohorts


def async_test(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return run


@async_test
async def test_traffic_uses_uk_dates_and_named_metrics():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={
            "header": {"metrics": [{"key": "LISTING_VIEWS_TOTAL"}, {"key": "TRANSACTION"}]},
            "records": [{"dimensionValues": [{"value": "123"}],
                         "metricValues": [{"value": 18, "applicable": True},
                                          {"value": 1, "applicable": True}]}],
            "lastUpdatedDate": "2026-09-30T12:00:00Z",
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async with SellerInsightsClient(http, "test-token") as client:
            result = await get_traffic_report(client, start=date(2026, 8, 31),
                end=date(2026, 9, 29), dimension="LISTING", listing_ids=["123"])
    assert result["records"][0]["metrics"]["TRANSACTION"]["value"] == 1
    assert result["last_updated_at"] == "2026-09-30T12:00:00Z"
    assert seen[0].url.params["filter"].startswith("marketplace_ids:{EBAY_GB},listing_ids:{123}")
    assert "2026-08-31T00:00:00.000+01:00" in seen[0].url.params["filter"]
    assert "2026-09-29T23:59:59.999+01:00" in seen[0].url.params["filter"]


@async_test
async def test_day_report_rejects_listing_filter():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as http:
        async with SellerInsightsClient(http, "test-token") as client:
            with pytest.raises(ValueError, match="account-level"):
                await get_traffic_report(client, start=date(2026, 9, 1),
                    end=date(2026, 9, 2), dimension="DAY", listing_ids=["123"])


@async_test
async def test_orders_are_filtered_and_strip_buyer_data():
    def handler(request):
        assert request.url.params["filter"].startswith("creationdate:")
        return httpx.Response(200, json={"total": 1, "orders": [{
            "creationDate": "2026-09-15T10:00:00Z", "buyer": {"username": "private"},
            "shippingStep": {"shipTo": {"addressLine1": "private"}},
            "cancelStatus": {"cancelState": "NONE_REQUESTED"},
            "lineItems": [
                {"legacyItemId": "123", "sku": "FS101", "quantity": 2,
                 "lineItemCost": {"value": "6.08", "currency": "GBP"},
                 "variationAspects": [{"name": "Exact Key", "value": "FS101"}]},
                {"legacyItemId": "999", "sku": "OTHER", "quantity": 1},
            ],
        }]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async with SellerInsightsClient(http, "test-token") as client:
            result = await get_key_order_lines(client, start=date(2026, 9, 1),
                                               end=date(2026, 9, 29), listing_ids=["123"])
    assert len(result["lines"]) == 1
    assert result["lines"][0]["variation_sku"] == "FS101"
    assert result["lines"][0]["realised_item_price_per_unit"]["value"] == "3.04"
    assert "private" not in str(result)


@async_test
async def test_promotion_inventory_separates_paid_ads_and_discounts():
    def handler(request):
        path = request.url.path
        if path.endswith("/ad_campaign"):
            return httpx.Response(200, json={"campaigns": [{"campaignId": "55", "campaignName": "Keys",
                "campaignStatus": "RUNNING", "startDate": "2026-08-14"}]})
        if path.endswith("/55/ad"):
            return httpx.Response(200, json={"ads": [{"listingId": "123", "bidPercentage": "17"},
                                                      {"listingId": "999", "bidPercentage": "8"}]})
        if path.endswith("/promotion"):
            return httpx.Response(200, json={"promotions": [{"promotionId": "77",
                "promotionType": "MARKDOWN_SALE", "promotionStatus": "RUNNING"}]})
        if path.endswith("/77/get_listing_set"):
            return httpx.Response(200, json={"listings": [{"listingId": "123"}]})
        raise AssertionError(path)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async with SellerInsightsClient(http, "test-token") as client:
            result = await get_promotion_inventory(client, listing_ids=["123"])
    assert result["paid_ads"][0]["bid_percentage"] == "17"
    assert result["discounts"][0]["promotion_type"] == "MARKDOWN_SALE"
    assert len(result["paid_ads"]) == 1


@async_test
async def test_ad_report_task_and_bounded_result():
    def handler(request):
        path = request.url.path
        if request.method == "POST":
            assert request.content
            assert path.endswith("/ad_report_task")
            return httpx.Response(201, headers={"Location": "https://api.ebay.com/sell/marketing/v1/ad_report_task/456"})
        if path.endswith("/ad_report_task/456"):
            return httpx.Response(200, json={"reportTaskStatus": "SUCCESS", "reportId": "789"})
        if path.endswith("/ad_report/789"):
            data = b"listing_id\timpressions\tclicks\n123\t100\t2\n999\t1000\t5\n"
            return httpx.Response(200, content=gzip.compress(data))
        raise AssertionError(path)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async with SellerInsightsClient(http, "test-token") as client:
            started = await start_ad_report(client, start=date(2026, 9, 1), end=date(2026, 9, 29),
                listing_ids=["123"], campaign_ids=["55"], funding_model="COST_PER_SALE")
            result = await fetch_ad_report(client, task_id=started["report_task_id"], listing_ids=["123"])
    assert started["report_task_id"] == "456"
    assert result["row_count"] == 1
    assert result["rows"][0]["impressions"] == "100"


def test_reporting_scopes_are_opt_in(monkeypatch):
    monkeypatch.delenv("EBAY_ENABLE_REPORTING_SCOPES", raising=False)
    assert all("sell.analytics.readonly" not in scope for scope in requested_scopes())
    monkeypatch.setenv("EBAY_ENABLE_REPORTING_SCOPES", "1")
    assert sum("readonly" in scope for scope in requested_scopes()) == 4


@async_test
async def test_empty_traffic_and_missing_listing_are_explicit():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"header": {"metrics": []}, "records": []})
    )) as http:
        async with SellerInsightsClient(http, "test-token") as client:
            result = await get_traffic_report(client, start=date(2026, 9, 1),
                end=date(2026, 9, 29), dimension="LISTING", listing_ids=["123"])
    assert result["records"] == []
    assert result["coverage"]["missing_listing_ids"] == ["123"]


@async_test
async def test_orders_paginate_and_include_ended_parent_ids():
    calls = []

    def handler(request):
        offset = int(request.url.params["offset"])
        calls.append(offset)
        count = 200 if offset == 0 else 1
        orders = [{"creationDate": "2026-09-10T00:00:00Z", "lineItems": [
            {"legacyItemId": "100" if offset == 0 else "200", "quantity": 1}
        ]} for _ in range(count)]
        return httpx.Response(200, json={"total": 201, "orders": orders})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async with SellerInsightsClient(http, "test-token") as client:
            result = await get_key_order_lines(client, start=date(2026, 9, 1),
                end=date(2026, 9, 29), listing_ids=["100", "200"])
    assert calls == [0, 200]
    assert {line["item_id"] for line in result["lines"]} == {"100", "200"}
    assert result["truncated"] is False


def test_competitor_relist_gap_is_not_misread_as_zero_sales():
    previous = {"source": "eBay Browse active UK listings", "series": "MRN",
        "captured_at": "2026-09-01T00:00:00Z", "parents": [
            {"parent_item_id": "100", "quantity_sold": 7}]}
    current = {"source": "eBay Browse active UK listings", "series": "MRN",
        "captured_at": "2026-09-30T00:00:00Z", "parents": [
            {"parent_item_id": "200", "quantity_sold": 1}]}
    compared = compare_key_cohorts(previous, current)
    assert compared["parents"][0]["status"] == "absent_from_current_search"
    assert all(row["cumulative_sold_delta_proxy"] is None for row in compared["parents"])


@async_test
async def test_discount_schema_and_access_gap_are_not_silent():
    def handler(request):
        path = request.url.path
        if path.endswith("/ad_campaign"):
            return httpx.Response(200, json={"campaigns": []})
        if path.endswith("/promotion"):
            return httpx.Response(200, json={"promotions": [{"promotionId": "77"}]})
        if path.endswith("/get_listing_set"):
            return httpx.Response(200, json={"items": [{"listingId": "123"}]})
        raise AssertionError(path)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async with SellerInsightsClient(http, "test-token") as client:
            result = await get_promotion_inventory(client, listing_ids=["123"])
    assert result["discounts"][0]["listing_ids"] == ["123"]
