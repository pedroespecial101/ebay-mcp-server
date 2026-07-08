"""Typed public models for the narrow eBay Trading API workflow."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

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
    is_charity: bool = False
    inventory_model: bool | None = None
    supported_for_revision: bool = False
    restrictions: list[str] = Field(default_factory=list)
    listing_url: str | None = None
    revision_token: str


class GetSellerItemInput(BaseModel):
    item_id: str = Field(pattern=r"^\d{8,20}$")


class ViewItemImagesInput(BaseModel):
    item_id: str = Field(pattern=r"^\d{8,20}$")
    start_index: int = Field(default=0, ge=0)
    limit: int = Field(default=4, ge=1, le=6)


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


class FixedPriceListingProposal(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500_000)
    price_gbp: Decimal = Field(gt=0, decimal_places=2)
    category_id: str = Field(pattern=r"^\d+$")
    condition_id: str = Field(pattern=r"^\d+$")
    condition_description: str | None = Field(default=None, max_length=1000)
    item_specifics: dict[str, list[str]] = Field(default_factory=dict)
    picture_urls: list[str] = Field(min_length=1, max_length=24)
    best_offer_enabled: bool = False

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
    max_listing_fee_gbp: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class AddFixedPriceItemResult(BaseModel):
    status: str
    item_id: str | None = None
    listing_url: str | None = None
    fees: list[TradingFee] = Field(default_factory=list)
    actual_fee_gbp: Decimal = Decimal("0.00")
    warnings: list[TradingIssue] = Field(default_factory=list)
    final_listing: EditableSellerListing | None = None
    idempotent_recovery: bool = False
