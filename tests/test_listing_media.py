from io import BytesIO

import pytest
from PIL import Image

from ebay_mcp.media import storage
from ebay_mcp.listing.workflow import _aspect_constraints, _inventory_matches, _offer_matches
from models.ebay.listing_workflow import SimpleListingInput


def jpeg_bytes(size=(120, 80), color="red"):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, "JPEG", exif=b"not-retained")
    return output.getvalue()


def test_normalize_image_outputs_bounded_rgb_jpeg_without_exif():
    result, width, height = storage.normalize_image(jpeg_bytes((5000, 1000)), "photo.jpg")
    assert (width, height) == (4000, 800)
    with Image.open(BytesIO(result)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert not image.getexif()


def test_normalize_rejects_non_image():
    with pytest.raises(storage.MediaStorageError):
        storage.normalize_image(b"not an image", "bad.txt")


def test_prepare_model_image_outputs_small_vision_safe_jpeg():
    result, width, height = storage.prepare_model_image(jpeg_bytes((5000, 2000)), "photo.jpg")
    assert max(width, height) <= storage.MAX_MODEL_IMAGE_EDGE
    assert len(result) <= storage.MAX_MODEL_IMAGE_BYTES
    with Image.open(BytesIO(result)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert not image.getexif()


def test_private_network_hosts_are_rejected(monkeypatch):
    monkeypatch.setattr(storage.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(storage.MediaStorageError, match="private or unsafe"):
        storage._validate_public_host("example.invalid")


def test_local_import_cannot_escape_root(tmp_path, monkeypatch):
    monkeypatch.setenv("EBAY_IMAGE_IMPORT_DIR", str(tmp_path / "inbox"))
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(jpeg_bytes())
    source = storage.ImageSource(kind="local_file", value=str(outside))
    with pytest.raises(storage.MediaStorageError, match="inside"):
        import asyncio
        asyncio.run(storage.stage_source(source))


def test_aspect_constraints_normalize_ebay_taxonomy():
    parsed = _aspect_constraints({"aspects": [{"localizedAspectName": "Brand", "aspectConstraint": {
        "aspectRequired": True, "itemToAspectCardinality": "SINGLE", "aspectMode": "SELECTION_ONLY"},
        "aspectValues": [{"localizedValue": "Acme"}]}]})
    assert parsed["Brand"] == {"required": True, "multi": False, "mode": "SELECTION_ONLY", "values": {"Acme"}}


def test_inventory_match_is_strict_for_idempotency():
    listing = SimpleListingInput(sku="sku-1", title="Title", description="Description", price_gbp="10.00",
        category_id="123", condition="USED_GOOD", condition_description="Light wear", aspects={"Brand": ["Acme"]},
        image_refs=["r2:staging/seller/x/photo.jpg"])
    item = {"condition": "USED_GOOD", "conditionDescription": "Light wear",
        "availability": {"shipToLocationAvailability": {"quantity": 1}},
        "product": {"title": "Title", "description": "Description", "aspects": {"Brand": ["Acme"]}}}
    assert _inventory_matches(item, listing)
    item["product"]["title"] = "Different"
    assert not _inventory_matches(item, listing)


def test_offer_match_includes_price_category_and_fixed_price_defaults():
    listing = SimpleListingInput(sku="sku-1", title="Title", description="Description", price_gbp="10.00",
        category_id="123", condition="USED_GOOD", condition_description="Light wear", aspects={},
        image_refs=["r2:staging/seller/x/photo.jpg"])
    offer = {"sku": "sku-1", "marketplaceId": "EBAY_GB", "format": "FIXED_PRICE", "listingDuration": "GTC",
        "categoryId": "123", "availableQuantity": 1, "pricingSummary": {"price": {"value": "10.00", "currency": "GBP"}}}
    assert _offer_matches(offer, listing)
    offer["pricingSummary"]["price"]["value"] = "11.00"
    assert not _offer_matches(offer, listing)
