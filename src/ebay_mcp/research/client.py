from __future__ import annotations

import asyncio
import base64
import ipaddress
import logging
import socket
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .config import Settings
from .errors import (
    EbayAuthenticationError,
    EbayError,
    EbayRateLimitError,
    ImageDownloadError,
)
from .models import (
    ApiWarning,
    AspectRefinement,
    Category,
    CompatibilityProperty,
    ImageSearchRequest,
    ItemDetail,
    Location,
    Money,
    Refinements,
    RefinementValue,
    SearchItem,
    SearchRequest,
    SearchResponse,
    SellerSummary,
    ShippingSummary,
    SortOrder,
)

logger = logging.getLogger(__name__)

OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"
SORT_VALUES = {
    SortOrder.NEWLY_LISTED: "newlyListed",
    SortOrder.ENDING_SOONEST: "endingSoonest",
    SortOrder.PRICE_ASC: "price",
    SortOrder.PRICE_DESC: "-price",
}
TRANSIENT_STATUS_CODES = {500, 502, 503, 504}


class EbayClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    async def __aenter__(self) -> EbayClient:
        await self._get_http_client()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def search_items(self, request: SearchRequest) -> SearchResponse:
        params = self._search_params(request)
        data = await self._request_json(
            "GET", "/buy/browse/v1/item_summary/search", params=params
        )
        return normalize_search_response(data, request.limit, request.offset)

    async def get_item(self, item_id: str) -> ItemDetail:
        clean_item_id = item_id.strip()
        if not clean_item_id or "/" in clean_item_id:
            raise EbayError("item_id must be a non-empty eBay Browse API item ID")
        data = await self._request_json(
            "GET",
            f"/buy/browse/v1/item/{clean_item_id}",
            params={"fieldgroups": "PRODUCT"},
        )
        return normalize_item_detail(data)

    async def search_by_image(self, request: ImageSearchRequest) -> SearchResponse:
        image = await self._download_public_image(request.image_url)
        return await self.search_by_image_bytes(request, image)

    async def search_by_image_bytes(
        self, request: ImageSearchRequest, image: bytes
    ) -> SearchResponse:
        """Search from trusted private bytes without requiring a public image URL."""
        if not image:
            raise ImageDownloadError("Image was empty")
        if len(image) > self.settings.image_max_bytes:
            raise ImageDownloadError("Image exceeds the 10 MiB image-search limit")
        params = self._image_search_params(request)
        data = await self._request_json(
            "POST",
            "/buy/browse/v1/item_summary/search_by_image",
            params=params,
            json={"image": base64.b64encode(image).decode("ascii")},
        )
        return normalize_search_response(data, request.limit, request.offset)

    def _search_params(self, request: SearchRequest) -> dict[str, str]:
        params: dict[str, str] = {
            "limit": str(request.limit),
            "offset": str(request.offset),
        }
        if request.query:
            params["q"] = request.query
        if request.gtin:
            params["gtin"] = request.gtin
        if request.category_ids:
            params["category_ids"] = ",".join(request.category_ids)
        if request.include_refinements:
            params["fieldgroups"] = "FULL"
        if request.sort in SORT_VALUES:
            params["sort"] = SORT_VALUES[request.sort]

        filters = self._common_filters(
            min_price=request.min_price,
            max_price=request.max_price,
            condition_ids=request.condition_ids,
            buying_options=[option.value for option in request.buying_options],
            item_location_country=request.item_location_country,
        )
        if request.search_in_description:
            filters.append("searchInDescription:true")
        params["filter"] = ",".join(filters)

        if request.aspect_filters:
            params["aspect_filter"] = _format_aspect_filter(
                request.category_ids[0], request.aspect_filters
            )
        if request.vehicle:
            params["compatibility_filter"] = _format_vehicle_filter(
                request.vehicle.model_dump(exclude_none=True)
            )
        return params

    def _image_search_params(self, request: ImageSearchRequest) -> dict[str, str]:
        params = {"limit": str(request.limit), "offset": str(request.offset)}
        if request.category_id:
            params["category_ids"] = request.category_id
        if request.include_refinements:
            params["fieldgroups"] = "FULL"
        params["filter"] = ",".join(
            self._common_filters(
                min_price=request.min_price,
                max_price=request.max_price,
                condition_ids=request.condition_ids,
                buying_options=[option.value for option in request.buying_options],
                item_location_country=request.item_location_country,
            )
        )
        if request.aspect_filters and request.category_id:
            params["aspect_filter"] = _format_aspect_filter(
                request.category_id, request.aspect_filters
            )
        return params

    def _common_filters(
        self,
        *,
        min_price: float | None,
        max_price: float | None,
        condition_ids: list[str],
        buying_options: list[str],
        item_location_country: str | None,
    ) -> list[str]:
        filters = [f"deliveryCountry:{self.settings.delivery_country}"]
        if min_price is not None or max_price is not None:
            lower = _format_number(min_price) if min_price is not None else ""
            upper = _format_number(max_price) if max_price is not None else ""
            filters.extend(
                [f"price:[{lower}..{upper}]", f"priceCurrency:{self.settings.currency}"]
            )
        if condition_ids:
            filters.append(f"conditionIds:{{{'|'.join(condition_ids)}}}")
        if buying_options:
            filters.append(f"buyingOptions:{{{'|'.join(buying_options)}}}")
        if item_location_country:
            filters.append(f"itemLocationCountry:{item_location_country.upper()}")
        return filters

    async def _get_token(self) -> str:
        now = time.monotonic()
        if self._token and now < self._token_expires_at:
            return self._token

        async with self._token_lock:
            now = time.monotonic()
            if self._token and now < self._token_expires_at:
                return self._token

            client_id, client_secret = self.settings.require_credentials()
            client = await self._get_http_client()
            try:
                response = await self._send_with_transient_retry(
                    client,
                    "POST",
                    f"{self.settings.api_base_url}/identity/v1/oauth2/token",
                    auth=httpx.BasicAuth(client_id, client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={"grant_type": "client_credentials", "scope": OAUTH_SCOPE},
                )
            except httpx.RequestError as exc:
                raise EbayAuthenticationError(
                    "Unable to reach the eBay OAuth service"
                ) from exc
            if response.status_code >= 400:
                raise EbayAuthenticationError(
                    f"eBay OAuth failed with HTTP {response.status_code}; check the application credentials"
                )

            payload = response.json()
            token = payload.get("access_token")
            if not token:
                raise EbayAuthenticationError(
                    "eBay OAuth response did not contain an access token"
                )
            expires_in = max(int(payload.get("expires_in", 0)), 0)
            self._token = str(token)
            self._token_expires_at = time.monotonic() + max(
                expires_in - self.settings.token_safety_margin_seconds, 0
            )
            logger.info("Minted a new eBay application access token")
            return self._token

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = await self._get_http_client()
        url = f"{self.settings.api_base_url}{path}"
        token = await self._get_token()
        for auth_attempt in range(2):
            try:
                response = await self._send_with_transient_retry(
                    client,
                    method,
                    url,
                    headers=self._browse_headers(token),
                    params=params,
                    json=json,
                )
            except httpx.RequestError as exc:
                raise EbayError("Unable to reach the eBay Browse API") from exc
            if response.status_code == 401 and auth_attempt == 0:
                # Only invalidate the token rejected by this request. If another
                # concurrent request already refreshed it, keep the newer token.
                if self._token == token:
                    self._token = None
                    self._token_expires_at = 0
                token = await self._get_token()
                continue
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                suffix = f" Retry after {retry_after} seconds." if retry_after else ""
                raise EbayRateLimitError(f"eBay API rate limit reached.{suffix}")
            if response.status_code >= 400:
                raise EbayError(_safe_api_error(response))
            try:
                payload = response.json()
            except ValueError as exc:
                raise EbayError("eBay API returned an invalid JSON response") from exc
            if not isinstance(payload, dict):
                raise EbayError("eBay API returned an unexpected response shape")
            return payload
        raise EbayAuthenticationError("eBay rejected the refreshed application token")

    async def _send_with_transient_retry(
        self, client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        for attempt in range(2):
            try:
                response = await client.request(method, url, **kwargs)
            except httpx.RequestError:
                if attempt:
                    raise
                await asyncio.sleep(0.2)
                continue
            if response.status_code not in TRANSIENT_STATUS_CODES or attempt:
                return response
            await asyncio.sleep(0.2)
        raise AssertionError("unreachable")

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self.settings.request_timeout_seconds,
                follow_redirects=False,
                headers={"User-Agent": "ebay-uk-browse-mcp/0.1.0"},
            )
        return self._http_client

    def _browse_headers(self, token: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Accept-Language": self.settings.locale,
            "Content-Language": self.settings.locale,
            "X-EBAY-C-MARKETPLACE-ID": self.settings.marketplace_id,
        }
        context = f"contextualLocation=country%3D{self.settings.delivery_country}"
        if self.settings.delivery_postal_code:
            context += f"%2Czip%3D{self.settings.delivery_postal_code}"
        headers["X-EBAY-C-ENDUSERCTX"] = context
        return headers

    async def _download_public_image(self, image_url: str) -> bytes:
        current_url = image_url
        client = await self._get_http_client()
        for _ in range(4):
            await _validate_public_https_url(current_url)
            try:
                async with client.stream("GET", current_url) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("Location")
                        if not location:
                            raise ImageDownloadError(
                                "Image redirect had no destination"
                            )
                        current_url = urljoin(current_url, location)
                        continue
                    if response.status_code >= 400:
                        raise ImageDownloadError(
                            f"Image download failed with HTTP {response.status_code}"
                        )
                    content_type = response.headers.get("Content-Type", "").split(
                        ";", 1
                    )[0]
                    if not content_type.startswith("image/"):
                        raise ImageDownloadError(
                            "Image URL did not return an image content type"
                        )
                    content_length = response.headers.get("Content-Length")
                    if (
                        content_length
                        and int(content_length) > self.settings.image_max_bytes
                    ):
                        raise ImageDownloadError(
                            "Image exceeds the 10 MiB download limit"
                        )
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self.settings.image_max_bytes:
                            raise ImageDownloadError(
                                "Image exceeds the 10 MiB download limit"
                            )
                        chunks.append(chunk)
                    if not chunks:
                        raise ImageDownloadError("Downloaded image was empty")
                    return b"".join(chunks)
            except httpx.RequestError as exc:
                raise ImageDownloadError("Unable to download the image") from exc
        raise ImageDownloadError("Image URL exceeded the redirect limit")


async def _validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ImageDownloadError("image_url must be a public HTTPS URL")
    if parsed.username or parsed.password:
        raise ImageDownloadError("image_url must not contain credentials")
    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ImageDownloadError("Image hostname could not be resolved") from exc
    for address in {item[4][0] for item in addresses}:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ImageDownloadError("image_url must not resolve to a private network")


def _format_aspect_filter(category_id: str, aspects: Mapping[str, list[str]]) -> str:
    parts = [f"categoryId:{_escape_filter_value(category_id)}"]
    for name, values in aspects.items():
        if not name.strip() or not values:
            raise EbayError("Aspect filters require non-empty names and values")
        escaped_values = "|".join(_escape_filter_value(value) for value in values)
        parts.append(f"{_escape_filter_value(name)}:{{{escaped_values}}}")
    return ",".join(parts)


def _format_vehicle_filter(vehicle: Mapping[str, str]) -> str:
    labels = {
        "year": "Year",
        "make": "Make",
        "model": "Model",
        "trim": "Trim",
        "engine": "Engine",
        "submodel": "Submodel",
    }
    return ";".join(
        f"{labels[key]}:{_escape_filter_value(value)}"
        for key, value in vehicle.items()
        if value
    )


def _escape_filter_value(value: str) -> str:
    result = str(value).strip().replace("\\", "\\\\")
    for character in ("|", "{", "}", ",", ";"):
        result = result.replace(character, f"\\{character}")
    return result


def _format_number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _safe_api_error(response: httpx.Response) -> str:
    message = f"eBay API request failed with HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return message
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            detail = first.get("longMessage") or first.get("message")
            error_id = first.get("errorId")
            if detail:
                message += f": {str(detail)[:500]}"
            if error_id is not None:
                message += f" (error {error_id})"
    return message


def _money(value: Any) -> Money | None:
    if (
        not isinstance(value, dict)
        or value.get("value") is None
        or not value.get("currency")
    ):
        return None
    return Money(value=str(value["value"]), currency=str(value["currency"]))


def _seller(value: Any) -> SellerSummary | None:
    if not isinstance(value, dict):
        return None
    return SellerSummary(
        username=value.get("username"),
        feedback_score=value.get("feedbackScore"),
        feedback_percentage=value.get("feedbackPercentage"),
        account_type=value.get("sellerAccountType"),
    )


def _location(value: Any) -> Location | None:
    if not isinstance(value, dict):
        return None
    return Location(
        city=value.get("city"),
        county=value.get("county"),
        postal_code=value.get("postalCode"),
        country=value.get("country"),
    )


def _categories(values: Any) -> list[Category]:
    if not isinstance(values, list):
        return []
    return [
        Category(
            category_id=str(value["categoryId"]),
            category_name=value.get("categoryName"),
        )
        for value in values
        if isinstance(value, dict) and value.get("categoryId") is not None
    ]


def _compatibility(values: Any) -> list[CompatibilityProperty]:
    if not isinstance(values, list):
        return []
    return [
        CompatibilityProperty(
            name=str(value.get("localizedName") or value.get("name")),
            value=str(value["value"]),
        )
        for value in values
        if isinstance(value, dict)
        and (value.get("localizedName") or value.get("name"))
        and value.get("value") is not None
    ]


def _shipping(values: Any) -> list[ShippingSummary]:
    if not isinstance(values, list):
        return []
    return [
        ShippingSummary(
            cost=_money(value.get("shippingCost")),
            min_delivery_date=value.get("minEstimatedDeliveryDate"),
            max_delivery_date=value.get("maxEstimatedDeliveryDate"),
        )
        for value in values
        if isinstance(value, dict)
    ]


def _search_item(item: Mapping[str, Any]) -> SearchItem:
    image = item.get("image")
    return SearchItem(
        item_id=str(item.get("itemId", "")),
        legacy_item_id=item.get("legacyItemId"),
        title=str(item.get("title", "Untitled listing")),
        url=item.get("itemWebUrl"),
        image_url=image.get("imageUrl") if isinstance(image, dict) else None,
        price=_money(item.get("price")),
        current_bid_price=_money(item.get("currentBidPrice")),
        shipping=_shipping(item.get("shippingOptions")),
        condition=item.get("condition"),
        condition_id=item.get("conditionId"),
        buying_options=item.get("buyingOptions") or [],
        bid_count=item.get("bidCount"),
        seller=_seller(item.get("seller")),
        location=_location(item.get("itemLocation")),
        categories=_categories(item.get("categories")),
        item_creation_date=item.get("itemCreationDate"),
        item_end_date=item.get("itemEndDate"),
        short_description=item.get("shortDescription"),
        compatibility_match=item.get("compatibilityMatch"),
        compatibility_properties=_compatibility(item.get("compatibilityProperties")),
    )


def _refinement_value(
    value: Mapping[str, Any], name_keys: tuple[str, ...]
) -> RefinementValue:
    name = next((value.get(key) for key in name_keys if value.get(key) is not None), "")
    return RefinementValue(value=str(name), match_count=value.get("matchCount"))


def _refinements(value: Any) -> Refinements | None:
    if not isinstance(value, dict):
        return None
    aspects = []
    for aspect in value.get("aspectDistributions") or []:
        if not isinstance(aspect, dict) or not aspect.get("localizedAspectName"):
            continue
        aspects.append(
            AspectRefinement(
                name=str(aspect["localizedAspectName"]),
                values=[
                    _refinement_value(item, ("localizedAspectValue",))
                    for item in aspect.get("aspectValueDistributions") or []
                    if isinstance(item, dict)
                ],
            )
        )
    return Refinements(
        dominant_category_id=value.get("dominantCategoryId"),
        categories=[
            _refinement_value(item, ("categoryName", "categoryId"))
            for item in value.get("categoryDistributions") or []
            if isinstance(item, dict)
        ],
        conditions=[
            _refinement_value(item, ("condition", "conditionId"))
            for item in value.get("conditionDistributions") or []
            if isinstance(item, dict)
        ],
        buying_options=[
            _refinement_value(item, ("buyingOption",))
            for item in value.get("buyingOptionDistributions") or []
            if isinstance(item, dict)
        ],
        aspects=aspects,
    )


def _warnings(values: Any) -> list[ApiWarning]:
    if not isinstance(values, list):
        return []
    return [
        ApiWarning(
            code=value.get("errorId"),
            message=str(
                value.get("longMessage") or value.get("message") or "eBay warning"
            ),
        )
        for value in values
        if isinstance(value, dict)
    ]


def normalize_search_response(
    data: Mapping[str, Any], limit: int, offset: int
) -> SearchResponse:
    items = [
        _search_item(item)
        for item in data.get("itemSummaries") or []
        if isinstance(item, dict) and item.get("itemId")
    ]
    total = int(data.get("total") or len(items))
    next_offset = (
        offset + limit if items and offset + limit < min(total, 10_000) else None
    )
    return SearchResponse(
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
        items=items,
        refinements=_refinements(data.get("refinement")),
        warnings=_warnings(data.get("warnings")),
    )


def normalize_item_detail(data: Mapping[str, Any]) -> ItemDetail:
    images = []
    primary = data.get("image")
    if isinstance(primary, dict) and primary.get("imageUrl"):
        images.append(str(primary["imageUrl"]))
    images.extend(
        str(image["imageUrl"])
        for image in data.get("additionalImages") or []
        if isinstance(image, dict) and image.get("imageUrl")
    )
    aspects: dict[str, list[str]] = {}
    for aspect in data.get("localizedAspects") or []:
        if not isinstance(aspect, dict) or not aspect.get("name"):
            continue
        values = aspect.get("value")
        aspects.setdefault(str(aspect["name"]), []).append(str(values))
    estimated_availability = data.get("estimatedAvailabilities") or []
    availability = estimated_availability[0] if estimated_availability else {}
    categories = _categories(data.get("categories"))
    if not categories and data.get("categoryId") is not None:
        categories = [
            Category(
                category_id=str(data["categoryId"]),
                category_name=data.get("categoryPath"),
            )
        ]
    return ItemDetail(
        item_id=str(data.get("itemId", "")),
        legacy_item_id=data.get("legacyItemId"),
        title=str(data.get("title", "Untitled listing")),
        url=data.get("itemWebUrl"),
        description=data.get("description"),
        short_description=data.get("shortDescription"),
        images=images,
        price=_money(data.get("price")),
        current_bid_price=_money(data.get("currentBidPrice")),
        condition=data.get("condition"),
        condition_id=data.get("conditionId"),
        buying_options=data.get("buyingOptions") or [],
        bid_count=data.get("bidCount"),
        seller=_seller(data.get("seller")),
        location=_location(data.get("itemLocation")),
        categories=categories,
        aspects=aspects,
        availability_status=availability.get("estimatedAvailabilityStatus")
        if isinstance(availability, dict)
        else None,
        estimated_available_quantity=availability.get("estimatedAvailableQuantity")
        if isinstance(availability, dict)
        else None,
        quantity_sold=data.get("quantitySold"),
        shipping=_shipping(data.get("shippingOptions")),
        return_terms=data.get("returnTerms"),
        item_creation_date=data.get("itemCreationDate"),
        item_end_date=data.get("itemEndDate"),
        compatibility_match=data.get("compatibilityMatch"),
        compatibility_properties=_compatibility(data.get("compatibilityProperties")),
    )
