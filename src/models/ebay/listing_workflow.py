"""Public models for the high-level eBay listing workflow."""

from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ImageSourceKind(str, Enum):
    URL = "url"
    LOCAL_FILE = "local_file"


class ImageSource(BaseModel):
    kind: ImageSourceKind
    value: str = Field(min_length=1, description="HTTPS URL or path inside the configured import directory.")
    filename: str | None = None


class StageImagesInput(BaseModel):
    sources: list[ImageSource] = Field(min_length=1, max_length=24)


class ViewEbayImageInput(BaseModel):
    url: str = Field(
        min_length=1,
        description="Public HTTPS image URL hosted on eBay's approved image CDN.",
    )
    max_px: Literal[512, 768, 1024] = Field(
        default=768,
        description="Maximum width or height after safe JPEG normalization.",
    )


class StagedImage(BaseModel):
    image_ref: str
    filename: str
    size: int
    width: int
    height: int
    uploaded_at: str


class ListingMode(str, Enum):
    DRAFT = "draft"
    PUBLISH = "publish"


class SimpleListingInput(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=4000)
    price_gbp: Decimal = Field(gt=0, decimal_places=2)
    category_id: str = Field(min_length=1)
    condition: str = Field(min_length=1)
    condition_description: str = Field(min_length=1, max_length=1000)
    aspects: dict[str, list[str]]
    image_refs: list[str] = Field(min_length=1, max_length=24)
    mode: ListingMode = ListingMode.DRAFT

    @field_validator("sku", "title", "description", "category_id", "condition", "condition_description")
    @classmethod
    def no_blank_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("aspects")
    @classmethod
    def valid_aspects(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if any(not name.strip() or not values or any(not item.strip() for item in values) for name, values in value.items()):
            raise ValueError("aspect names and values must be non-empty")
        return value


class PublishListingInput(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    max_fee_gbp: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class DiscardDraftInput(BaseModel):
    sku: str = Field(min_length=1, max_length=50)


class WorkflowIssue(BaseModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class FeeEstimate(BaseModel):
    amount_gbp: Decimal = Decimal("0.00")
    fees: list[dict[str, Any]] = Field(default_factory=list)


class ListingValidationResult(BaseModel):
    valid: bool
    normalized: SimpleListingInput
    errors: list[WorkflowIssue] = Field(default_factory=list)
    warnings: list[WorkflowIssue] = Field(default_factory=list)


class ListingWorkflowResult(BaseModel):
    status: str
    completed_steps: list[str] = Field(default_factory=list)
    sku: str
    offer_id: str | None = None
    listing_id: str | None = None
    listing_url: str | None = None
    fee_estimate: FeeEstimate | None = None
    warnings: list[WorkflowIssue] = Field(default_factory=list)
    recoverable: bool = True
    next_action: str | None = None
    error: WorkflowIssue | None = None
