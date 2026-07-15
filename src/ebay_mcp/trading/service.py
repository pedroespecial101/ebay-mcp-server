"""Business logic for the narrow quantity-one Trading API workflow."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree as ET

from ebay_mcp.media.ebay import upload_staged_pictures
from ebay_mcp.media.storage import EBAY_IMAGE_HOSTS, download_public_image, prepare_model_image
from ebay_mcp.trading.client import (
    TradingAPIError, TradingClient, element, find, findall, value,
)
from models.ebay.trading import (
    AddFixedPriceItemInput, AddFixedPriceItemResult, EditableSellerListing,
    FixedPriceListingProposal, FixedPriceRevisionPatch, RecentSellerListingsInput,
    RecentSellerListingsResult, ReviseFixedPriceItemInput, ReviseFixedPriceItemResult,
    SellerListingSummary, SellerPolicyReferences, TradingFee, TradingIssue,
    UploadedListingPicture, VerifyAddFixedPriceItemResult,
    ViewItemImagesInput,
)
from utils.api_utils import get_standard_ebay_headers

INVENTORY_OFFERS_URL = "https://api.ebay.com/sell/inventory/v1/offer"
VERIFICATION_TTL = timedelta(minutes=15)
SUPPORTED_LISTING_TYPES = {"FixedPriceItem", "StoresFixedPrice"}
_VERIFICATIONS: dict[str, dict[str, Any]] = {}
logger = logging.getLogger(__name__)

TRADING_PACKAGE_TYPES = {
    "PARCEL_OR_PADDED_ENVELOPE": "ParcelOrPaddedEnvelope",
    "PACKAGE_THICK_ENVELOPE": "PackageThickEnvelope",
    "LETTER": "Letter",
    "LARGE_ENVELOPE": "LargeEnvelope",
    "MAILING_BOX": "MailingBoxes",
    "PADDED_BAGS": "PaddedBags",
    "TOUGH_BAGS": "ToughBags",
    "BULKY_GOODS": "BulkyGoods",
}


@dataclass(frozen=True)
class ModelListingImage:
    index: int
    data: bytes | None = None
    width: int | None = None
    height: int | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class ModelListingImages:
    item_id: str
    total_images: int
    start_index: int
    images: list[ModelListingImage]


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _parse_decimal(raw: str | None, default: str = "0") -> Decimal:
    try:
        return Decimal(raw or default)
    except Exception:
        return Decimal(default)


def _parse_int(raw: str | None, default: int = 0) -> int:
    try:
        return int(raw or default)
    except (TypeError, ValueError):
        return default


def _proposal_digest(proposal: FixedPriceListingProposal) -> str:
    payload = proposal.model_dump(mode="json")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _revision_state(listing: dict[str, Any]) -> str:
    editable = {
        key: listing[key]
        for key in (
            "item_id", "title", "description", "price_gbp", "condition_id",
            "condition_description", "primary_category_id", "item_specifics",
            "best_offer_enabled", "picture_urls", "status", "listing_type", "site",
            "quantity", "quantity_sold", "has_variations", "is_charity", "inventory_model",
        )
    }
    return hashlib.sha256(json.dumps(editable, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _parse_specifics(item: ET.Element) -> dict[str, list[str]]:
    specifics: dict[str, list[str]] = {}
    for entry in findall(item, "ItemSpecifics/NameValueList"):
        name = value(entry, "Name")
        values = [node.text or "" for node in findall(entry, "Value") if node.text]
        if name and values:
            specifics[name] = values
    return specifics


def _parse_fees(root: ET.Element) -> list[TradingFee]:
    fees = []
    for entry in findall(root, "Fees/Fee"):
        amount_node = find(entry, "Fee")
        fees.append(TradingFee(
            name=value(entry, "Name", "Unknown") or "Unknown",
            amount=_parse_decimal(amount_node.text if amount_node is not None else None),
            currency=(amount_node.attrib.get("currencyID", "GBP") if amount_node is not None else "GBP"),
        ))
    return fees


def _total_fees(fees: list[TradingFee]) -> Decimal:
    return sum((fee.amount for fee in fees if fee.currency == "GBP"), Decimal("0.00"))


def _parse_policies(item: ET.Element) -> SellerPolicyReferences:
    return SellerPolicyReferences(
        payment_profile_id=value(item, "SellerProfiles/SellerPaymentProfile/PaymentProfileID"),
        return_profile_id=value(item, "SellerProfiles/SellerReturnProfile/ReturnProfileID"),
        shipping_profile_id=value(item, "SellerProfiles/SellerShippingProfile/ShippingProfileID"),
    )


async def _inventory_model_status(client: TradingClient, item: ET.Element) -> bool | None:
    sku = value(item, "SKU")
    item_id = value(item, "ItemID")
    if not sku or not item_id or not client.access_token:
        return False
    try:
        response = await client.client.get(
            INVENTORY_OFFERS_URL,
            headers=get_standard_ebay_headers(client.access_token),
            params={"sku": sku, "limit": 25},
        )
    except Exception:
        return None
    if response.status_code == 404:
        return False
    if response.status_code != 200:
        return None
    try:
        offers = response.json().get("offers", [])
    except ValueError:
        return None
    return any(str((offer.get("listing") or {}).get("listingId") or offer.get("listingId") or "") == item_id for offer in offers)


def _listing_restrictions(data: dict[str, Any], start_time: datetime | None) -> list[str]:
    restrictions = []
    if (data.get("status") or "").lower() != "active":
        restrictions.append("listing_not_active")
    if start_time and start_time > datetime.now(timezone.utc):
        restrictions.append("scheduled_listing")
    if data.get("listing_type") not in SUPPORTED_LISTING_TYPES:
        restrictions.append("not_fixed_price")
    if data.get("site") != "UK":
        restrictions.append("not_ebay_uk")
    if data.get("quantity") != 1:
        restrictions.append("not_quantity_one")
    if data.get("quantity_sold", 0) > 0:
        restrictions.append("listing_has_sales")
    if data.get("has_variations"):
        restrictions.append("variation_listing")
    if data.get("is_charity"):
        restrictions.append("charity_listing")
    if data.get("inventory_model") is True:
        restrictions.append("inventory_api_listing")
    if data.get("inventory_model") is None:
        restrictions.append("inventory_model_unknown")
    if data.get("seller_matches") is False:
        restrictions.append("not_authenticated_seller_listing")
    return restrictions


async def _parse_editable_item(client: TradingClient, item: ET.Element) -> EditableSellerListing:
    item_id = value(item, "ItemID", "") or ""
    start_time = _parse_datetime(value(item, "ListingDetails/StartTime"))
    inventory_model = await _inventory_model_status(client, item)
    seller_name = value(item, "Seller/UserID")
    expected_seller = os.getenv("EBAY_USER_NAME")
    raw: dict[str, Any] = {
        "item_id": item_id,
        "title": value(item, "Title", "") or "",
        "description": value(item, "Description", "") or "",
        "price_gbp": _parse_decimal(value(item, "StartPrice") or value(item, "SellingStatus/CurrentPrice")),
        "condition_id": value(item, "ConditionID"),
        "condition_description": value(item, "ConditionDescription"),
        "primary_category_id": value(item, "PrimaryCategory/CategoryID", "") or "",
        "primary_category_name": value(item, "PrimaryCategory/CategoryName"),
        "item_specifics": _parse_specifics(item),
        "best_offer_enabled": (value(item, "BestOfferDetails/BestOfferEnabled", "false") or "false").lower() == "true",
        "picture_urls": [node.text for node in findall(item, "PictureDetails/PictureURL") if node.text],
        "policies": _parse_policies(item),
        "status": value(item, "SellingStatus/ListingStatus"),
        "listing_type": value(item, "ListingType"),
        "site": value(item, "Site"),
        "quantity": _parse_int(value(item, "Quantity"), 1),
        "quantity_sold": _parse_int(value(item, "SellingStatus/QuantitySold")),
        "has_variations": find(item, "Variations") is not None,
        "is_charity": find(item, "Charity") is not None,
        "inventory_model": inventory_model,
        "seller_matches": not (
            expected_seller and seller_name and seller_name.casefold() != expected_seller.casefold()
        ),
        "listing_url": value(item, "ListingDetails/ViewItemURL") or f"https://www.ebay.co.uk/itm/{item_id}",
    }
    restrictions = _listing_restrictions(raw, start_time)
    raw["restrictions"] = restrictions
    raw["supported_for_revision"] = not restrictions
    raw["revision_token"] = _revision_state(raw)
    return EditableSellerListing(**raw)


def _get_item_request(item_id: str) -> ET.Element:
    root = element("GetItemRequest")
    element("ItemID", item_id, root)
    element("DetailLevel", "ReturnAll", root)
    element("IncludeItemSpecifics", True, root)
    return root


async def get_item(item_id: str, client: TradingClient | None = None) -> EditableSellerListing:
    if client is None:
        async with TradingClient() as owned:
            return await get_item(item_id, owned)
    response = await client.call("GetItem", _get_item_request(item_id))
    item = find(response.root, "Item")
    if item is None:
        raise TradingAPIError("eBay returned no item for that item ID.")
    return await _parse_editable_item(client, item)


async def view_item_images(
    params: ViewItemImagesInput, client: TradingClient | None = None
) -> ModelListingImages:
    listing = await get_item(params.item_id, client)
    total = len(listing.picture_urls)
    if not total:
        raise ValueError("This listing has no photographs to inspect.")
    if params.start_index >= total:
        raise ValueError(f"start_index must be less than the listing's {total} photographs.")
    selected = list(enumerate(
        listing.picture_urls[params.start_index:params.start_index + params.limit],
        start=params.start_index,
    ))

    logger.info(
        "Preparing seller listing images item_id=%s start_index=%d limit=%d max_px=%d.",
        params.item_id,
        params.start_index,
        params.limit,
        params.max_px,
    )

    async def fetch(index: int, url: str) -> ModelListingImage:
        try:
            data, filename = await download_public_image(url, allowed_hosts=EBAY_IMAGE_HOSTS)
            prepared, width, height = await asyncio.to_thread(
                prepare_model_image,
                data,
                filename,
                params.max_px,
            )
            logger.info(
                "Prepared seller listing image item_id=%s index=%d width=%d height=%d bytes=%d.",
                params.item_id,
                index,
                width,
                height,
                len(prepared),
            )
            return ModelListingImage(index=index, data=prepared, width=width, height=height)
        except Exception as exc:
            logger.warning(
                "Could not prepare seller listing image item_id=%s index=%d error_type=%s.",
                params.item_id,
                index,
                exc.__class__.__name__,
            )
            return ModelListingImage(index=index, error_code="image_unavailable")

    images = await asyncio.gather(*(fetch(index, url) for index, url in selected))
    successes = sum(1 for image in images if image.data is not None)
    logger.info(
        "Prepared seller listing image batch item_id=%s attempted=%d returned=%d total=%d.",
        params.item_id,
        len(images),
        successes,
        total,
    )
    return ModelListingImages(
        item_id=listing.item_id,
        total_images=total,
        start_index=params.start_index,
        images=list(images),
    )


async def get_recent_seller_listings(
    params: RecentSellerListingsInput, client: TradingClient | None = None
) -> RecentSellerListingsResult:
    if client is None:
        async with TradingClient() as owned:
            return await get_recent_seller_listings(params, owned)
    now = datetime.now(timezone.utc)
    root = element("GetSellerListRequest")
    element("StartTimeFrom", (now - timedelta(days=params.lookback_days)).isoformat().replace("+00:00", "Z"), root)
    element("StartTimeTo", now.isoformat().replace("+00:00", "Z"), root)
    element("DetailLevel", "ReturnAll", root)
    element("IncludeVariations", True, root)
    pagination = element("Pagination", parent=root)
    element("EntriesPerPage", params.page_size, pagination)
    element("PageNumber", params.page_number, pagination)
    response = await client.call("GetSellerList", root)
    accepted: list[SellerListingSummary] = []
    excluded = 0
    for item in findall(response.root, "ItemArray/Item"):
        status = value(item, "SellingStatus/ListingStatus")
        listing_type = value(item, "ListingType")
        start = _parse_datetime(value(item, "ListingDetails/StartTime"))
        quantity = _parse_int(value(item, "Quantity"), 1)
        if (status != "Active" or listing_type not in SUPPORTED_LISTING_TYPES
                or find(item, "Variations") is not None or quantity != 1 or find(item, "Charity") is not None):
            excluded += 1
            continue
        inventory_model = await _inventory_model_status(client, item)
        if start and start > now or inventory_model is True:
            excluded += 1
            continue
        price_node = find(item, "SellingStatus/CurrentPrice")
        if price_node is None:
            price_node = find(item, "StartPrice")
        accepted.append(SellerListingSummary(
            item_id=value(item, "ItemID", "") or "",
            title=value(item, "Title", "") or "",
            price_gbp=_parse_decimal(price_node.text) if price_node is not None else None,
            start_time=start,
            end_time=_parse_datetime(value(item, "ListingDetails/EndTime")),
            status=status,
            quantity=quantity,
            quantity_sold=_parse_int(value(item, "SellingStatus/QuantitySold")),
            picture_url=value(item, "PictureDetails/GalleryURL") or value(item, "PictureDetails/PictureURL"),
            listing_url=value(item, "ListingDetails/ViewItemURL") or f"https://www.ebay.co.uk/itm/{value(item, 'ItemID', '')}",
            listing_type=listing_type,
        ))
    accepted.sort(key=lambda entry: entry.start_time or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return RecentSellerListingsResult(
        listings=accepted,
        page_number=params.page_number,
        page_size=params.page_size,
        total_pages=_parse_int(value(response.root, "PaginationResult/TotalNumberOfPages")) or None,
        total_entries=_parse_int(value(response.root, "PaginationResult/TotalNumberOfEntries")) or None,
        has_more=(value(response.root, "HasMoreItems", "false") or "false").lower() == "true",
        excluded_count=excluded,
        warnings=response.warnings,
    )


def _merged_specifics(current: dict[str, list[str]], patch: FixedPriceRevisionPatch) -> dict[str, list[str]]:
    merged = {name: list(values) for name, values in current.items()}
    for name in patch.item_specifics_remove:
        merged.pop(name, None)
    for name, values in patch.item_specifics_upsert.items():
        merged[name] = list(values)
    return merged


def _append_specifics(parent: ET.Element, specifics: dict[str, list[str]]) -> None:
    container = element("ItemSpecifics", parent=parent)
    for name in sorted(specifics):
        entry = element("NameValueList", parent=container)
        element("Name", name, entry)
        for specific_value in specifics[name]:
            element("Value", specific_value, entry)


def _revision_diff(current: EditableSellerListing, patch: FixedPriceRevisionPatch) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    mappings = {
        "title": patch.title, "description": patch.description, "price_gbp": patch.price_gbp,
        "condition_id": patch.condition_id, "condition_description": patch.condition_description,
        "primary_category_id": patch.primary_category_id, "best_offer_enabled": patch.best_offer_enabled,
        "picture_urls": patch.picture_urls,
    }
    for field, new_value in mappings.items():
        if new_value is not None and getattr(current, field) != new_value:
            diff[field] = {"before": getattr(current, field), "after": new_value}
    if patch.item_specifics_upsert or patch.item_specifics_remove:
        merged = _merged_specifics(current.item_specifics, patch)
        if merged != current.item_specifics:
            diff["item_specifics"] = {"before": current.item_specifics, "after": merged}
    return diff


def _build_revise_request(current: EditableSellerListing, patch: FixedPriceRevisionPatch) -> ET.Element:
    root = element("ReviseFixedPriceItemRequest")
    item = element("Item", parent=root)
    element("ItemID", current.item_id, item)
    if patch.title is not None:
        element("Title", patch.title, item)
    if patch.description is not None:
        element("Description", patch.description, item)
    if patch.price_gbp is not None:
        price = element("StartPrice", patch.price_gbp, item)
        price.set("currencyID", "GBP")
    if patch.condition_id is not None:
        element("ConditionID", patch.condition_id, item)
    if patch.condition_description is not None:
        element("ConditionDescription", patch.condition_description, item)
    if patch.primary_category_id is not None:
        category = element("PrimaryCategory", parent=item)
        element("CategoryID", patch.primary_category_id, category)
    if patch.best_offer_enabled is not None:
        best_offer = element("BestOfferDetails", parent=item)
        element("BestOfferEnabled", patch.best_offer_enabled, best_offer)
    if patch.item_specifics_upsert or patch.item_specifics_remove or patch.primary_category_id is not None:
        merged = _merged_specifics(current.item_specifics, patch)
        if merged:
            _append_specifics(item, merged)
        elif current.item_specifics:
            element("DeletedField", "Item.ItemSpecifics", root)
    if patch.picture_urls is not None:
        pictures = element("PictureDetails", parent=item)
        for url in patch.picture_urls:
            element("PictureURL", url, pictures)
    return root


async def revise_fixed_price_item(
    params: ReviseFixedPriceItemInput, client: TradingClient | None = None
) -> ReviseFixedPriceItemResult:
    if client is None:
        async with TradingClient() as owned:
            return await revise_fixed_price_item(params, owned)
    current = await get_item(params.item_id, client)
    if current.revision_token != params.revision_token:
        raise ValueError("The listing changed after it was inspected. Fetch it again before revising.")
    if not current.supported_for_revision:
        raise ValueError(f"This listing cannot be revised by the narrow Trading tool: {', '.join(current.restrictions)}")
    diff = _revision_diff(current, params.patch)
    if not diff:
        raise ValueError("The requested patch does not change the listing.")
    response = await client.call("ReviseFixedPriceItem", _build_revise_request(current, params.patch))
    final = await get_item(params.item_id, client)
    warnings = list(response.warnings)
    if params.patch.price_gbp is not None and current.best_offer_enabled:
        warnings.append(TradingIssue(
            code="best_offer_thresholds_may_reset",
            severity="Warning",
            message="Changing price can clear existing Best Offer auto-accept and auto-decline thresholds.",
        ))
    return ReviseFixedPriceItemResult(
        status="revised",
        item_id=params.item_id,
        applied_diff=diff,
        warnings=warnings,
        fees=_parse_fees(response.root),
        final_listing=final,
    )


async def upload_listing_pictures(image_refs: list[str]) -> list[UploadedListingPicture]:
    return await upload_staged_pictures(image_refs)


async def _required_add_defaults(client: TradingClient) -> dict[str, str]:
    values = {
        "payment": os.getenv("EBAY_PAYMENT_POLICY_ID", ""),
        "return": os.getenv("EBAY_RETURN_POLICY_ID", ""),
        "shipping": os.getenv("EBAY_FULFILLMENT_POLICY_ID", ""),
        "location": os.getenv("EBAY_ITEM_LOCATION", ""),
        "postal_code": os.getenv("EBAY_ITEM_POSTAL_CODE", "") or os.getenv("EBAY_DELIVERY_POSTAL_CODE", ""),
    }
    location_key = os.getenv("EBAY_MERCHANT_LOCATION_KEY", "")
    if (not values["location"] or not values["postal_code"]) and location_key and client.access_token:
        try:
            response = await client.client.get(
                f"https://api.ebay.com/sell/inventory/v1/location/{quote(location_key, safe='')}",
                headers=get_standard_ebay_headers(client.access_token),
            )
            if response.status_code == 200:
                address = (response.json().get("location") or {}).get("address") or {}
                values["location"] = values["location"] or address.get("city", "")
                values["postal_code"] = values["postal_code"] or address.get("postalCode", "")
        except Exception:
            pass
    missing = [name for name, setting in values.items() if not setting]
    if missing:
        raise ValueError(f"Trading listing defaults are not configured: {', '.join(missing)}")
    return values


def _build_add_request(call_name: str, proposal: FixedPriceListingProposal, uuid: str,
                       defaults: dict[str, str]) -> ET.Element:
    root = element(f"{call_name}Request")
    item = element("Item", parent=root)
    element("Title", proposal.title, item)
    element("Description", proposal.description, item)
    category = element("PrimaryCategory", parent=item)
    element("CategoryID", proposal.category_id, category)
    element("ConditionID", proposal.condition_id, item)
    if proposal.condition_description:
        element("ConditionDescription", proposal.condition_description, item)
    price = element("StartPrice", proposal.price_gbp, item)
    price.set("currencyID", "GBP")
    element("Currency", "GBP", item)
    element("Country", "GB", item)
    element("Site", "UK", item)
    element("Location", defaults["location"], item)
    element("PostalCode", defaults["postal_code"], item)
    element("ListingType", "FixedPriceItem", item)
    element("ListingDuration", "GTC", item)
    element("Quantity", 1, item)
    if proposal.sku:
        element("SKU", proposal.sku, item)
        element("InventoryTrackingMethod", "SKU", item)
    element("UUID", uuid, item)
    element("CategoryMappingAllowed", False, item)
    best_offer = element("BestOfferDetails", parent=item)
    element("BestOfferEnabled", proposal.best_offer_enabled, best_offer)
    if proposal.item_specifics:
        _append_specifics(item, proposal.item_specifics)
    pictures = element("PictureDetails", parent=item)
    element("PictureSource", "EPS", pictures)
    for url in proposal.picture_urls:
        element("PictureURL", url, pictures)
    if proposal.package:
        package = element("ShippingPackageDetails", parent=item)
        element("MeasurementUnit", "Metric", package)
        element("PackageDepth", proposal.package.height_cm, package)
        element("PackageLength", proposal.package.length_cm, package)
        element("PackageWidth", proposal.package.width_cm, package)
        element("ShippingPackage", TRADING_PACKAGE_TYPES[proposal.package.package_type], package)
        major = element("WeightMajor", proposal.package.weight_grams // 1000, package)
        major.set("unit", "kg")
        minor = element("WeightMinor", proposal.package.weight_grams % 1000, package)
        minor.set("unit", "gr")
    profiles = element("SellerProfiles", parent=item)
    payment = element("SellerPaymentProfile", parent=profiles)
    element("PaymentProfileID", defaults["payment"], payment)
    returns = element("SellerReturnProfile", parent=profiles)
    element("ReturnProfileID", defaults["return"], returns)
    shipping = element("SellerShippingProfile", parent=profiles)
    element("ShippingProfileID", defaults["shipping"], shipping)
    return root


async def _verify_proposal(
    proposal: FixedPriceListingProposal, uuid: str, client: TradingClient
) -> tuple[list[TradingFee], list[TradingIssue], list[TradingIssue]]:
    defaults = await _required_add_defaults(client)
    try:
        response = await client.call(
            "VerifyAddFixedPriceItem",
            _build_add_request("VerifyAddFixedPriceItem", proposal, uuid, defaults),
        )
        return _parse_fees(response.root), response.warnings, []
    except TradingAPIError as exc:
        errors = [issue for issue in exc.issues if issue.severity.lower() == "error"]
        warnings = [issue for issue in exc.issues if issue.severity.lower() != "error"]
        if not errors:
            errors = [TradingIssue(code="verify_failed", severity="Error", message=str(exc))]
        return [], warnings, errors


async def verify_add_fixed_price_item(
    proposal: FixedPriceListingProposal, client: TradingClient | None = None
) -> VerifyAddFixedPriceItemResult:
    if client is None:
        async with TradingClient() as owned:
            return await verify_add_fixed_price_item(proposal, owned)
    uuid = secrets.token_hex(16).upper()
    fees, warnings, errors = await _verify_proposal(proposal, uuid, client)
    if errors:
        return VerifyAddFixedPriceItemResult(
            valid=False,
            fees=fees,
            estimated_fee_gbp=_total_fees(fees),
            warnings=warnings,
            errors=errors,
        )
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + VERIFICATION_TTL
    _VERIFICATIONS[token] = {"digest": _proposal_digest(proposal), "uuid": uuid, "expires_at": expires_at}
    return VerifyAddFixedPriceItemResult(
        valid=True,
        verification_token=token,
        expires_at=expires_at,
        fees=fees,
        estimated_fee_gbp=_total_fees(fees),
        warnings=warnings,
    )


def _duplicate_item_id(error: TradingAPIError) -> str | None:
    if error.root is None:
        return None
    duplicate = find(error.root, "DuplicateInvocationDetails") is not None or any("duplicate" in issue.message.lower() for issue in error.issues)
    if not duplicate:
        return None
    candidates = [node.text or "" for node in findall(error.root, "Errors/ErrorParameters/Value")]
    candidates.extend(issue.message for issue in error.issues)
    for candidate in candidates:
        match = re.search(r"\b(\d{8,20})\b", candidate)
        if match:
            return match.group(1)
    return None


async def add_fixed_price_item(
    params: AddFixedPriceItemInput, client: TradingClient | None = None
) -> AddFixedPriceItemResult:
    if client is None:
        async with TradingClient() as owned:
            return await add_fixed_price_item(params, owned)
    verification = _VERIFICATIONS.get(params.verification_token)
    if not verification:
        raise ValueError("The verification token is unknown or the server restarted; verify the listing again.")
    if verification["expires_at"] <= datetime.now(timezone.utc):
        _VERIFICATIONS.pop(params.verification_token, None)
        raise ValueError("The verification token expired; verify the listing again.")
    if verification["digest"] != _proposal_digest(params.proposal):
        raise ValueError("The listing proposal changed after verification; verify the new proposal.")
    fees, verify_warnings, errors = await _verify_proposal(params.proposal, verification["uuid"], client)
    if errors:
        raise ValueError(f"The listing no longer verifies: {errors[0].message}")
    estimate = _total_fees(fees)
    if estimate > params.max_listing_fee_gbp:
        raise ValueError(f"Estimated listing fees are GBP {estimate}; approved ceiling is GBP {params.max_listing_fee_gbp}.")
    try:
        defaults = await _required_add_defaults(client)
        response = await client.call(
            "AddFixedPriceItem",
            _build_add_request("AddFixedPriceItem", params.proposal, verification["uuid"], defaults),
        )
        item_id = value(response.root, "ItemID")
        actual_fees = _parse_fees(response.root)
        warnings = verify_warnings + response.warnings
        recovered = False
    except TradingAPIError as exc:
        item_id = _duplicate_item_id(exc)
        if not item_id:
            raise
        actual_fees = []
        warnings = verify_warnings + [issue for issue in exc.issues if issue.severity.lower() != "error"]
        recovered = True
    if not item_id:
        raise TradingAPIError("eBay accepted the add request but returned no item ID.")
    final = await get_item(item_id, client)
    return AddFixedPriceItemResult(
        status="published",
        item_id=item_id,
        listing_url=final.listing_url,
        fees=actual_fees,
        actual_fee_gbp=_total_fees(actual_fees),
        warnings=warnings,
        final_listing=final,
        idempotent_recovery=recovered,
    )
