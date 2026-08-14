"""Upload privately staged photographs to eBay Picture Services via Media API."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx

from ebay_auth.ebay_auth import refresh_access_token
from ebay_mcp.media.storage import get_staged_bytes
from ebay_service import get_ebay_access_token
from models.ebay.trading import UploadedListingPicture
from utils.api_utils import get_standard_ebay_headers, is_token_error

MEDIA_UPLOAD_URL = "https://apim.ebay.com/commerce/media/v1_beta/image/create_image_from_file"
EPS_503_RETRY_DELAYS_SECONDS = (2.0, 6.0)
logger = logging.getLogger(__name__)


class EbayMediaUploadError(RuntimeError):
    pass


def _response_detail(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if not isinstance(errors, list) or not errors or not isinstance(errors[0], dict):
        return None
    error = errors[0]
    message = error.get("message") or error.get("longMessage")
    code = error.get("errorId")
    parts = [str(value).strip() for value in (code, message) if value]
    return ": ".join(parts)[:300] or None


def _response_suffix(response: httpx.Response) -> str:
    detail = _response_detail(response)
    return f" eBay reported {detail}." if detail else ""


def _upload_error(response: httpx.Response, *, refreshed: bool) -> EbayMediaUploadError:
    suffix = _response_suffix(response)
    if response.status_code == 401 and refreshed:
        return EbayMediaUploadError(
            "eBay still rejected the EPS image upload after Listing Studio automatically "
            "refreshed the seller access token (HTTP 401). Seller consent may have been "
            f"revoked; run the eBay login flow, then retry preparation.{suffix}"
        )
    if response.status_code == 403:
        return EbayMediaUploadError(
            "eBay denied the EPS image upload (HTTP 403). The seller token may lack the "
            f"required sell.inventory permission; run the eBay login flow, then retry preparation.{suffix}"
        )
    return EbayMediaUploadError(
        f"eBay rejected the EPS image upload (HTTP {response.status_code}).{suffix}"
    )


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
            refreshed = False
            retry_delays = iter(EPS_503_RETRY_DELAYS_SECONDS)
            while True:
                headers = get_standard_ebay_headers(token)
                headers.pop("Content-Type", None)
                response = await http.post(
                    MEDIA_UPLOAD_URL,
                    headers=headers,
                    files={"image": (filename, raw, "image/jpeg")},
                )
                if response.status_code == 401 and not refreshed:
                    logger.info("EPS image upload received HTTP 401; refreshing the seller access token once.")
                    token = await asyncio.to_thread(refresh_access_token)
                    if not token or is_token_error(token):
                        raise EbayMediaUploadError(
                            "The EPS image upload found an expired seller access token, but automatic "
                            "refresh failed. Run the eBay login flow, then retry preparation."
                            f"{_response_suffix(response)}"
                        )
                    refreshed = True
                    logger.info("Seller access token refreshed; retrying the EPS image upload.")
                    continue
                if response.status_code == 503:
                    delay = next(retry_delays, None)
                    if delay is not None:
                        logger.warning(
                            "EPS image upload received HTTP 503; retrying the same staged image in %.0f seconds.",
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                break
            if response.status_code != 201:
                raise _upload_error(response, refreshed=refreshed)
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
