import asyncio
from io import BytesIO

import httpx
import pytest
from PIL import Image

from ebay_mcp.media import ebay as ebay_media
from ebay_mcp.media import storage
from ebay_mcp.media import server as media_server
from ebay_mcp.listing.workflow import _aspect_constraints, _inventory_matches, _offer_matches
from models.ebay.listing_workflow import SimpleListingInput, ViewEbayImageInput


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
    result, width, height = storage.prepare_model_image(jpeg_bytes((5000, 2000)), "photo.jpg", max_edge=768)
    assert max(width, height) <= 768
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
        asyncio.run(storage.stage_source(source))


def test_listing_studio_has_a_separate_restricted_import_root(tmp_path, monkeypatch):
    inbox = tmp_path / "existing-inbox"
    studio = tmp_path / "listing-studio" / "images" / "ebay"
    studio.mkdir(parents=True)
    image = studio / "photo.jpg"
    image.write_bytes(jpeg_bytes())
    monkeypatch.setenv("EBAY_IMAGE_IMPORT_DIR", str(inbox))
    monkeypatch.setenv("EBAY_LISTING_STUDIO_IMPORT_DIR", str(studio))

    expected = storage.StagedImage(
        image_ref="r2:staging/seller/test/photo.jpg",
        filename="photo.jpg",
        size=100,
        width=120,
        height=80,
        uploaded_at="2026-07-13T00:00:00+00:00",
    )
    monkeypatch.setattr(storage, "stage_bytes", lambda data, filename: expected)
    source = storage.ImageSource(kind="local_file", value=str(image))
    assert asyncio.run(storage.stage_source(source)) == expected


def test_view_ebay_image_returns_one_normalized_image_without_source_url(monkeypatch):
    async def download(_url, allowed_hosts=None):
        assert allowed_hosts == media_server.EBAY_IMAGE_HOSTS
        return jpeg_bytes((1200, 800)), "s-l1600.jpg"

    monkeypatch.setattr(media_server, "download_public_image", download)
    result = asyncio.run(media_server.view_ebay_image(ViewEbayImageInput(
        url="https://i.ebayimg.com/images/g/example/s-l1600.jpg",
        max_px=512,
    )))
    image_blocks = [block for block in result.content if block.type == "image"]
    assert len(image_blocks) == 1
    assert image_blocks[0].mimeType == "image/jpeg"
    assert result.structured_content["source"] == "ebay_image_cdn"
    assert result.structured_content["max_px"] == 512
    assert "i.ebayimg.com" not in str(result.structured_content)


def test_view_ebay_image_rejects_non_ebay_hosts():
    with pytest.raises(ValueError, match="approved eBay image"):
        asyncio.run(media_server.view_ebay_image(ViewEbayImageInput(
            url="https://example.com/image.jpg",
        )))


def test_eps_upload_refreshes_expired_token_once(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(401, json={"errors": [{"errorId": 1001, "message": "Token expired"}]})
        return httpx.Response(
            201,
            json={"imageUrl": "https://i.ebayimg.com/images/g/test/s-l1600.jpg"},
            headers={"location": "https://apim.ebay.com/commerce/media/v1_beta/image/123"},
        )

    async def stale_token():
        return "stale-token"

    monkeypatch.setattr(ebay_media, "get_ebay_access_token", stale_token)
    monkeypatch.setattr(ebay_media, "refresh_access_token", lambda: "fresh-token")
    monkeypatch.setattr(ebay_media, "get_staged_bytes", lambda _ref: (jpeg_bytes(), "photo.jpg"))
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def run():
        try:
            return await ebay_media.upload_staged_pictures(["r2:test"], client=http)
        finally:
            await http.aclose()

    result = asyncio.run(run())
    assert [request.headers["authorization"] for request in requests] == [
        "Bearer stale-token",
        "Bearer fresh-token",
    ]
    assert result[0].image_id == "123"


def test_eps_upload_explains_failed_automatic_refresh(monkeypatch):
    async def stale_token():
        return "stale-token"

    def handler(_request):
        return httpx.Response(401, json={"errors": [{"errorId": 1001, "message": "Token expired"}]})

    monkeypatch.setattr(ebay_media, "get_ebay_access_token", stale_token)
    monkeypatch.setattr(ebay_media, "refresh_access_token", lambda: None)
    monkeypatch.setattr(ebay_media, "get_staged_bytes", lambda _ref: (jpeg_bytes(), "photo.jpg"))
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def run():
        try:
            with pytest.raises(ebay_media.EbayMediaUploadError, match="automatic refresh failed") as exc:
                await ebay_media.upload_staged_pictures(["r2:test"], client=http)
            return str(exc.value)
        finally:
            await http.aclose()

    message = asyncio.run(run())
    assert "1001: Token expired" in message
    assert "retry preparation" in message


def test_eps_upload_explains_rejection_after_refresh(monkeypatch):
    async def stale_token():
        return "stale-token"

    def handler(_request):
        return httpx.Response(401, json={"errors": [{"errorId": 1001, "message": "Invalid token"}]})

    monkeypatch.setattr(ebay_media, "get_ebay_access_token", stale_token)
    monkeypatch.setattr(ebay_media, "refresh_access_token", lambda: "fresh-token")
    monkeypatch.setattr(ebay_media, "get_staged_bytes", lambda _ref: (jpeg_bytes(), "photo.jpg"))
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def run():
        try:
            with pytest.raises(
                ebay_media.EbayMediaUploadError,
                match="after Listing Studio automatically refreshed",
            ) as exc:
                await ebay_media.upload_staged_pictures(["r2:test"], client=http)
            return str(exc.value)
        finally:
            await http.aclose()

    message = asyncio.run(run())
    assert "Seller consent may have been revoked" in message
    assert "1001: Invalid token" in message


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
