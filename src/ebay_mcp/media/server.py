"""MCP Apps image uploader and safe non-interactive image ingress."""

import asyncio
import base64
import logging
from typing import Any
from urllib.parse import urlparse

from fastmcp import FastMCP
from fastmcp.apps.file_upload import FileUpload, _b64_decoded_size, _format_size
from fastmcp.server.context import Context
from fastmcp.tools.base import ToolResult
from fastmcp.utilities.types import Image
from mcp.types import TextContent
from prefab_ui.actions import SetState, ShowToast
from prefab_ui.actions.mcp import CallTool
from prefab_ui.app import PrefabApp
from prefab_ui.components import Badge, Button, Card, CardContent, CardHeader, Column, DropZone, H3, Muted, Row, Small
from prefab_ui.components.control_flow import ForEach, If
from prefab_ui.rx import ERROR, RESULT, STATE, Rx

from ebay_mcp.media.storage import (
    EBAY_IMAGE_HOSTS,
    MAX_INPUT_BYTES,
    download_public_image,
    list_staged,
    prepare_model_image,
    stage_bytes,
    stage_source,
)
from models.ebay.listing_workflow import StageImagesInput, StagedImage, ViewEbayImageInput


logger = logging.getLogger(__name__)


def _approved_ebay_image_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or host not in EBAY_IMAGE_HOSTS
    ):
        raise ValueError("Only public HTTPS URLs on approved eBay image domains can be viewed.")
    return host


class EbayImageUpload(FileUpload):
    """An image-only FileUpload whose bytes go directly to private R2."""

    def _register_tools(self) -> None:
        provider = self

        @self.tool(
            name="store_images",
            description=(
                "Stage uploaded listing photographs privately in R2. "
                "This stores media for later listing creation; it does not publish or change an eBay listing."
            ),
        )
        def store_images(files: list[dict], ctx: Context) -> list[dict]:
            """Store uploaded photographs privately without placing their bytes in model context."""
            if not 1 <= len(files) <= 24:
                raise ValueError("Upload between 1 and 24 images.")
            for file in files:
                if _b64_decoded_size(file.get("data", "")) > provider._max_file_size:
                    raise ValueError(f"{file.get('name', 'Image')} exceeds {_format_size(provider._max_file_size)}.")
                mime = file.get("type", "").lower()
                if mime not in {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}:
                    raise ValueError("Only JPEG, PNG, WebP and HEIC images are accepted.")
            return provider.on_store(files, ctx)

        @self.tool(
            name="list_staged_images",
            model=True,
            description="List private staged image references; read-only and does not contact eBay.",
        )
        def list_staged_images(ctx: Context) -> list[dict]:
            """List private staged images and their opaque references."""
            return provider.on_list(ctx)

        @self.ui(
            name="open_image_uploader",
            description=(
                "Open the private listing-photograph uploader UI. "
                "Use before listing_create when local image upload is needed."
            ),
            annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        )
        def open_image_uploader(ctx: Context) -> PrefabApp:
            """Open the image uploader; uploaded bytes bypass the language-model context."""
            with Card(css_class="max-w-2xl mx-auto") as view:
                with CardHeader(), Row(gap=2, align="center"):
                    H3(provider._title)
                    with If(STATE.stored.length()):
                        Badge(STATE.stored.length(), variant="secondary")
                with CardContent(), Column(gap=4):
                    Muted(provider._description)
                    DropZone(name="pending", icon="image", label=provider._drop_label,
                        description="JPEG, PNG, WebP or HEIC; up to 12 MiB each", multiple=True,
                        max_size=provider._max_file_size)
                    with If(STATE.pending.length()), Column(gap=2):
                        with ForEach("pending"), Row(gap=2, align="center"), Column(gap=0):
                            Small(Rx("$item.name"))
                            Muted(Rx("$item.type"))
                        Button("Stage images", on_click=CallTool("store_images", arguments={"files": Rx("pending")},
                            on_success=[SetState("stored", RESULT), SetState("pending", []),
                                ShowToast("Images staged", variant="success")],
                            on_error=ShowToast(ERROR, variant="error")))
                    with If(STATE.stored.length()):
                        with ForEach("stored") as image, Row(gap=2, align="center", css_class="justify-between"):
                            Small(image.filename)
                            Badge(image.size_display, variant="outline")
            return PrefabApp(view=view, state={"pending": [], "stored": provider.on_list(ctx)})

    def on_store(self, files: list[dict[str, Any]], ctx: Context) -> list[dict[str, Any]]:
        staged = [stage_bytes(base64.b64decode(file["data"], validate=True), file.get("name")) for file in files]
        return [self._summary(image) for image in staged]

    def on_list(self, ctx: Context) -> list[dict[str, Any]]:
        return [self._summary(image) for image in list_staged()]

    @staticmethod
    def _summary(image: StagedImage) -> dict[str, Any]:
        data = image.model_dump()
        data["size_display"] = _format_size(image.size)
        data["type"] = "image/jpeg"
        return data


media_mcp = FastMCP("eBay private image staging")
media_mcp.add_provider(EbayImageUpload(
    name="eBay images", max_file_size=MAX_INPUT_BYTES, title="eBay listing photographs",
    description="Images are normalized and stored privately; the model receives only opaque references.",
    drop_label="Drop listing photographs here in gallery order",
))


@media_mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})
async def stage_images(input: StageImagesInput) -> list[StagedImage]:
    """Stage ordered public HTTPS images or files from the restricted local import directory."""
    results = []
    for source in input.sources:
        results.append(await stage_source(source))
    return results


@media_mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
async def view_ebay_image(input: ViewEbayImageInput) -> ToolResult:
    """View one approved eBay CDN image URL as a normalized MCP image.

    This is a model-vision viewer for eBay image URLs returned by Browse or
    Trading results. It is not a staging/upload tool and not a general web image
    proxy. The server fetches only approved eBay image hosts, strips metadata,
    resizes to max_px, re-encodes as JPEG, and omits the source URL from the
    result. Prefer max_px=768; if a client blocks an image, retry with 512.
    """
    host = _approved_ebay_image_url(input.url)
    logger.info(
        "Preparing eBay CDN image for model inspection host=%s max_px=%d.",
        host,
        input.max_px,
    )
    data, filename = await download_public_image(input.url, allowed_hosts=EBAY_IMAGE_HOSTS)
    prepared, width, height = await asyncio.to_thread(
        prepare_model_image,
        data,
        filename,
        input.max_px,
    )
    logger.info(
        "Prepared eBay CDN image for model inspection width=%d height=%d bytes=%d.",
        width,
        height,
        len(prepared),
    )
    return ToolResult(
        content=[
            TextContent(type="text", text="One normalized eBay image for visual inspection."),
            Image(data=prepared, format="jpeg").to_image_content(),
        ],
        structured_content={
            "source": "ebay_image_cdn",
            "width": width,
            "height": height,
            "max_px": input.max_px,
            "mime_type": "image/jpeg",
        },
    )
