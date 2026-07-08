"""Mocked workflow tests: no request reaches eBay or R2."""

import asyncio
from decimal import Decimal

from ebay_mcp.listing import workflow
from models.ebay.listing_workflow import FeeEstimate, ListingValidationResult, PublishListingInput, SimpleListingInput


def proposal(mode="draft"):
    return SimpleListingInput(sku="codex-test-sku", title="Used test item", description="Light wear",
        price_gbp="12.50", category_id="123", condition="USED_GOOD", condition_description="Light wear",
        aspects={"Brand": ["Unbranded"]}, image_refs=["r2:staging/seller/x/photo.jpg"], mode=mode)


def inventory(data):
    return {"condition": data.condition, "conditionDescription": data.condition_description,
        "availability": {"shipToLocationAvailability": {"quantity": 1}},
        "product": {"title": data.title, "description": data.description, "aspects": data.aspects}}


def offer(data, published=False):
    value = {"offerId": "offer-1", "sku": data.sku, "marketplaceId": "EBAY_GB", "format": "FIXED_PRICE",
        "listingDuration": "GTC", "categoryId": data.category_id, "availableQuantity": 1,
        "pricingSummary": {"price": {"value": str(data.price_gbp), "currency": "GBP"}}, "status": "UNPUBLISHED"}
    if published:
        value.update(status="PUBLISHED", listing={"listingId": "123456789"})
    return value


class FakeResponse:
    def __init__(self, body=None): self.body = body or {}
    def json(self): return self.body


class FakeAPI:
    calls = []
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def request(self, method, path, **kwargs):
        self.calls.append((method, path))
        return FakeResponse()


def test_create_resumes_matching_draft_without_rewriting(monkeypatch):
    data = proposal()
    monkeypatch.setattr(workflow, "EbayAPI", FakeAPI)
    async def valid(*_): return ListingValidationResult(valid=True, normalized=data)
    async def get_item(*_): return inventory(data)
    async def get_offers(*_): return [offer(data)]
    async def fees(*_): return FeeEstimate(amount_gbp=Decimal("0"))
    monkeypatch.setattr(workflow, "validate_listing", valid)
    monkeypatch.setattr(workflow, "_get_inventory", get_item)
    monkeypatch.setattr(workflow, "_get_offers", get_offers)
    monkeypatch.setattr(workflow, "_fees", fees)
    result = asyncio.run(workflow.create_listing(data))
    assert result.status == "draft_ready"
    assert "inventory_item_resumed" in result.completed_steps
    assert "offer_resumed" in result.completed_steps
    assert not any(method in {"PUT", "DELETE"} for method, _ in FakeAPI.calls)


def test_publish_verifies_active_listing_after_zero_fee(monkeypatch):
    data = proposal("publish")
    FakeAPI.calls = []
    monkeypatch.setattr(workflow, "EbayAPI", FakeAPI)
    async def get_offers(*_): return [offer(data)]
    async def fees(*_): return FeeEstimate(amount_gbp=Decimal("0"))
    async def poll(*_): return offer(data, published=True)
    monkeypatch.setattr(workflow, "_get_offers", get_offers)
    monkeypatch.setattr(workflow, "_fees", fees)
    monkeypatch.setattr(workflow, "_poll_published", poll)
    result = asyncio.run(workflow.publish_listing(PublishListingInput(sku=data.sku)))
    assert result.status == "published"
    assert result.listing_id == "123456789"
    assert ("POST", "/sell/inventory/v1/offer/offer-1/publish") in FakeAPI.calls


def test_nonzero_fee_requires_explicit_ceiling(monkeypatch):
    data = proposal()
    FakeAPI.calls = []
    monkeypatch.setattr(workflow, "EbayAPI", FakeAPI)
    async def get_offers(*_): return [offer(data)]
    async def fees(*_): return FeeEstimate(amount_gbp=Decimal("1.25"))
    monkeypatch.setattr(workflow, "_get_offers", get_offers)
    monkeypatch.setattr(workflow, "_fees", fees)
    result = asyncio.run(workflow.publish_listing(PublishListingInput(sku=data.sku)))
    assert result.status == "fee_approval_required"
    assert not any(path.endswith("/publish") for _, path in FakeAPI.calls)
