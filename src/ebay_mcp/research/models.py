from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SortOrder(StrEnum):
    BEST_MATCH = "best_match"
    NEWLY_LISTED = "newly_listed"
    ENDING_SOONEST = "ending_soonest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"


class BuyingOption(StrEnum):
    FIXED_PRICE = "FIXED_PRICE"
    AUCTION = "AUCTION"
    BEST_OFFER = "BEST_OFFER"
    CLASSIFIED_AD = "CLASSIFIED_AD"


class VehicleCompatibility(ApiModel):
    year: str = Field(description="Vehicle model year")
    make: str
    model: str
    trim: str | None = None
    engine: str | None = None
    submodel: str | None = None


class SearchRequest(ApiModel):
    query: str | None = Field(default=None, min_length=2)
    gtin: str | None = Field(default=None, min_length=8)
    category_ids: list[str] = Field(default_factory=list, max_length=3)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    condition_ids: list[str] = Field(default_factory=list)
    buying_options: list[BuyingOption] = Field(default_factory=list)
    item_location_country: str | None = Field(default=None, min_length=2, max_length=2)
    search_in_description: bool = False
    aspect_filters: dict[str, list[str]] = Field(default_factory=dict)
    vehicle: VehicleCompatibility | None = None
    sort: SortOrder = SortOrder.BEST_MATCH
    include_refinements: bool = False
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=9_999)

    @model_validator(mode="after")
    def validate_search(self) -> SearchRequest:
        if bool(self.query) == bool(self.gtin):
            raise ValueError("Provide exactly one of query or gtin")
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price cannot exceed max_price")
        if self.offset and self.offset % self.limit:
            raise ValueError("offset must be zero or a multiple of limit")
        if (self.aspect_filters or self.vehicle) and len(self.category_ids) != 1:
            raise ValueError(
                "Exactly one category_id is required for aspect or vehicle filters"
            )
        return self


class ImageSearchRequest(ApiModel):
    image_url: str
    category_id: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    condition_ids: list[str] = Field(default_factory=list)
    buying_options: list[BuyingOption] = Field(default_factory=list)
    item_location_country: str | None = Field(default=None, min_length=2, max_length=2)
    aspect_filters: dict[str, list[str]] = Field(default_factory=dict)
    include_refinements: bool = False
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=9_999)

    @model_validator(mode="after")
    def validate_image_search(self) -> ImageSearchRequest:
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price cannot exceed max_price")
        if self.offset and self.offset % self.limit:
            raise ValueError("offset must be zero or a multiple of limit")
        if self.aspect_filters and not self.category_id:
            raise ValueError("category_id is required for aspect filters")
        return self


class Money(ApiModel):
    value: str
    currency: str


class SellerSummary(ApiModel):
    username: str | None = None
    feedback_score: int | None = None
    feedback_percentage: str | None = None
    account_type: str | None = None


class Location(ApiModel):
    city: str | None = None
    county: str | None = None
    postal_code: str | None = None
    country: str | None = None


class Category(ApiModel):
    category_id: str
    category_name: str | None = None


class CompatibilityProperty(ApiModel):
    name: str
    value: str


class ShippingSummary(ApiModel):
    cost: Money | None = None
    min_delivery_date: str | None = None
    max_delivery_date: str | None = None


class SearchItem(ApiModel):
    item_id: str
    legacy_item_id: str | None = None
    title: str
    url: str | None = None
    image_url: str | None = None
    price: Money | None = None
    current_bid_price: Money | None = None
    shipping: list[ShippingSummary] = Field(default_factory=list)
    condition: str | None = None
    condition_id: str | None = None
    buying_options: list[str] = Field(default_factory=list)
    bid_count: int | None = None
    seller: SellerSummary | None = None
    location: Location | None = None
    categories: list[Category] = Field(default_factory=list)
    item_creation_date: str | None = None
    item_end_date: str | None = None
    short_description: str | None = None
    compatibility_match: str | None = None
    compatibility_properties: list[CompatibilityProperty] = Field(default_factory=list)


class RefinementValue(ApiModel):
    value: str
    match_count: int | None = None


class AspectRefinement(ApiModel):
    name: str
    values: list[RefinementValue] = Field(default_factory=list)


class Refinements(ApiModel):
    dominant_category_id: str | None = None
    categories: list[RefinementValue] = Field(default_factory=list)
    conditions: list[RefinementValue] = Field(default_factory=list)
    buying_options: list[RefinementValue] = Field(default_factory=list)
    aspects: list[AspectRefinement] = Field(default_factory=list)


class ApiWarning(ApiModel):
    code: int | str | None = None
    message: str


class SearchResponse(ApiModel):
    notice: str = (
        "Live listings and asking prices only; not completed-sale comparables."
    )
    total: int
    limit: int
    offset: int
    next_offset: int | None = None
    items: list[SearchItem] = Field(default_factory=list)
    refinements: Refinements | None = None
    warnings: list[ApiWarning] = Field(default_factory=list)


class ItemDetail(ApiModel):
    notice: str = "Live listing details only; not a completed-sale comparable."
    item_id: str
    legacy_item_id: str | None = None
    title: str
    url: str | None = None
    description: str | None = None
    short_description: str | None = None
    images: list[str] = Field(default_factory=list)
    price: Money | None = None
    current_bid_price: Money | None = None
    condition: str | None = None
    condition_id: str | None = None
    buying_options: list[str] = Field(default_factory=list)
    bid_count: int | None = None
    seller: SellerSummary | None = None
    location: Location | None = None
    categories: list[Category] = Field(default_factory=list)
    aspects: dict[str, list[str]] = Field(default_factory=dict)
    availability_status: str | None = None
    estimated_available_quantity: int | None = None
    quantity_sold: int | None = None
    shipping: list[ShippingSummary] = Field(default_factory=list)
    return_terms: dict[str, Any] | None = None
    item_creation_date: str | None = None
    item_end_date: str | None = None
    compatibility_match: str | None = None
    compatibility_properties: list[CompatibilityProperty] = Field(default_factory=list)
