"""Mocked Trading workflow tests; no request reaches eBay, R2, or the seller account."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

import httpx
import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ebay_mcp.trading import client as trading_client
from ebay_mcp.trading import server as trading_server
from ebay_mcp.trading.client import TradingAPIError, TradingClient, TradingResponse, element, find, findall, value
from ebay_mcp.trading import service
from ebay_mcp.media import ebay as media_api
from models.ebay.trading import (
    AddFixedPriceItemInput, FixedPriceListingProposal, FixedPriceRevisionPatch,
    AddFixedPriceVariationsInput, MultiVariationFixedPriceListingProposal,
    AppendFixedPriceVariationInput,
    ReorderFixedPriceVariationsInput,
    EndFixedPriceItemInput,
    RecentSellerListingsInput, ReviseFixedPriceItemInput,
    ViewItemImagesInput,
)


def trading_xml(ack: str, message: str | None = None) -> bytes:
    root = element("GetItemResponse")
    element("Ack", ack, root)
    if message:
        error = element("Errors", parent=root)
        element("ShortMessage", message, error)
        element("LongMessage", message, error)
        element("ErrorCode", "21917053", error)
        element("SeverityCode", "Error", error)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


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


def item_response(
    item_id="123456789012", title="Placeholder", *, listing_type="FixedPriceItem",
    status="Active", quantity_sold=0,
):
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
    element("QuantitySold", quantity_sold, selling)
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
        self.ended = False
        self.sold = False

    async def call(self, name, request):
        self.calls.append((name, request))
        if name == "GetItem":
            return item_response(
                self.item_id,
                self.current_title,
                status="Completed" if self.ended else "Active",
                quantity_sold=1 if self.sold else 0,
            )
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
        if name == "EndFixedPriceItem":
            self.ended = True
            return response("EndFixedPriceItem")
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


def key_master_variations(count=2):
    return [
        {
            "sku": f"TLL-{number:03d}-TL",
            "price": "4.95",
            "quantity": 1,
            "quantity_sold": 0,
            "selector": f"MRN{number} — Union — TLL-{number:03d}-TL",
            "urls": [
                f"https://i.ebayimg.com/images/g/MRN{number}-front/s-l1600.jpg",
                f"https://i.ebayimg.com/images/g/MRN{number}-rear/s-l1600.jpg",
            ],
        }
        for number in range(1, count + 1)
    ]


def key_master_response(
    variations, item_id="123456789012", specificity_values=None, dimension="Key Code",
):
    result = item_response(item_id, "MRN classic car keys")
    item = find(result.root, "Item")
    matrix = element("Variations", parent=item)
    for source in variations:
        variation = element("Variation", parent=matrix)
        element("SKU", source["sku"], variation)
        price = element("StartPrice", source["price"], variation)
        price.set("currencyID", "GBP")
        element("Quantity", source["quantity"], variation)
        selling = element("SellingStatus", parent=variation)
        element("QuantitySold", source["quantity_sold"], selling)
        specifics = element("VariationSpecifics", parent=variation)
        pair = element("NameValueList", parent=specifics)
        element("Name", dimension, pair)
        element("Value", source["selector"], pair)
    pictures = element("Pictures", parent=matrix)
    element("VariationSpecificName", dimension, pictures)
    for source in variations:
        picture_set = element("VariationSpecificPictureSet", parent=pictures)
        element("VariationSpecificValue", source["selector"], picture_set)
        for url in source["urls"]:
            element("PictureURL", url, picture_set)
    specifics_set = element("VariationSpecificsSet", parent=matrix)
    pair = element("NameValueList", parent=specifics_set)
    element("Name", dimension, pair)
    sources_by_selector = {source["selector"]: source for source in variations}
    for selector in specificity_values or [source["selector"] for source in variations]:
        source = sources_by_selector[selector]
        element("Value", source["selector"], pair)
    return result


class FakeVariationAppendClient(FakeTradingClient):
    def __init__(self, variations=None):
        super().__init__()
        self.variations = variations or key_master_variations()
        self.raise_after_revise = False
        self.corrupt_readback = False
        self.revised = False
        self.specificity_values = [entry["selector"] for entry in self.variations]

    async def call(self, name, request):
        self.calls.append((name, request))
        if name == "GetItem":
            source = [dict(entry, urls=list(entry["urls"])) for entry in self.variations]
            if self.corrupt_readback and self.revised and source:
                source[0]["price"] = "9.99"
            return key_master_response(source, self.item_id, self.specificity_values)
        if name == "ReviseFixedPriceItem":
            revised_variations = findall(request, "Item/Variations/Variation")
            if not revised_variations:
                self.specificity_values = [
                    node.text for node in findall(
                        request, "Item/Variations/VariationSpecificsSet/NameValueList/Value"
                    ) if node.text
                ]
                self.revised = True
                if self.raise_after_revise:
                    raise TradingAPIError("network timeout after eBay may have applied the revision")
                return response("ReviseFixedPriceItem")
            picture_sets = {
                value(entry, "VariationSpecificValue"): [
                    picture.text for picture in findall(entry, "PictureURL") if picture.text
                ]
                for entry in findall(request, "Item/Variations/Pictures/VariationSpecificPictureSet")
            }
            parsed = []
            for entry in findall(request, "Item/Variations/Variation"):
                selector = value(entry, "VariationSpecifics/NameValueList/Value")
                existing = next((source for source in self.variations if source["sku"] == value(entry, "SKU")), None)
                parsed.append({
                    "sku": value(entry, "SKU"),
                    "price": value(entry, "StartPrice"),
                    # eBay's GetItem reports total quantity rather than the
                    # available value expected by Revise.
                    "quantity": existing["quantity"] if existing else int(value(entry, "Quantity") or "0"),
                    "quantity_sold": existing["quantity_sold"] if existing else 0,
                    "selector": selector,
                    "urls": picture_sets[selector],
                })
            self.variations = parsed
            self.specificity_values = [
                node.text for node in findall(
                    request, "Item/Variations/VariationSpecificsSet/NameValueList/Value"
                ) if node.text
            ]
            self.revised = True
            if self.raise_after_revise:
                raise TradingAPIError("network timeout after eBay may have applied the revision")
            return response("ReviseFixedPriceItem")
        return await super().call(name, request)


def proposal():
    return FixedPriceListingProposal(
        sku="SKU-001",
        title="Used test item",
        description="Used item with light wear.",
        price_gbp="12.50",
        category_id="123",
        condition_id="3000",
        condition_description="Light wear",
        item_specifics={"Brand": ["Acme"]},
        picture_urls=["https://i.ebayimg.com/images/g/one/s-l1600.jpg"],
        package={
            "weight_grams": 1250,
            "length_cm": "30",
            "width_cm": "20",
            "height_cm": "10",
            "package_type": "PARCEL_OR_PADDED_ENVELOPE",
        },
    )


def variation_proposal(uuid=None):
    return MultiVariationFixedPriceListingProposal(
        uuid=uuid,
        title="Two finishes of the same fitting",
        description="Two truthful variations, each photographed.",
        category_id="123",
        condition_id="3000",
        item_specifics={"Brand": ["Acme"]},
        picture_urls=["https://i.ebayimg.com/images/g/shared/s-l1600.jpg"],
        variations=[
            {
                "sku": "ACME-BRASS-S",
                "price_gbp": "12.50",
                "quantity": 2,
                "specifics": {"Finish": "Brass", "Size": "Small"},
            },
            {
                "sku": "ACME-STEEL-S",
                "price_gbp": "13.50",
                "quantity": 3,
                "specifics": {"Finish": "Steel", "Size": "Small"},
            },
        ],
        picture_mapping={
            "dimension": "Finish",
            "sets": [
                {"value": "Brass", "picture_urls": ["https://i.ebayimg.com/images/g/brass/s-l1600.jpg"]},
                {"value": "Steel", "picture_urls": ["https://i.ebayimg.com/images/g/steel/s-l1600.jpg"]},
            ],
        },
    )


def key_postage_variation_proposal():
    payload = variation_proposal().model_dump(mode="json")
    for variation in payload["variations"]:
        variation["price_gbp"] = "3.04"
    payload.update({
        "shipping_profile_id": "key-postage-policy",
        "shipping_discount_profile_id": "key-combined-discount-policy",
        "buyer_paid_postage": {
            "first_item_gbp": "1.50",
            "additional_item_gbp": "0.50",
            "simple_delivery": False,
        },
    })
    return MultiVariationFixedPriceListingProposal(**payload)


def key_code_variation_proposal():
    codes = ("MRN-001", "MRN-002", "MRN-003", "MRN-004", "MRN-005")
    return MultiVariationFixedPriceListingProposal(
        title="Five coded vintage keys",
        description="Each variation is identified by its photographed key code.",
        category_id="123",
        condition_id="3000",
        item_specifics={"Brand": ["Unbranded"]},
        picture_urls=["https://i.ebayimg.com/images/g/shared/s-l1600.jpg"],
        variations=[
            {
                "sku": f"KEY-{code}",
                "price_gbp": "12.50",
                "quantity": 1,
                "specifics": {"Key Code": code},
            }
            for code in codes
        ],
        picture_mapping={
            "dimension": "Key Code",
            "sets": [
                {"value": code, "picture_urls": [f"https://i.ebayimg.com/images/g/{code}/s-l1600.jpg"]}
                for code in codes
            ],
        },
    )


def append_key_input(revision_token, *, sku="TLL-038-TL", selector="MRN7 — Romac — TLL-038-TL"):
    return AppendFixedPriceVariationInput(
        item_id="123456789012",
        expected_revision_token=revision_token,
        operation_id="append-TLL-038-TL-1",
        variation={
            "sku": sku,
            "price_gbp": "4.95",
            "quantity": 1,
            "specifics": {"Key Code": selector},
        },
        picture_dimension="Key Code",
        picture_urls=[
            "https://i.ebayimg.com/images/g/MRN7-front/s-l1600.jpg",
            "https://i.ebayimg.com/images/g/MRN7-rear/s-l1600.jpg",
        ],
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


def test_trading_client_refreshes_once_for_xml_token_expiry(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, content=trading_xml("Failure", "IAF token supplied is expired."))
        return httpx.Response(200, content=trading_xml("Success"))

    monkeypatch.setattr(trading_client, "refresh_access_token", lambda: "fresh-token")
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def run():
        try:
            client = TradingClient(client=http, access_token="expired-token")
            return await client.call("GetItem", element("GetItemRequest"))
        finally:
            await http.aclose()

    result = asyncio.run(run())
    assert result.ack == "Success"
    assert len(requests) == 2
    assert requests[0].headers["X-EBAY-API-IAF-TOKEN"] == "expired-token"
    assert requests[1].headers["X-EBAY-API-IAF-TOKEN"] == "fresh-token"


def test_trading_client_does_not_refresh_for_unrelated_failure(monkeypatch):
    refresh_calls = []
    monkeypatch.setattr(trading_client, "refresh_access_token", lambda: refresh_calls.append(True))
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=trading_xml("Failure", "The item cannot be revised."))
    )
    http = httpx.AsyncClient(transport=transport)

    async def run():
        try:
            client = TradingClient(client=http, access_token="valid-token")
            await client.call("GetItem", element("GetItemRequest"))
        finally:
            await http.aclose()

    with pytest.raises(TradingAPIError, match="cannot be revised"):
        asyncio.run(run())
    assert not refresh_calls


def test_view_item_images_returns_real_image_content_without_bytes_in_metadata(monkeypatch):
    async def fetch(_):
        return service.ModelListingImages(
            item_id="123456789012",
            total_images=2,
            start_index=0,
            images=[service.ModelListingImage(
                index=0,
                data=b"jpeg-image-bytes",
                width=768,
                height=512,
            )],
        )

    monkeypatch.setattr(trading_server, "fetch_item_images", fetch)
    result = asyncio.run(trading_server.view_item_images(ViewItemImagesInput(item_id="123456789012")))
    image_blocks = [block for block in result.content if block.type == "image"]
    assert len(image_blocks) == 1
    assert image_blocks[0].mimeType == "image/jpeg"
    assert image_blocks[0].data
    assert result.structured_content["has_more"] is True
    assert result.structured_content["next_start_index"] == 1
    assert result.structured_content["images"][0]["status"] == "ok"
    assert result.structured_content["images"][0]["width"] == 768
    assert "jpeg-image-bytes" not in str(result.structured_content)
    assert "i.ebayimg.com" not in str(result.structured_content)


def test_view_item_images_defaults_to_one_and_rejects_large_batches():
    assert ViewItemImagesInput(item_id="123456789012").limit == 1
    with pytest.raises(ValidationError):
        ViewItemImagesInput(item_id="123456789012", limit=4)


def test_direct_add_contract_has_no_fee_ceiling():
    schema = AddFixedPriceItemInput.model_json_schema()
    assert set(schema["properties"]) == {"proposal", "verification_token"}


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


def test_end_fixed_price_item_reads_current_state_and_proves_unsold_end():
    client = FakeTradingClient()
    listing = asyncio.run(service.get_item(client.item_id, client))
    result = asyncio.run(service.end_fixed_price_item(EndFixedPriceItemInput(
        item_id=client.item_id,
        expected_revision_token=listing.revision_token,
        expected_price_gbp=listing.price_gbp,
    ), client))
    assert result.status == "ended"
    assert result.final_listing.status == "Completed"
    assert result.final_listing.quantity_sold == 0
    assert [name for name, _ in client.calls].count("EndFixedPriceItem") == 1


def test_end_fixed_price_item_refuses_a_sale_before_any_end_call():
    client = FakeTradingClient()
    client.sold = True
    listing = asyncio.run(service.get_item(client.item_id, client))
    with pytest.raises(ValueError, match="has sales"):
        asyncio.run(service.end_fixed_price_item(EndFixedPriceItemInput(
            item_id=client.item_id,
            expected_revision_token=listing.revision_token,
            expected_price_gbp=listing.price_gbp,
        ), client))
    assert not any(name == "EndFixedPriceItem" for name, _ in client.calls)


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


def test_reported_fee_metadata_does_not_block_add():
    client = FakeTradingClient()
    client.verify_fee = Decimal("1.25")
    verified = asyncio.run(service.verify_add_fixed_price_item(proposal(), client))
    params = AddFixedPriceItemInput(
        proposal=proposal(), verification_token=verified.verification_token
    )
    result = asyncio.run(service.add_fixed_price_item(params, client))
    assert result.status == "published"
    assert any(name == "AddFixedPriceItem" for name, _ in client.calls)


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
        proposal=proposal(), verification_token=verified.verification_token
    ), client))
    assert result.status == "published"
    assert result.item_id == client.item_id
    assert client.added_uuid == verified_uuid
    assert result.final_listing.revision_token


def test_direct_add_serializes_sku_and_metric_package_details():
    client = FakeTradingClient()
    asyncio.run(service.verify_add_fixed_price_item(proposal(), client))
    request = next(request for name, request in client.calls if name == "VerifyAddFixedPriceItem")
    assert value(request, "Item/SKU") == "SKU-001"
    assert value(request, "Item/InventoryTrackingMethod") == "SKU"
    assert value(request, "Item/ShippingPackageDetails/MeasurementUnit") == "Metric"
    assert value(request, "Item/ShippingPackageDetails/ShippingPackage") == "ParcelOrPaddedEnvelope"
    assert value(request, "Item/ShippingPackageDetails/WeightMajor") == "1"
    assert value(request, "Item/ShippingPackageDetails/WeightMinor") == "250"
    assert find(request, "Item/ShippingPackageDetails/WeightMajor").attrib["unit"] == "kg"
    assert find(request, "Item/ShippingPackageDetails/WeightMinor").attrib["unit"] == "gr"


def test_duplicate_uuid_recovers_original_item_as_idempotent_success():
    client = FakeTradingClient()
    client.duplicate = True
    verified = asyncio.run(service.verify_add_fixed_price_item(proposal(), client))
    result = asyncio.run(service.add_fixed_price_item(AddFixedPriceItemInput(
        proposal=proposal(), verification_token=verified.verification_token
    ), client))
    assert result.item_id == client.item_id
    assert result.idempotent_recovery is True


def test_variation_proposal_requires_complete_picture_mapping_for_its_single_dimension():
    incomplete = variation_proposal().model_dump(mode="json")
    incomplete["picture_mapping"] = {
        "dimension": "Finish",
        "sets": [{"value": "Brass", "picture_urls": ["https://i.ebayimg.com/images/g/brass/s-l1600.jpg"]}],
    }
    with pytest.raises(ValidationError, match="cover exactly every value"):
        MultiVariationFixedPriceListingProposal(**incomplete)
    overlapping = variation_proposal().model_dump(mode="json")
    overlapping["item_specifics"] = {"Finish": ["Brass"]}
    with pytest.raises(ValidationError, match="cannot also be variation dimensions"):
        MultiVariationFixedPriceListingProposal(**overlapping)


def test_variation_verify_serializes_correct_xml_shape_and_returns_durable_identity():
    client = FakeTradingClient()
    verified = asyncio.run(service.verify_add_fixed_price_variations(variation_proposal(), client))
    request = next(request for name, request in client.calls if name == "VerifyAddFixedPriceItem")
    item = find(request, "Item")
    assert verified.valid is True
    assert verified.verification_token
    assert verified.uuid and len(verified.uuid) == 32
    assert verified.proposal_digest and len(verified.proposal_digest) == 64
    assert value(request, "Item/UUID") == verified.uuid
    assert find(request, "Item/StartPrice") is None
    assert find(request, "Item/Quantity") is None
    variations = find(item, "Variations")
    assert [node.tag.rsplit("}", 1)[-1] for node in variations] == [
        "Variation", "Variation", "Pictures", "VariationSpecificsSet",
    ]
    assert value(variations, "Pictures/VariationSpecificName") == "Finish"
    assert [value(node, "VariationSpecificValue") for node in findall(variations, "Pictures/VariationSpecificPictureSet")] == [
        "Brass", "Steel",
    ]
    dimensions = {
        value(entry, "Name"): [node.text for node in findall(entry, "Value")]
        for entry in findall(variations, "VariationSpecificsSet/NameValueList")
    }
    assert dimensions == {"Finish": ["Brass", "Steel"], "Size": ["Small"]}


def test_key_postage_uses_distinct_business_and_combined_postage_discount_profiles():
    client = FakeTradingClient()
    proposal = key_postage_variation_proposal()

    asyncio.run(service.verify_add_fixed_price_variations(proposal, client))

    request = next(request for name, request in client.calls if name == "VerifyAddFixedPriceItem")
    assert value(request, "Item/SellerProfiles/SellerShippingProfile/ShippingProfileID") == "key-postage-policy"
    assert value(request, "Item/ShippingDetails/ShippingDiscountProfileID") == "key-combined-discount-policy"
    assert [value(node, "StartPrice") for node in findall(request, "Item/Variations/Variation")] == ["3.04", "3.04"]
    assert b"3.35" not in ET.tostring(request, encoding="utf-8")
    assert proposal.buyer_paid_postage.first_item_gbp == Decimal("1.50")
    assert proposal.buyer_paid_postage.additional_item_gbp == Decimal("0.50")
    assert proposal.buyer_paid_postage.simple_delivery is False


def test_buyer_paid_postage_requires_distinct_shipping_and_combined_discount_policy_ids():
    payload = variation_proposal().model_dump(mode="json")
    payload["buyer_paid_postage"] = {
        "first_item_gbp": "1.50", "additional_item_gbp": "0.50", "simple_delivery": False,
    }
    with pytest.raises(ValidationError, match="shipping business-policy ID"):
        MultiVariationFixedPriceListingProposal(**payload)
    payload["shipping_profile_id"] = "key-postage-policy"
    with pytest.raises(ValidationError, match="combined-postage discount-policy ID"):
        MultiVariationFixedPriceListingProposal(**payload)


def test_get_item_exposes_distinct_shipping_business_policy_and_discount_rule():
    client = FakeTradingClient()
    original_call = client.call

    async def call_with_policies(name, request):
        if name != "GetItem":
            return await original_call(name, request)
        result = item_response()
        item = find(result.root, "Item")
        profiles = element("SellerProfiles", parent=item)
        shipping = element("SellerShippingProfile", parent=profiles)
        element("ShippingProfileID", "239238622016", shipping)
        details = element("ShippingDetails", parent=item)
        element("ShippingDiscountProfileID", "275444326016", details)
        return result

    client.call = call_with_policies
    listing = asyncio.run(service.get_item(client.item_id, client))

    assert listing.policies.shipping_profile_id == "239238622016"
    assert listing.policies.shipping_discount_profile_id == "275444326016"


def test_five_mrn_key_codes_use_one_dimension_with_complete_picture_mapping():
    client = FakeTradingClient()
    verified = asyncio.run(service.verify_add_fixed_price_variations(key_code_variation_proposal(), client))
    request = next(request for name, request in client.calls if name == "VerifyAddFixedPriceItem")
    variations = find(request, "Item/Variations")
    assert verified.valid is True
    assert value(variations, "Pictures/VariationSpecificName") == "Key Code"
    assert len(findall(variations, "Variation")) == 5
    assert all(
        value(entry, "VariationSpecifics/NameValueList/Name") == "Key Code"
        for entry in findall(variations, "Variation")
    )
    assert [value(entry, "VariationSpecificValue") for entry in findall(
        variations, "Pictures/VariationSpecificPictureSet"
    )] == ["MRN-001", "MRN-002", "MRN-003", "MRN-004", "MRN-005"]
    dimension_set = findall(variations, "VariationSpecificsSet/NameValueList")
    assert len(dimension_set) == 1
    assert value(dimension_set[0], "Name") == "Key Code"
    assert [node.text for node in findall(dimension_set[0], "Value")] == [
        "MRN-001", "MRN-002", "MRN-003", "MRN-004", "MRN-005",
    ]


def test_key_code_master_creation_uses_natural_dropdown_order():
    payload = key_code_variation_proposal().model_dump(mode="json")
    selectors = [
        "FR865 — Unbranded — TLL-158-TL",
        "FR795 — Unbranded — TLL-159-TL",
        "FR852 — ROMAC — TLL-160-TL",
    ]
    payload["variations"] = [
        {
            "sku": f"TLL-{158 + index:03d}-TL", "price_gbp": "4.95", "quantity": 1,
            "specifics": {"Key Code": selector},
        }
        for index, selector in enumerate(selectors)
    ]
    payload["picture_mapping"] = {
        "dimension": "Key Code",
        "sets": [
            {"value": selector, "picture_urls": [f"https://i.ebayimg.com/images/g/{index}/s-l1600.jpg"]}
            for index, selector in enumerate(selectors)
        ],
    }
    client = FakeTradingClient()

    asyncio.run(service.verify_add_fixed_price_variations(
        MultiVariationFixedPriceListingProposal(**payload), client,
    ))

    request = next(request for name, request in client.calls if name == "VerifyAddFixedPriceItem")
    matrix = find(request, "Item/Variations")
    expected = [
        "FR795 — Unbranded — TLL-159-TL",
        "FR852 — ROMAC — TLL-160-TL",
        "FR865 — Unbranded — TLL-158-TL",
    ]
    assert [value(entry, "VariationSpecificValue") for entry in findall(
        matrix, "Pictures/VariationSpecificPictureSet",
    )] == expected
    assert [node.text for node in findall(
        matrix, "VariationSpecificsSet/NameValueList/Value",
    )] == expected


def test_one_key_code_dimension_survives_add_get_item_readback():
    client = FakeTradingClient()
    readback = item_response(client.item_id)
    item = find(readback.root, "Item")
    variations = element("Variations", parent=item)
    codes = ("MRN-001", "MRN-002", "MRN-003", "MRN-004", "MRN-005")
    for code in codes:
        variation = element("Variation", parent=variations)
        element("SKU", f"KEY-{code}", variation)
        element("StartPrice", "12.50", variation)
        element("Quantity", 1, variation)
        specifics = element("VariationSpecifics", parent=variation)
        pair = element("NameValueList", parent=specifics)
        element("Name", "Key Code", pair)
        element("Value", code, pair)
    pictures = element("Pictures", parent=variations)
    element("VariationSpecificName", "Key Code", pictures)
    for code in codes:
        picture_set = element("VariationSpecificPictureSet", parent=pictures)
        element("VariationSpecificValue", code, picture_set)
        element("PictureURL", f"https://i.ebayimg.com/images/g/{code}/s-l1600.jpg", picture_set)
    dimension_set = element("VariationSpecificsSet", parent=variations)
    pair = element("NameValueList", parent=dimension_set)
    element("Name", "Key Code", pair)
    for code in codes:
        element("Value", code, pair)

    original_call = client.call

    async def custom_call(name, request):
        if name == "GetItem":
            return readback
        return await original_call(name, request)

    client.call = custom_call
    listing_proposal = key_code_variation_proposal()
    verified = asyncio.run(service.verify_add_fixed_price_variations(listing_proposal, client))
    result = asyncio.run(service.add_fixed_price_variations(AddFixedPriceVariationsInput(
        proposal=listing_proposal, verification_token=verified.verification_token,
    ), client))
    details = result.final_listing.variation_details
    assert details.dimensions == {"Key Code": list(codes)}
    assert [entry.specifics for entry in details.variations] == [
        {"Key Code": code} for code in codes
    ]
    assert details.picture_dimension == "Key Code"
    assert set(details.picture_sets) == set(codes)


def test_variation_add_reuses_verified_uuid_and_reads_back_normalized_variations():
    client = FakeTradingClient()
    readback = item_response(client.item_id)
    item = find(readback.root, "Item")
    variations = element("Variations", parent=item)
    for sku, finish, quantity in (("ACME-BRASS-S", "Brass", 2), ("ACME-STEEL-S", "Steel", 3)):
        variation = element("Variation", parent=variations)
        element("SKU", sku, variation)
        element("StartPrice", "12.50", variation)
        element("Quantity", quantity, variation)
        specifics = element("VariationSpecifics", parent=variation)
        for name, specific_value in (("Finish", finish), ("Size", "Small")):
            pair = element("NameValueList", parent=specifics)
            element("Name", name, pair)
            element("Value", specific_value, pair)
    pictures = element("Pictures", parent=variations)
    element("VariationSpecificName", "Finish", pictures)
    for finish in ("Brass", "Steel"):
        picture_set = element("VariationSpecificPictureSet", parent=pictures)
        element("VariationSpecificValue", finish, picture_set)
        element("PictureURL", f"https://i.ebayimg.com/images/g/{finish}/s-l1600.jpg", picture_set)
    dimension_set = element("VariationSpecificsSet", parent=variations)
    for name, values in (("Finish", ("Brass", "Steel")), ("Size", ("Small",))):
        pair = element("NameValueList", parent=dimension_set)
        element("Name", name, pair)
        for specific_value in values:
            element("Value", specific_value, pair)

    original_call = client.call

    async def custom_call(name, request):
        if name == "GetItem":
            return readback
        return await original_call(name, request)

    client.call = custom_call
    verified = asyncio.run(service.verify_add_fixed_price_variations(variation_proposal(), client))
    result = asyncio.run(service.add_fixed_price_variations(AddFixedPriceVariationsInput(
        proposal=variation_proposal(), verification_token=verified.verification_token,
    ), client))
    assert client.added_uuid == verified.uuid == result.uuid
    assert result.proposal_digest == verified.proposal_digest
    assert result.final_listing.variation_details.picture_dimension == "Finish"
    assert result.final_listing.variation_details.picture_sets["Steel"][0].startswith("https://i.ebayimg.com/")
    assert [variation.sku for variation in result.final_listing.variation_details.variations] == [
        "ACME-BRASS-S", "ACME-STEEL-S",
    ]


def test_variation_verification_digest_rejects_changed_content_but_allows_saved_uuid_on_reverify():
    client = FakeTradingClient()
    verified = asyncio.run(service.verify_add_fixed_price_variations(variation_proposal(), client))
    changed = variation_proposal().model_copy(update={"title": "Changed title"})
    with pytest.raises(ValueError, match="changed after verification"):
        asyncio.run(service.add_fixed_price_variations(AddFixedPriceVariationsInput(
            proposal=changed, verification_token=verified.verification_token,
        ), client))
    retried = asyncio.run(service.verify_add_fixed_price_variations(variation_proposal(verified.uuid.lower()), client))
    assert retried.uuid == verified.uuid
    assert retried.proposal_digest == verified.proposal_digest


def test_append_key_variation_emits_complete_golden_matrix_and_reads_it_back():
    client = FakeVariationAppendClient()
    before = asyncio.run(service.get_item(client.item_id, client))
    params = append_key_input(before.revision_token)
    result = asyncio.run(service.append_fixed_price_variation(params, client))

    assert result.status == "appended"
    assert result.operation_id == params.operation_id
    assert result.idempotent_recovery is False
    assert [entry.sku for entry in result.final_listing.variation_details.variations] == [
        "TLL-001-TL", "TLL-002-TL", "TLL-038-TL",
    ]
    request = next(request for name, request in client.calls if name == "ReviseFixedPriceItem")
    item = find(request, "Item")
    assert [node.tag.rsplit("}", 1)[-1] for node in item] == ["ItemID", "Variations"]
    matrix = find(item, "Variations")
    assert [node.tag.rsplit("}", 1)[-1] for node in matrix] == [
        "Variation", "Variation", "Variation", "Pictures", "VariationSpecificsSet",
    ]
    assert find(item, "StartPrice") is None
    assert find(item, "Quantity") is None
    assert [value(entry, "SKU") for entry in findall(matrix, "Variation")] == [
        "TLL-001-TL", "TLL-002-TL", "TLL-038-TL",
    ]
    sets = findall(matrix, "Pictures/VariationSpecificPictureSet")
    assert value(find(matrix, "Pictures"), "VariationSpecificName") == "Key Code"
    assert value(sets[-1], "VariationSpecificValue") == "MRN7 — Romac — TLL-038-TL"
    assert [picture.text for picture in findall(sets[-1], "PictureURL")] == params.picture_urls
    values = [node.text for node in findall(matrix, "VariationSpecificsSet/NameValueList/Value")]
    assert values == [
        "MRN1 — Union — TLL-001-TL",
        "MRN2 — Union — TLL-002-TL",
        "MRN7 — Romac — TLL-038-TL",
    ]


def test_append_repairs_misaligned_dropdown_order_and_uses_natural_key_code_order():
    variations = [
        *key_master_variations(2),
        {
            "sku": "TLL-020-TL", "price": "4.95", "quantity": 1, "quantity_sold": 0,
            "selector": "MRN20 — Union — TLL-020-TL",
            "urls": [
                "https://i.ebayimg.com/images/g/MRN20-front/s-l1600.jpg",
                "https://i.ebayimg.com/images/g/MRN20-rear/s-l1600.jpg",
            ],
        },
    ]
    client = FakeVariationAppendClient(variations)
    client.specificity_values = [
        "MRN20 — Union — TLL-020-TL",
        "MRN1 — Union — TLL-001-TL",
        "MRN2 — Union — TLL-002-TL",
    ]
    before = asyncio.run(service.get_item(client.item_id, client))

    result = asyncio.run(service.append_fixed_price_variation(append_key_input(before.revision_token), client))

    assert result.status == "appended"
    assert result.final_listing.variation_details.dimensions["Key Code"] == [
        "MRN1 — Union — TLL-001-TL",
        "MRN2 — Union — TLL-002-TL",
        "MRN7 — Romac — TLL-038-TL",
        "MRN20 — Union — TLL-020-TL",
    ]


def test_reorder_key_master_repairs_dropdown_order_without_changing_members():
    variations = [
        {
            "sku": "TLL-158-TL", "price": "4.95", "quantity": 1, "quantity_sold": 0,
            "selector": "FR865 — Unbranded — TLL-158-TL",
            "urls": ["https://i.ebayimg.com/images/g/FR865-front/s-l1600.jpg"],
        },
        {
            "sku": "TLL-159-TL", "price": "4.95", "quantity": 1, "quantity_sold": 0,
            "selector": "FR795 — Unbranded — TLL-159-TL",
            "urls": ["https://i.ebayimg.com/images/g/FR795-front/s-l1600.jpg"],
        },
        {
            "sku": "TLL-160-TL", "price": "4.95", "quantity": 1, "quantity_sold": 0,
            "selector": "FR852 — ROMAC — TLL-160-TL",
            "urls": ["https://i.ebayimg.com/images/g/FR852-front/s-l1600.jpg"],
        },
    ]
    client = FakeVariationAppendClient(variations)
    before = asyncio.run(service.get_item(client.item_id, client))

    result = asyncio.run(service.reorder_fixed_price_variations(
        ReorderFixedPriceVariationsInput(
            item_id=client.item_id, expected_revision_token=before.revision_token,
            operation_id="reorder-FR-1",
        ),
        client,
    ))

    assert result.status == "reordered"
    request = next(request for name, request in client.calls if name == "ReviseFixedPriceItem")
    matrix = find(request, "Item/Variations")
    assert [node.tag.rsplit("}", 1)[-1] for node in matrix] == ["VariationSpecificsSet"]
    assert [entry.sku for entry in result.final_listing.variation_details.variations] == [
        "TLL-158-TL", "TLL-159-TL", "TLL-160-TL",
    ]
    assert result.final_listing.variation_details.dimensions["Key Code"] == [
        "FR795 — Unbranded — TLL-159-TL",
        "FR852 — ROMAC — TLL-160-TL",
        "FR865 — Unbranded — TLL-158-TL",
    ]
    assert result.final_listing.variation_details.picture_sets == {
        entry["selector"]: entry["urls"] for entry in variations
    }


def test_reorder_recovers_after_ambiguous_timeout_when_readback_is_ordered():
    variations = [
        {
            "sku": "TLL-158-TL", "price": "4.95", "quantity": 1, "quantity_sold": 0,
            "selector": "FR865 — Unbranded — TLL-158-TL",
            "urls": ["https://i.ebayimg.com/images/g/FR865/s-l1600.jpg"],
        },
        {
            "sku": "TLL-159-TL", "price": "4.95", "quantity": 1, "quantity_sold": 0,
            "selector": "FR795 — Unbranded — TLL-159-TL",
            "urls": ["https://i.ebayimg.com/images/g/FR795/s-l1600.jpg"],
        },
    ]
    client = FakeVariationAppendClient(variations)
    client.raise_after_revise = True
    before = asyncio.run(service.get_item(client.item_id, client))

    result = asyncio.run(service.reorder_fixed_price_variations(
        ReorderFixedPriceVariationsInput(
            item_id=client.item_id, expected_revision_token=before.revision_token,
            operation_id="reorder-FR-timeout",
        ),
        client,
    ))

    assert result.status == "already_ordered"
    assert result.idempotent_recovery is True
    assert result.final_listing.variation_details.dimensions["Key Code"] == [
        "FR795 — Unbranded — TLL-159-TL", "FR865 — Unbranded — TLL-158-TL",
    ]


def test_append_uses_available_stock_for_sold_variations_without_replenishing_them():
    variations = key_master_variations()
    variations[0]["quantity"] = 3
    variations[0]["quantity_sold"] = 2
    client = FakeVariationAppendClient(variations)
    before = asyncio.run(service.get_item(client.item_id, client))
    result = asyncio.run(service.append_fixed_price_variation(append_key_input(before.revision_token), client))
    request = next(request for name, request in client.calls if name == "ReviseFixedPriceItem")
    first = findall(request, "Item/Variations/Variation")[0]
    assert value(first, "Quantity") == "1"
    preserved = result.final_listing.variation_details.variations[0]
    assert preserved.quantity == 3
    assert preserved.quantity_sold == 2


def test_append_rejects_non_eps_or_duplicate_photo_urls_at_the_boundary():
    with pytest.raises(ValidationError, match="EPS"):
        AppendFixedPriceVariationInput(
            **append_key_input("a" * 64).model_dump(mode="json") | {
                "picture_urls": ["https://example.com/front.jpg", "https://i.ebayimg.com/images/g/rear/s-l1600.jpg"],
            }
        )
    with pytest.raises(ValidationError, match="distinct"):
        AppendFixedPriceVariationInput(
            **append_key_input("a" * 64).model_dump(mode="json") | {
                "picture_urls": [
                    "https://i.ebayimg.com/images/g/same/s-l1600.jpg",
                    "https://i.ebayimg.com/images/g/same/s-l1600.jpg",
                ],
            }
        )


def test_append_rejects_stale_baseline_before_revising():
    client = FakeVariationAppendClient()
    stale_token = asyncio.run(service.get_item(client.item_id, client)).revision_token
    client.variations.append(key_master_variations(3)[-1])
    client.specificity_values.append(key_master_variations(3)[-1]["selector"])
    with pytest.raises(ValueError, match="changed after"):
        asyncio.run(service.append_fixed_price_variation(append_key_input(stale_token), client))
    assert not any(name == "ReviseFixedPriceItem" for name, _ in client.calls)


def test_append_rejects_duplicate_sku_or_selector_before_revising():
    client = FakeVariationAppendClient()
    revision = asyncio.run(service.get_item(client.item_id, client)).revision_token
    with pytest.raises(ValueError, match="physical SKU"):
        asyncio.run(service.append_fixed_price_variation(append_key_input(
            revision,
            sku="TLL-001-TL",
            selector="MRN7 — Romac — TLL-038-TL",
        ), client))
    with pytest.raises(ValueError, match="selector"):
        asyncio.run(service.append_fixed_price_variation(append_key_input(
            revision,
            sku="TLL-038-TL",
            selector="MRN1 — Union — TLL-001-TL",
        ), client))
    assert not any(name == "ReviseFixedPriceItem" for name, _ in client.calls)


def test_append_rejects_the_250_variation_capacity_before_revising():
    client = FakeVariationAppendClient(key_master_variations(250))
    revision = asyncio.run(service.get_item(client.item_id, client)).revision_token
    with pytest.raises(ValueError, match="maximum 250"):
        asyncio.run(service.append_fixed_price_variation(append_key_input(revision), client))
    assert not any(name == "ReviseFixedPriceItem" for name, _ in client.calls)


def test_append_recovers_exact_already_applied_member_without_revision():
    desired = {
        "sku": "TLL-038-TL",
        "price": "4.95",
        "quantity": 1,
        "quantity_sold": 0,
        "selector": "MRN7 — Romac — TLL-038-TL",
        "urls": [
            "https://i.ebayimg.com/images/g/MRN7-front/s-l1600.jpg",
            "https://i.ebayimg.com/images/g/MRN7-rear/s-l1600.jpg",
        ],
    }
    client = FakeVariationAppendClient([*key_master_variations(), desired])
    result = asyncio.run(service.append_fixed_price_variation(append_key_input("f" * 64), client))
    assert result.status == "already_applied"
    assert result.idempotent_recovery is True
    assert not any(name == "ReviseFixedPriceItem" for name, _ in client.calls)


def test_append_reads_ebay_before_recovering_an_ambiguous_timeout():
    client = FakeVariationAppendClient()
    revision = asyncio.run(service.get_item(client.item_id, client)).revision_token
    client.raise_after_revise = True
    result = asyncio.run(service.append_fixed_price_variation(append_key_input(revision), client))
    assert result.status == "already_applied"
    assert result.idempotent_recovery is True
    assert [entry.sku for entry in result.final_listing.variation_details.variations][-1] == "TLL-038-TL"


def test_append_raises_when_readback_changed_a_preexisting_variation():
    client = FakeVariationAppendClient()
    revision = asyncio.run(service.get_item(client.item_id, client)).revision_token
    client.corrupt_readback = True
    with pytest.raises(TradingAPIError, match="changed an existing variation"):
        asyncio.run(service.append_fixed_price_variation(append_key_input(revision), client))


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
