"""Typed public models for the narrow eBay Trading API workflow."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


class TradingIssue(BaseModel):
    code: str
    severity: str
    message: str
    field: str | None = None


class TradingFee(BaseModel):
    name: str
    amount: Decimal = Decimal("0.00")
    currency: str = "GBP"


class RecentSellerListingsInput(BaseModel):
    lookback_days: int = Field(default=7, ge=1, le=119)
    page_size: int = Field(default=25, ge=1, le=200)
    page_number: int = Field(default=1, ge=1)


class SellerListingSummary(BaseModel):
    item_id: str
    title: str
    price_gbp: Decimal | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: str | None = None
    quantity: int | None = None
    quantity_sold: int = 0
    picture_url: str | None = None
    listing_url: str | None = None
    listing_type: str | None = None


class RecentSellerListingsResult(BaseModel):
    listings: list[SellerListingSummary]
    page_number: int
    page_size: int
    total_pages: int | None = None
    total_entries: int | None = None
    has_more: bool = False
    excluded_count: int = 0
    warnings: list[TradingIssue] = Field(default_factory=list)


class SellerPolicyReferences(BaseModel):
    payment_profile_id: str | None = None
    return_profile_id: str | None = None
    shipping_profile_id: str | None = None


class EditableSellerListing(BaseModel):
    item_id: str
    title: str
    description: str
    price_gbp: Decimal
    condition_id: str | None = None
    condition_description: str | None = None
    primary_category_id: str
    primary_category_name: str | None = None
    item_specifics: dict[str, list[str]] = Field(default_factory=dict)
    best_offer_enabled: bool = False
    picture_urls: list[str] = Field(default_factory=list)
    policies: SellerPolicyReferences = Field(default_factory=SellerPolicyReferences)
    status: str | None = None
    listing_type: str | None = None
    site: str | None = None
    quantity: int = 1
    quantity_sold: int = 0
    has_variations: bool = False
    variation_details: "VariationListingDetails | None" = None
    is_charity: bool = False
    inventory_model: bool | None = None
    supported_for_revision: bool = False
    restrictions: list[str] = Field(default_factory=list)
    listing_url: str | None = None
    revision_token: str


class GetSellerItemInput(BaseModel):
    item_id: str = Field(pattern=r"^\d{8,20}$")


class ViewItemImagesInput(BaseModel):
    item_id: str = Field(pattern=r"^\d{8,20}$", description="The seller listing to inspect.")
    start_index: int = Field(
        default=0,
        ge=0,
        description="Zero-based first photograph. Use next_start_index from the previous response to continue.",
    )
    limit: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Photographs in this response only. Repeat calls can retrieve every image in the listing.",
    )
    max_px: Literal[512, 768, 1024] = Field(
        default=768,
        description="Maximum width or height after safe JPEG normalization.",
    )


class FixedPriceRevisionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, min_length=1, max_length=500_000)
    price_gbp: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    condition_id: str | None = Field(default=None, pattern=r"^\d+$")
    condition_description: str | None = Field(default=None, max_length=1000)
    primary_category_id: str | None = Field(default=None, pattern=r"^\d+$")
    best_offer_enabled: bool | None = None
    item_specifics_upsert: dict[str, list[str]] = Field(default_factory=dict)
    item_specifics_remove: list[str] = Field(default_factory=list)
    picture_urls: list[str] | None = Field(default=None, min_length=1, max_length=24)

    @field_validator("title", "description", "condition_description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("item_specifics_upsert")
    @classmethod
    def validate_specifics(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if any(not key.strip() or not values or any(not item.strip() for item in values) for key, values in value.items()):
            raise ValueError("item specific names and values must be non-empty")
        return value

    @field_validator("picture_urls")
    @classmethod
    def validate_picture_urls(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(not url.startswith("https://") for url in value):
            raise ValueError("picture URLs must use HTTPS")
        return value

    @model_validator(mode="after")
    def at_least_one_change(self):
        fields = self.model_dump(exclude_none=True)
        if not any(value not in ({}, []) for value in fields.values()):
            raise ValueError("at least one revision is required")
        overlap = set(self.item_specifics_upsert) & set(self.item_specifics_remove)
        if overlap:
            raise ValueError(f"item specifics cannot be updated and removed together: {', '.join(sorted(overlap))}")
        return self


class ReviseFixedPriceItemInput(BaseModel):
    item_id: str = Field(pattern=r"^\d{8,20}$")
    revision_token: str = Field(min_length=64, max_length=64)
    patch: FixedPriceRevisionPatch


class ReviseFixedPriceItemResult(BaseModel):
    status: str
    item_id: str
    applied_diff: dict[str, Any] = Field(default_factory=dict)
    warnings: list[TradingIssue] = Field(default_factory=list)
    fees: list[TradingFee] = Field(default_factory=list)
    final_listing: EditableSellerListing | None = None


class UploadListingPicturesInput(BaseModel):
    image_refs: list[str] = Field(min_length=1, max_length=24)


class UploadedListingPicture(BaseModel):
    image_ref: str
    image_id: str | None = None
    image_url: str
    expiration_date: datetime | None = None


class ListingPackage(BaseModel):
    weight_grams: int = Field(gt=0, le=30_000)
    length_cm: Decimal = Field(gt=0, le=200, decimal_places=2)
    width_cm: Decimal = Field(gt=0, le=200, decimal_places=2)
    height_cm: Decimal = Field(gt=0, le=200, decimal_places=2)
    package_type: Literal[
        "PARCEL_OR_PADDED_ENVELOPE", "PACKAGE_THICK_ENVELOPE", "LETTER",
        "LARGE_ENVELOPE", "MAILING_BOX", "PADDED_BAGS", "TOUGH_BAGS",
        "BULKY_GOODS",
    ] = "PARCEL_OR_PADDED_ENVELOPE"


class ListingVariation(BaseModel):
    """One purchasable combination returned by or sent to the Trading API."""

    sku: str | None = Field(default=None, min_length=1, max_length=80)
    price_gbp: Decimal = Field(gt=0, decimal_places=2)
    quantity: int = Field(ge=0, le=999_999)
    quantity_sold: int = Field(default=0, ge=0)
    specifics: dict[str, str] = Field(min_length=1, max_length=5)

    @field_validator("specifics")
    @classmethod
    def validate_specifics(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned = {name.strip(): item.strip() for name, item in value.items()}
        if len(cleaned) != len(value) or any(not name or not item for name, item in cleaned.items()):
            raise ValueError("variation specific names and values must be non-empty")
        return cleaned


class VariationPictureSet(BaseModel):
    value: str = Field(min_length=1, max_length=65)
    picture_urls: list[str] = Field(min_length=1, max_length=12)

    @field_validator("value")
    @classmethod
    def clean_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("picture_urls")
    @classmethod
    def eps_urls_only(cls, value: list[str]) -> list[str]:
        if any(not url.startswith("https://") for url in value):
            raise ValueError("picture URLs must use HTTPS")
        return value


class VariationPictureMapping(BaseModel):
    """Pictures for all values of one, and only one, variation dimension."""

    dimension: str = Field(min_length=1, max_length=65)
    sets: list[VariationPictureSet] = Field(min_length=1)

    @field_validator("dimension")
    @classmethod
    def clean_dimension(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def unique_values(self):
        values = [entry.value for entry in self.sets]
        if len(values) != len(set(values)):
            raise ValueError("each picture-mapped variation value may appear only once")
        return self


class VariationListingDetails(BaseModel):
    """Normalized variation state parsed from Trading GetItem read-back."""

    dimensions: dict[str, list[str]] = Field(default_factory=dict)
    variations: list[ListingVariation] = Field(default_factory=list)
    picture_dimension: str | None = None
    picture_sets: dict[str, list[str]] = Field(default_factory=dict)


class AppendFixedPriceVariationInput(BaseModel):
    """The one safe variation mutation supported for an existing key master."""

    item_id: str = Field(pattern=r"^\d{8,20}$")
    expected_revision_token: str = Field(min_length=64, max_length=64)
    operation_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$",
        description="Durable caller journal ID used to correlate safe retries.",
    )
    variation: ListingVariation
    picture_dimension: Literal["Key Code"] = "Key Code"
    picture_urls: list[str] = Field(min_length=2, max_length=2)

    @field_validator("picture_urls")
    @classmethod
    def eps_urls_only(cls, urls: list[str]) -> list[str]:
        if len(set(urls)) != 2:
            raise ValueError("the two variation pictures must be distinct")
        for url in urls:
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname != "i.ebayimg.com":
                raise ValueError("variation picture URLs must be HTTPS EPS i.ebayimg.com URLs")
        return urls

    @model_validator(mode="after")
    def validate_single_key_variation(self):
        if self.variation.sku is None:
            raise ValueError("the appended variation requires a physical SKU")
        if self.variation.quantity != 1 or self.variation.quantity_sold != 0:
            raise ValueError("the appended variation must have quantity one and no sales")
        if set(self.variation.specifics) != {self.picture_dimension}:
            raise ValueError("the appended variation must use only the Key Code dimension")
        selector = self.variation.specifics[self.picture_dimension]
        if len(selector) > 65:
            raise ValueError("the Key Code selector must be at most 65 characters")
        return self


class AppendFixedPriceVariationResult(BaseModel):
    status: Literal["appended", "already_applied"]
    item_id: str
    operation_id: str
    warnings: list[TradingIssue] = Field(default_factory=list)
    fees: list[TradingFee] = Field(default_factory=list)
    final_listing: EditableSellerListing
    idempotent_recovery: bool = False


class MultiVariationFixedPriceListingProposal(BaseModel):
    """A direct fixed-price Trading proposal with 2--250 purchasable variations."""

    uuid: str | None = Field(default=None, pattern=r"^[0-9A-Fa-f]{32}$")
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500_000)
    category_id: str = Field(pattern=r"^\d+$")
    condition_id: str = Field(pattern=r"^\d+$")
    condition_description: str | None = Field(default=None, max_length=1000)
    item_specifics: dict[str, list[str]] = Field(default_factory=dict)
    picture_urls: list[str] = Field(min_length=1, max_length=24)
    variations: list[ListingVariation] = Field(min_length=2, max_length=250)
    picture_mapping: VariationPictureMapping
    best_offer_enabled: bool = False
    package: ListingPackage | None = None

    @field_validator("uuid")
    @classmethod
    def normalize_uuid(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("title", "description", "condition_description")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("item_specifics")
    @classmethod
    def validate_item_specifics(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if any(not key.strip() or not values or any(not item.strip() for item in values) for key, values in value.items()):
            raise ValueError("item specific names and values must be non-empty")
        return value

    @field_validator("picture_urls")
    @classmethod
    def eps_urls_only(cls, value: list[str]) -> list[str]:
        if any(not url.startswith("https://") for url in value):
            raise ValueError("picture URLs must use HTTPS")
        return value

    @model_validator(mode="after")
    def validate_variation_matrix(self):
        first_names = set(self.variations[0].specifics)
        if not 1 <= len(first_names) <= 5:
            raise ValueError("each variation must use one to five variation dimensions")
        if any(set(entry.specifics) != first_names for entry in self.variations):
            raise ValueError("every variation must specify the same variation dimensions")
        if first_names & set(self.item_specifics):
            raise ValueError("item specifics cannot also be variation dimensions")
        combinations = [tuple(entry.specifics[name] for name in sorted(first_names)) for entry in self.variations]
        if len(combinations) != len(set(combinations)):
            raise ValueError("each variation must have a unique combination of values")
        skus = [entry.sku for entry in self.variations]
        if any(sku is None for sku in skus) or len(skus) != len(set(skus)):
            raise ValueError("every variation requires a unique SKU")
        if self.picture_mapping.dimension not in first_names:
            raise ValueError("the picture-mapped dimension must be a variation dimension")
        dimension_values = {entry.specifics[self.picture_mapping.dimension] for entry in self.variations}
        mapped_values = {entry.value for entry in self.picture_mapping.sets}
        if mapped_values != dimension_values:
            raise ValueError("picture mappings must cover exactly every value of the mapped variation dimension")
        return self


class FixedPriceListingProposal(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500_000)
    price_gbp: Decimal = Field(gt=0, decimal_places=2)
    category_id: str = Field(pattern=r"^\d+$")
    condition_id: str = Field(pattern=r"^\d+$")
    condition_description: str | None = Field(default=None, max_length=1000)
    item_specifics: dict[str, list[str]] = Field(default_factory=dict)
    picture_urls: list[str] = Field(min_length=1, max_length=24)
    best_offer_enabled: bool = False
    package: ListingPackage | None = None

    @field_validator("title", "description", "condition_description")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("item_specifics")
    @classmethod
    def validate_item_specifics(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if any(not key.strip() or not values or any(not item.strip() for item in values) for key, values in value.items()):
            raise ValueError("item specific names and values must be non-empty")
        return value

    @field_validator("picture_urls")
    @classmethod
    def eps_urls_only(cls, value: list[str]) -> list[str]:
        if any(not url.startswith("https://") for url in value):
            raise ValueError("picture URLs must use HTTPS")
        return value


class VerifyAddFixedPriceItemInput(BaseModel):
    proposal: FixedPriceListingProposal


class VerifyAddFixedPriceItemResult(BaseModel):
    valid: bool
    verification_token: str | None = None
    expires_at: datetime | None = None
    fees: list[TradingFee] = Field(default_factory=list)
    estimated_fee_gbp: Decimal = Decimal("0.00")
    warnings: list[TradingIssue] = Field(default_factory=list)
    errors: list[TradingIssue] = Field(default_factory=list)


class AddFixedPriceItemInput(BaseModel):
    proposal: FixedPriceListingProposal
    verification_token: str = Field(min_length=20)


class AddFixedPriceItemResult(BaseModel):
    status: str
    item_id: str | None = None
    listing_url: str | None = None
    fees: list[TradingFee] = Field(default_factory=list)
    actual_fee_gbp: Decimal = Decimal("0.00")
    warnings: list[TradingIssue] = Field(default_factory=list)
    final_listing: EditableSellerListing | None = None
    idempotent_recovery: bool = False


class VerifyAddFixedPriceVariationsInput(BaseModel):
    proposal: MultiVariationFixedPriceListingProposal


class VerifyAddFixedPriceVariationsResult(VerifyAddFixedPriceItemResult):
    """A short-lived confirmation record, safe to persist with its UUID and digest."""

    uuid: str | None = None
    proposal_digest: str | None = None


class AddFixedPriceVariationsInput(BaseModel):
    proposal: MultiVariationFixedPriceListingProposal
    verification_token: str = Field(min_length=20)


class AddFixedPriceVariationsResult(AddFixedPriceItemResult):
    uuid: str
    proposal_digest: str
