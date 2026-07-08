"""Resumable, idempotent fixed-price listing orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import json
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx

from ebay_mcp.config import ebay_offer_defaults
from ebay_mcp.media.storage import get_manifest, get_staged_bytes, put_manifest
from ebay_service import get_ebay_access_token
from models.ebay.listing_workflow import (
    DiscardDraftInput, FeeEstimate, ListingValidationResult, ListingWorkflowResult,
    PublishListingInput, SimpleListingInput, WorkflowIssue,
)
from utils.api_utils import get_standard_ebay_headers, is_token_error

API = "https://api.ebay.com"
MEDIA_API = "https://apim.ebay.com"
CONDITION_IDS = {
    "NEW": "1000", "NEW_OTHER": "1500", "NEW_WITH_DEFECTS": "1750",
    "CERTIFIED_REFURBISHED": "2000", "EXCELLENT_REFURBISHED": "2010",
    "VERY_GOOD_REFURBISHED": "2020", "GOOD_REFURBISHED": "2030",
    "SELLER_REFURBISHED": "2500", "LIKE_NEW": "2750", "USED_EXCELLENT": "3000",
    "USED_VERY_GOOD": "4000", "USED_GOOD": "5000", "USED_ACCEPTABLE": "6000",
    "FOR_PARTS_OR_NOT_WORKING": "7000",
}


class EbayWorkflowError(RuntimeError):
    def __init__(self, code: str, message: str, status: int | None = None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _sanitized_error(response: httpx.Response) -> EbayWorkflowError:
    message = f"eBay rejected the request ({response.status_code})."
    code = f"ebay_http_{response.status_code}"
    try:
        body = response.json()
        error = (body.get("errors") or [None])[0]
        if error:
            code = str(error.get("errorId") or code)
            message = error.get("longMessage") or error.get("message") or message
    except Exception:
        pass
    return EbayWorkflowError(code, message, response.status_code)


class EbayAPI:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=30)
        self.owned = client is None
        self.headers: dict[str, str] | None = None

    async def __aenter__(self):
        token = await get_ebay_access_token()
        if is_token_error(token):
            raise EbayWorkflowError("authentication_required", "Seller authentication is unavailable; run the eBay login tool.")
        self.headers = get_standard_ebay_headers(token)
        return self

    async def __aexit__(self, *_):
        if self.owned:
            await self.client.aclose()

    async def request(self, method: str, path: str, *, json_body: Any = None, params: dict | None = None,
                      files: dict | None = None, expected: set[int] = {200}) -> httpx.Response:
        headers = dict(self.headers or {})
        if files:
            headers.pop("Content-Type", None)
        url = path if path.startswith("https://") else API + path
        response = await self.client.request(method, url, headers=headers, json=json_body, params=params, files=files)
        if response.status_code not in expected:
            raise _sanitized_error(response)
        return response


def _aspect_constraints(raw: dict) -> dict[str, dict]:
    result = {}
    for aspect in raw.get("aspects", []):
        name = aspect.get("localizedAspectName")
        if not name:
            continue
        constraint = aspect.get("aspectConstraint", {})
        result[name] = {
            "required": bool(constraint.get("aspectRequired")),
            "multi": constraint.get("itemToAspectCardinality") == "MULTI",
            "mode": constraint.get("aspectMode"),
            "values": {entry.get("localizedValue") for entry in aspect.get("aspectValues", []) if entry.get("localizedValue")},
        }
    return result


async def validate_listing(data: SimpleListingInput, api: EbayAPI | None = None) -> ListingValidationResult:
    errors: list[WorkflowIssue] = []
    warnings: list[WorkflowIssue] = []
    for index, reference in enumerate(data.image_refs):
        try:
            await asyncio.to_thread(get_staged_bytes, reference)
        except Exception:
            errors.append(WorkflowIssue(code="image_unavailable", field=f"image_refs.{index}", message="Staged image is missing or inaccessible."))
    own = api is None
    try:
        if own:
            api = await EbayAPI().__aenter__()
        taxonomy = (await api.request("GET", "/commerce/taxonomy/v1/category_tree/3/get_item_aspects_for_category",
            params={"category_id": data.category_id})).json()
        constraints = _aspect_constraints(taxonomy)
        if not constraints:
            errors.append(WorkflowIssue(code="invalid_category", field="category_id", message="Category has no listing aspects or is not a valid leaf category."))
        for name, rule in constraints.items():
            values = data.aspects.get(name, [])
            if rule["required"] and not values:
                errors.append(WorkflowIssue(code="missing_required_aspect", field=f"aspects.{name}", message=f"Required aspect '{name}' is missing."))
            if values and not rule["multi"] and len(values) > 1:
                errors.append(WorkflowIssue(code="aspect_cardinality", field=f"aspects.{name}", message=f"Aspect '{name}' accepts one value."))
            invalid = [value for value in values if rule["mode"] == "SELECTION_ONLY" and rule["values"] and value not in rule["values"]]
            if invalid:
                errors.append(WorkflowIssue(code="invalid_aspect_value", field=f"aspects.{name}", message=f"Unsupported value for '{name}'.", details={"values": invalid}))
        unknown = sorted(set(data.aspects) - set(constraints))
        for name in unknown:
            warnings.append(WorkflowIssue(code="unknown_aspect", field=f"aspects.{name}", message=f"eBay did not return '{name}' for this category."))
        policies = (await api.request("GET", "/sell/metadata/v1/marketplace/EBAY_GB/get_item_condition_policies",
            params={"filter": f"categoryIds:{{{data.category_id}}}"})).json()
        allowed_ids = {str(item.get("conditionId")) for policy in policies.get("itemConditionPolicies", []) for item in policy.get("itemConditions", [])}
        condition_id = CONDITION_IDS.get(data.condition.upper())
        if not condition_id:
            errors.append(WorkflowIssue(code="invalid_condition", field="condition", message="Condition is not a supported Inventory API condition value."))
        elif allowed_ids and condition_id not in allowed_ids:
            errors.append(WorkflowIssue(code="condition_not_allowed", field="condition", message="Condition is not permitted in this eBay UK category."))
    except EbayWorkflowError as exc:
        errors.append(WorkflowIssue(code=exc.code, message=exc.message))
    finally:
        if own and api:
            await api.__aexit__(None, None, None)
    return ListingValidationResult(valid=not errors, normalized=data, errors=errors, warnings=warnings)


def _digest(data: SimpleListingInput) -> str:
    payload = data.model_dump(mode="json", exclude={"mode"})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _inventory_matches(item: dict, data: SimpleListingInput) -> bool:
    product = item.get("product", {})
    quantity = item.get("availability", {}).get("shipToLocationAvailability", {}).get("quantity")
    return (product.get("title") == data.title and product.get("description") == data.description
        and product.get("aspects", {}) == data.aspects and item.get("condition") == data.condition.upper()
        and item.get("conditionDescription") == data.condition_description and quantity == 1)


def _offer_matches(offer: dict, data: SimpleListingInput) -> bool:
    price = offer.get("pricingSummary", {}).get("price", {})
    try:
        price_matches = Decimal(str(price.get("value"))) == data.price_gbp and price.get("currency") == "GBP"
    except Exception:
        price_matches = False
    return (offer.get("sku") == data.sku and offer.get("marketplaceId") == "EBAY_GB"
        and offer.get("format") == "FIXED_PRICE" and offer.get("listingDuration") == "GTC"
        and str(offer.get("categoryId")) == data.category_id and offer.get("availableQuantity") == 1
        and price_matches)


async def _get_inventory(api: EbayAPI, sku: str) -> dict | None:
    response = await api.client.get(API + f"/sell/inventory/v1/inventory_item/{quote(sku, safe='')}", headers=api.headers)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise _sanitized_error(response)
    return response.json()


async def _get_offers(api: EbayAPI, sku: str) -> list[dict]:
    response = await api.request("GET", "/sell/inventory/v1/offer", params={"sku": sku, "marketplace_id": "EBAY_GB"})
    return response.json().get("offers", [])


def _offer_listing_id(offer: dict) -> str | None:
    listing = offer.get("listing") or {}
    return listing.get("listingId") or offer.get("listingId")


def _is_published(offer: dict) -> bool:
    return offer.get("status") in {"PUBLISHED", "PUBLISHED_OUT_OF_STOCK"} or bool(_offer_listing_id(offer))


async def _upload_images(api: EbayAPI, data: SimpleListingInput, manifest: dict, digest: str) -> list[str]:
    images = manifest.setdefault("eps_images", [])
    for reference in data.image_refs[len(images):]:
        raw, name = await asyncio.to_thread(get_staged_bytes, reference)
        response = await api.request("POST", MEDIA_API + "/commerce/media/v1_beta/image/create_image_from_file",
            files={"image": (name, raw, "image/jpeg")}, expected={201})
        body = response.json()
        image_url = body.get("imageUrl")
        location = response.headers.get("location", "")
        if not image_url:
            raise EbayWorkflowError("media_response_invalid", "eBay accepted an image but returned no EPS URL.")
        images.append({"image_id": location.rstrip("/").split("/")[-1] or None, "url": image_url,
            "expiration": body.get("expirationDate")})
        await asyncio.to_thread(put_manifest, data.sku, digest, manifest)
    return [entry["url"] for entry in images]


async def _fees(api: EbayAPI, offer_id: str) -> FeeEstimate:
    body = (await api.request("POST", "/sell/inventory/v1/offer/get_listing_fees",
        json_body={"offers": [{"offerId": offer_id}]})).json()
    fees, total = [], Decimal("0")
    for summary in body.get("feeSummaries", []):
        for fee in summary.get("fees", []):
            amount = fee.get("amount", {})
            value = Decimal(str(amount.get("value", "0")))
            discount = Decimal(str(fee.get("promotionalDiscount", {}).get("value", "0")))
            total += max(Decimal("0"), value - discount)
            fees.append({"fee_type": fee.get("feeType"), "amount": str(value), "discount": str(discount)})
    return FeeEstimate(amount_gbp=total, fees=fees)


async def _poll_published(api: EbayAPI, offer_id: str) -> dict | None:
    for delay in (0, 1, 2, 4, 8):
        if delay:
            await asyncio.sleep(delay)
        offer = (await api.request("GET", f"/sell/inventory/v1/offer/{offer_id}")).json()
        if _is_published(offer):
            return offer
    return None


async def create_listing(data: SimpleListingInput) -> ListingWorkflowResult:
    completed: list[str] = []
    try:
        async with EbayAPI() as api:
            validation = await validate_listing(data, api)
            if not validation.valid:
                return ListingWorkflowResult(status="validation_failed", sku=data.sku, warnings=validation.warnings,
                    recoverable=True, next_action="Correct the validation errors and retry listing_create.",
                    error=WorkflowIssue(code="validation_failed", message="Listing validation failed.", details={"errors": [e.model_dump() for e in validation.errors]}))
            completed.append("validated")
            existing = await _get_inventory(api, data.sku)
            offers = await _get_offers(api, data.sku) if existing else []
            if existing and not _inventory_matches(existing, data):
                return ListingWorkflowResult(status="conflict", sku=data.sku, completed_steps=completed, recoverable=False,
                    error=WorkflowIssue(code="sku_content_conflict", message="This SKU already exists with different content; it was not changed."))
            if len(offers) > 1:
                return ListingWorkflowResult(status="conflict", sku=data.sku, completed_steps=completed, recoverable=False,
                    error=WorkflowIssue(code="ambiguous_offers", message="More than one offer exists for this SKU; no changes were made."))
            if offers and not _offer_matches(offers[0], data):
                return ListingWorkflowResult(status="conflict", sku=data.sku, completed_steps=completed, recoverable=False,
                    error=WorkflowIssue(code="offer_content_conflict", message="This SKU has an offer with different category, price, format, duration, marketplace, or quantity; it was not changed."))
            if offers and _is_published(offers[0]):
                listing_id = _offer_listing_id(offers[0])
                return ListingWorkflowResult(status="published", sku=data.sku, completed_steps=completed + ["already_published"],
                    offer_id=offers[0].get("offerId"), listing_id=listing_id,
                    listing_url=f"https://www.ebay.co.uk/itm/{listing_id}" if listing_id else None, recoverable=False)
            if not existing:
                digest = _digest(data)
                manifest = await asyncio.to_thread(get_manifest, data.sku, digest) or {"version": 1, "sku": data.sku}
                urls = await _upload_images(api, data, manifest, digest)
                completed.append("eps_images_uploaded")
                payload = {"availability": {"shipToLocationAvailability": {"quantity": 1}},
                    "condition": data.condition.upper(), "conditionDescription": data.condition_description,
                    "product": {"title": data.title, "description": data.description, "aspects": data.aspects, "imageUrls": urls}}
                await api.request("PUT", f"/sell/inventory/v1/inventory_item/{quote(data.sku, safe='')}", json_body=payload, expected={204})
                verified = await _get_inventory(api, data.sku)
                if not verified or not _inventory_matches(verified, data):
                    raise EbayWorkflowError("inventory_verification_failed", "Inventory item was written but did not verify; retry safely with the same SKU.")
                completed.append("inventory_item_verified")
            else:
                completed.append("inventory_item_resumed")
            if offers:
                offer = offers[0]
                offer_id = offer["offerId"]
                completed.append("offer_resumed")
            else:
                cfg = ebay_offer_defaults
                payload = {"sku": data.sku, "marketplaceId": "EBAY_GB", "format": "FIXED_PRICE", "listingDuration": "GTC",
                    "availableQuantity": 1, "categoryId": data.category_id,
                    "merchantLocationKey": cfg.EBAY_MERCHANT_LOCATION_KEY,
                    "listingPolicies": {"paymentPolicyId": cfg.EBAY_PAYMENT_POLICY_ID,
                        "returnPolicyId": cfg.EBAY_RETURN_POLICY_ID, "fulfillmentPolicyId": cfg.EBAY_FULFILLMENT_POLICY_ID},
                    "pricingSummary": {"price": {"value": f"{data.price_gbp:.2f}", "currency": "GBP"}},
                    "includeCatalogProductDetails": cfg.EBAY_LISTING_INCLUDE_CATALOG_PRODUCT_DETAILS}
                created = (await api.request("POST", "/sell/inventory/v1/offer", json_body=payload, expected={201})).json()
                offer_id = created.get("offerId")
                if not offer_id:
                    raise EbayWorkflowError("offer_response_invalid", "eBay created an offer but returned no offer ID.")
                offer = (await api.request("GET", f"/sell/inventory/v1/offer/{offer_id}")).json()
                completed.append("offer_verified")
            fee = await _fees(api, offer_id)
            completed.append("fees_checked")
            if data.mode.value == "draft" or fee.amount_gbp > 0:
                warning = []
                if fee.amount_gbp > 0:
                    warning.append(WorkflowIssue(code="nonzero_fee", message=f"Estimated listing fee is GBP {fee.amount_gbp}; explicit approval is required."))
                return ListingWorkflowResult(status="draft_ready", sku=data.sku, completed_steps=completed, offer_id=offer_id,
                    fee_estimate=fee, warnings=validation.warnings + warning, next_action="Call listing_publish with an approved fee ceiling.")
            await api.request("POST", f"/sell/inventory/v1/offer/{offer_id}/publish", expected={200})
            published = await _poll_published(api, offer_id)
            if not published:
                return ListingWorkflowResult(status="publish_pending", sku=data.sku, completed_steps=completed + ["publish_requested"],
                    offer_id=offer_id, fee_estimate=fee, next_action="Retry listing_publish; it will inspect eBay state before acting.")
            listing_id = _offer_listing_id(published)
            return ListingWorkflowResult(status="published", sku=data.sku, completed_steps=completed + ["published_verified"],
                offer_id=offer_id, listing_id=listing_id, listing_url=f"https://www.ebay.co.uk/itm/{listing_id}" if listing_id else None,
                fee_estimate=fee, recoverable=False)
    except EbayWorkflowError as exc:
        return ListingWorkflowResult(status="failed", sku=data.sku, completed_steps=completed, recoverable=True,
            next_action="Retry listing_create with the same SKU and content.", error=WorkflowIssue(code=exc.code, message=exc.message))
    except Exception:
        return ListingWorkflowResult(status="failed", sku=data.sku, completed_steps=completed, recoverable=True,
            next_action="Retry listing_create with the same SKU and content.", error=WorkflowIssue(code="internal_workflow_error", message="The listing workflow failed; no automatic rollback was attempted."))


async def publish_listing(data: PublishListingInput) -> ListingWorkflowResult:
    try:
        async with EbayAPI() as api:
            offers = await _get_offers(api, data.sku)
            if len(offers) != 1:
                return ListingWorkflowResult(status="conflict", sku=data.sku, recoverable=False,
                    error=WorkflowIssue(code="offer_not_unique", message="Exactly one offer must exist for this SKU."))
            offer = offers[0]; offer_id = offer["offerId"]
            if _is_published(offer):
                listing_id = _offer_listing_id(offer)
                return ListingWorkflowResult(status="published", sku=data.sku, completed_steps=["already_published"], offer_id=offer_id,
                    listing_id=listing_id, listing_url=f"https://www.ebay.co.uk/itm/{listing_id}" if listing_id else None, recoverable=False)
            fee = await _fees(api, offer_id)
            if fee.amount_gbp > data.max_fee_gbp:
                return ListingWorkflowResult(status="fee_approval_required", sku=data.sku, completed_steps=["fees_checked"],
                    offer_id=offer_id, fee_estimate=fee, next_action="Call listing_publish again with an explicitly approved sufficient max_fee_gbp.")
            await api.request("POST", f"/sell/inventory/v1/offer/{offer_id}/publish", expected={200})
            published = await _poll_published(api, offer_id)
            if not published:
                return ListingWorkflowResult(status="publish_pending", sku=data.sku, completed_steps=["fees_checked", "publish_requested"],
                    offer_id=offer_id, fee_estimate=fee, next_action="Retry listing_publish to verify the ambiguous result.")
            listing_id = _offer_listing_id(published)
            return ListingWorkflowResult(status="published", sku=data.sku, completed_steps=["fees_checked", "published_verified"],
                offer_id=offer_id, listing_id=listing_id, listing_url=f"https://www.ebay.co.uk/itm/{listing_id}" if listing_id else None,
                fee_estimate=fee, recoverable=False)
    except EbayWorkflowError as exc:
        return ListingWorkflowResult(status="failed", sku=data.sku, error=WorkflowIssue(code=exc.code, message=exc.message),
            next_action="Retry listing_publish; current eBay state will be inspected first.")
    except Exception:
        return ListingWorkflowResult(status="failed", sku=data.sku,
            error=WorkflowIssue(code="internal_workflow_error", message="Publication could not be verified."),
            next_action="Retry listing_publish; current eBay state will be inspected first.")


async def discard_draft(data: DiscardDraftInput) -> ListingWorkflowResult:
    try:
        async with EbayAPI() as api:
            offers = await _get_offers(api, data.sku)
            if len(offers) > 1 or any(_is_published(offer) or offer.get("listing") for offer in offers):
                return ListingWorkflowResult(status="refused", sku=data.sku, recoverable=False,
                    error=WorkflowIssue(code="active_or_ambiguous_listing", message="Draft cleanup refused because listing state is published or ambiguous."))
            completed = []
            if offers:
                await api.request("DELETE", f"/sell/inventory/v1/offer/{offers[0]['offerId']}", expected={204})
                completed.append("offer_deleted")
            if await _get_inventory(api, data.sku):
                await api.request("DELETE", f"/sell/inventory/v1/inventory_item/{quote(data.sku, safe='')}", expected={204})
                completed.append("inventory_item_deleted")
            if await _get_inventory(api, data.sku) is not None:
                raise EbayWorkflowError("cleanup_verification_failed", "Inventory item still exists after cleanup.")
            return ListingWorkflowResult(status="discarded", sku=data.sku, completed_steps=completed, recoverable=False)
    except EbayWorkflowError as exc:
        return ListingWorkflowResult(status="failed", sku=data.sku, error=WorkflowIssue(code=exc.code, message=exc.message),
            next_action="Inspect the draft before retrying cleanup.")
    except Exception:
        return ListingWorkflowResult(status="failed", sku=data.sku,
            error=WorkflowIssue(code="internal_workflow_error", message="Draft cleanup could not be verified."),
            next_action="Inspect the draft before retrying cleanup.")
