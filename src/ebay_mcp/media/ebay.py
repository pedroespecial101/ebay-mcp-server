"""Upload privately staged photographs to eBay Picture Services via Media API."""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from ebay_mcp.media.storage import get_staged_bytes
from ebay_service import get_ebay_access_token
from models.ebay.trading import UploadedListingPicture
from utils.api_utils import get_standard_ebay_headers, is_token_error

MEDIA_UPLOAD_URL = "https://apim.ebay.com/commerce/media/v1_beta/image/create_image_from_file"


class EbayMediaUploadError(RuntimeError):
    pass


def _expiration_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


async def upload_staged_pictures(
    image_refs: list[str], client: httpx.AsyncClient | None = None
) -> list[UploadedListingPicture]:
    token = await get_ebay_access_token()
    if is_token_error(token):
        raise EbayMediaUploadError("Seller authentication is unavailable; run the eBay login tool.")
    owned_client = client is None
    http = client or httpx.AsyncClient(timeout=45)
    results: list[UploadedListingPicture] = []
    try:
        for image_ref in image_refs:
            raw, filename = await asyncio.to_thread(get_staged_bytes, image_ref)
            headers = get_standard_ebay_headers(token)
            headers.pop("Content-Type", None)
            response = await http.post(
                MEDIA_UPLOAD_URL,
                headers=headers,
                files={"image": (filename, raw, "image/jpeg")},
            )
            if response.status_code != 201:
                raise EbayMediaUploadError(f"eBay rejected an image upload (HTTP {response.status_code}).")
            try:
                body = response.json()
            except ValueError as exc:
                raise EbayMediaUploadError("eBay returned an invalid image-upload response.") from exc
            image_url = body.get("imageUrl")
            if not image_url:
                raise EbayMediaUploadError("eBay accepted an image but returned no EPS URL.")
            location = response.headers.get("location", "")
            results.append(UploadedListingPicture(
                image_ref=image_ref,
                image_id=location.rstrip("/").split("/")[-1] or None,
                image_url=image_url,
                expiration_date=_expiration_date(body.get("expirationDate")),
            ))
    finally:
        if owned_client:
            await http.aclose()
    return results
