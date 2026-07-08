"""Mocked Trading workflow tests; no request reaches eBay, R2, or the seller account."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ebay_mcp.trading.client import TradingAPIError, TradingResponse, element, find, findall, value
from ebay_mcp.trading import service
from ebay_mcp.media import ebay as media_api
from models.ebay.trading import (
    AddFixedPriceItemInput, FixedPriceListingProposal, FixedPriceRevisionPatch,
    RecentSellerListingsInput, ReviseFixedPriceItemInput,
)


def response(name: str, *, ack: str = "Success", issues=None) -> TradingResponse:
    root = element(f"{name}Response")
    element("Ack", ack, root)
    return TradingResponse(root=root, ack=ack, errors=issues or [])


def add_fee(root: ET.Element, amount: str, name: str = "InsertionFee") -> None:
    fees = find(root, "Fees")
    if fees is None:
        fees = element("Fees", parent=root)
    fee = element("Fee", parent=fees)
    element("Name", name, fee)
    amount_node = element("Fee", amount, fee)
    amount_node.set("currencyID", "GBP")


def item_response(item_id="123456789012", title="Placeholder", *, listing_type="FixedPriceItem", status="Active"):
    result = response("GetItem")
    item = element("Item", parent=result.root)
    element("ItemID", item_id, item)
    element("Title", title, item)
    element("Description", "Truthful unfinished description", item)
    price = element("StartPrice", "999.00", item)
    price.set("currencyID", "GBP")
    element("ConditionID", "3000", item)
    element("ConditionDescription", "Used with light wear", item)
    category = element("PrimaryCategory", parent=item)
    element("CategoryID", "123", category)
    element("CategoryName", "Test category", category)
    specifics = element("ItemSpecifics", parent=item)
    for name, values in {"Brand": ["Acme"], "Colour": ["Red"]}.items():
        entry = element("NameValueList", parent=specifics)
        element("Name", name, entry)
        for entry_value in values:
            element("Value", entry_value, entry)
    pictures = element("PictureDetails", parent=item)
    element("PictureURL", "https://i.ebayimg.com/images/g/one/s-l1600.jpg", pictures)
    element("ListingType", listing_type, item)
    element("Site", "UK", item)
    element("Quantity", "1", item)
    selling = element("SellingStatus", parent=item)
    element("ListingStatus", status, selling)
    element("QuantitySold", "0", selling)
    details = element("ListingDetails", parent=item)
    element("StartTime", (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), details)
    element("EndTime", (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(), details)
    element("ViewItemURL", f"https://www.ebay.co.uk/itm/{item_id}", details)
    best = element("BestOfferDetails", parent=item)
    element("BestOfferEnabled", False, best)
    return result


class FakeHTTP:
    async def get(self, *args, **kwargs):
        return type("Response", (), {"status_code": 404})()


class FakeTradingClient:
    def __init__(self):
        self.access_token = "fake-token"
        self.client = FakeHTTP()
        self.calls = []
        self.current_title = "Placeholder"
        self.verify_fee = Decimal("0")
        self.added_uuid = None
        self.item_id = "123456789012"
        self.duplicate = False

    async def call(self, name, request):
        self.calls.append((name, request))
        if name == "GetItem":
            return item_response(self.item_id, self.current_title)
        if name == "GetSellerList":
            result = response("GetSellerList")
            array = element("ItemArray", parent=result.root)
            source = find(item_response().root, "Item")
            array.append(source)
            pagination = element("PaginationResult", parent=result.root)
            element("TotalNumberOfPages", 1, pagination)
            element("TotalNumberOfEntries", 1, pagination)
            element("HasMoreItems", False, result.root)
            return result
        if name == "ReviseFixedPriceItem":
            self.current_title = value(request, "Item/Title", self.current_title)
            return response("ReviseFixedPriceItem")
        if name == "VerifyAddFixedPriceItem":
            result = response("VerifyAddFixedPriceItem")
            add_fee(result.root, str(self.verify_fee))
            return result
        if name == "AddFixedPriceItem":
            self.added_uuid = value(request, "Item/UUID")
            if self.duplicate:
                root = element("AddFixedPriceItemResponse")
                duplicate = element("DuplicateInvocationDetails", parent=root)
                element("Status", "Success", duplicate)
                error = element("Errors", parent=root)
                params = element("ErrorParameters", parent=error)
                element("Value", self.item_id, params)
                issue = service.TradingIssue(code="duplicate", severity="Error", message="Duplicate invocation")
                raise TradingAPIError("Duplicate invocation", [issue], root=root)
            result = response("AddFixedPriceItem")
            element("ItemID", self.item_id, result.root)
            add_fee(result.root, str(self.verify_fee))
            return result
        raise AssertionError(name)


def proposal():
    return FixedPriceListingProposal(
        title="Used test item",
        description="Used item with light wear.",
        price_gbp="12.50",
        category_id="123",
        condition_id="3000",
        condition_description="Light wear",
        item_specifics={"Brand": ["Acme"]},
        picture_urls=["https://i.ebayimg.com/images/g/one/s-l1600.jpg"],
    )


@pytest.fixture(autouse=True)
def defaults(monkeypatch):
    monkeypatch.setenv("EBAY_PAYMENT_POLICY_ID", "1001")
    monkeypatch.setenv("EBAY_RETURN_POLICY_ID", "1002")
    monkeypatch.setenv("EBAY_FULFILLMENT_POLICY_ID", "1003")
    monkeypatch.setenv("EBAY_ITEM_LOCATION", "London")
    monkeypatch.setenv("EBAY_ITEM_POSTAL_CODE", "SW1A1AA")
    monkeypatch.delenv("EBAY_USER_NAME", raising=False)
    service._VERIFICATIONS.clear()


def test_recent_listings_returns_active_fixed_price_takeover_candidates():
    client = FakeTradingClient()
    result = asyncio.run(service.get_recent_seller_listings(RecentSellerListingsInput(), client))
    assert [listing.item_id for listing in result.listings] == [client.item_id]
    assert result.listings[0].price_gbp == Decimal("999.00")
    assert result.excluded_count == 0


def test_get_item_returns_revision_token_and_complete_editable_state():
    listing = asyncio.run(service.get_item("123456789012", FakeTradingClient()))
    assert listing.supported_for_revision
    assert len(listing.revision_token) == 64
    assert listing.item_specifics == {"Brand": ["Acme"], "Colour": ["Red"]}
    assert listing.picture_urls[0].startswith("https://i.ebayimg.com/")


def test_variation_listing_is_flagged_and_rejected_for_narrow_revision():
    client = FakeTradingClient()
    result = item_response()
    element("Variations", parent=find(result.root, "Item"))

    async def custom_call(name, request):
        return result

    client.call = custom_call
    listing = asyncio.run(service.get_item(client.item_id, client))
    assert not listing.supported_for_revision
    assert "variation_listing" in listing.restrictions


def test_revision_rejects_stale_token_before_write():
    client = FakeTradingClient()
    listing = asyncio.run(service.get_item(client.item_id, client))
    client.current_title = "Changed elsewhere"
    params = ReviseFixedPriceItemInput(
        item_id=client.item_id,
        revision_token=listing.revision_token,
        patch=FixedPriceRevisionPatch(title="Polished title"),
    )
    with pytest.raises(ValueError, match="changed after"):
        asyncio.run(service.revise_fixed_price_item(params, client))
    assert not any(name == "ReviseFixedPriceItem" for name, _ in client.calls)


def test_revision_sends_complete_merged_item_specifics_and_escapes_xml():
    current = asyncio.run(service.get_item("123456789012", FakeTradingClient()))
    patch = FixedPriceRevisionPatch(
        title="A & B <original>",
        item_specifics_upsert={"Material": ["Steel & brass"]},
        item_specifics_remove=["Colour"],
    )
    request = service._build_revise_request(current, patch)
    serialized = ET.tostring(request, encoding="unicode")
    assert "A &amp; B &lt;original&gt;" in serialized
    entries = findall(find(request, "Item"), "ItemSpecifics/NameValueList")
    parsed = {value(entry, "Name"): [node.text for node in findall(entry, "Value")] for entry in entries}
    assert parsed == {"Brand": ["Acme"], "Material": ["Steel & brass"]}


def test_revision_uses_deleted_field_when_removing_all_item_specifics():
    current = asyncio.run(service.get_item("123456789012", FakeTradingClient()))
    request = service._build_revise_request(
        current,
        FixedPriceRevisionPatch(item_specifics_remove=["Brand", "Colour"]),
    )
    assert value(request, "DeletedField") == "Item.ItemSpecifics"
    assert find(request, "Item/ItemSpecifics") is None


def test_fee_ceiling_blocks_add_before_publication():
    client = FakeTradingClient()
    client.verify_fee = Decimal("1.25")
    verified = asyncio.run(service.verify_add_fixed_price_item(proposal(), client))
    params = AddFixedPriceItemInput(
        proposal=proposal(), verification_token=verified.verification_token, max_listing_fee_gbp="1.00"
    )
    with pytest.raises(ValueError, match="approved ceiling"):
        asyncio.run(service.add_fixed_price_item(params, client))
    assert not any(name == "AddFixedPriceItem" for name, _ in client.calls)


def test_direct_add_can_resolve_location_from_existing_merchant_location(monkeypatch):
    monkeypatch.delenv("EBAY_ITEM_LOCATION", raising=False)
    monkeypatch.delenv("EBAY_ITEM_POSTAL_CODE", raising=False)
    monkeypatch.delenv("EBAY_DELIVERY_POSTAL_CODE", raising=False)
    monkeypatch.setenv("EBAY_MERCHANT_LOCATION_KEY", "default-location")

    class LocationResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"location": {"address": {"city": "London", "postalCode": "SW1A1AA"}}}

    class LocationHTTP(FakeHTTP):
        async def get(self, *args, **kwargs):
            return LocationResponse()

    client = FakeTradingClient()
    client.client = LocationHTTP()
    defaults = asyncio.run(service._required_add_defaults(client))
    assert defaults["location"] == "London"
    assert defaults["postal_code"] == "SW1A1AA"


def test_verified_add_uses_same_uuid_and_reads_back_listing():
    client = FakeTradingClient()
    verified = asyncio.run(service.verify_add_fixed_price_item(proposal(), client))
    verify_call = next(request for name, request in client.calls if name == "VerifyAddFixedPriceItem")
    verified_uuid = value(verify_call, "Item/UUID")
    result = asyncio.run(service.add_fixed_price_item(AddFixedPriceItemInput(
        proposal=proposal(), verification_token=verified.verification_token, max_listing_fee_gbp="0"
    ), client))
    assert result.status == "published"
    assert result.item_id == client.item_id
    assert client.added_uuid == verified_uuid
    assert result.final_listing.revision_token


def test_duplicate_uuid_recovers_original_item_as_idempotent_success():
    client = FakeTradingClient()
    client.duplicate = True
    verified = asyncio.run(service.verify_add_fixed_price_item(proposal(), client))
    result = asyncio.run(service.add_fixed_price_item(AddFixedPriceItemInput(
        proposal=proposal(), verification_token=verified.verification_token, max_listing_fee_gbp="0"
    ), client))
    assert result.item_id == client.item_id
    assert result.idempotent_recovery is True


def test_media_upload_returns_only_eps_metadata(monkeypatch):
    async def token():
        return "fake-token"

    class UploadResponse:
        status_code = 201
        headers = {"location": "https://apim.ebay.com/commerce/media/v1_beta/image/image-1"}

        @staticmethod
        def json():
            return {"imageUrl": "https://i.ebayimg.com/images/g/one/s-l1600.jpg", "expirationDate": "2026-08-01T00:00:00Z"}

    class UploadClient:
        async def post(self, *args, **kwargs):
            assert kwargs["files"]["image"][1] == b"private-image-bytes"
            return UploadResponse()

    monkeypatch.setattr(media_api, "get_ebay_access_token", token)
    monkeypatch.setattr(media_api, "get_staged_bytes", lambda ref: (b"private-image-bytes", "photo.jpg"))
    result = asyncio.run(media_api.upload_staged_pictures(["r2:staging/seller/x/photo.jpg"], UploadClient()))
    serialized = result[0].model_dump_json()
    assert result[0].image_id == "image-1"
    assert "private-image-bytes" not in serialized
