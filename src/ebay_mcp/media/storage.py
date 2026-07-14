"""Private R2 image staging, normalization, and safe ingress."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import socket
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import boto3
import httpx
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from models.ebay.listing_workflow import ImageSource, ImageSourceKind, StagedImage

register_heif_opener()
MAX_INPUT_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 12 * 1024 * 1024
MAX_MODEL_IMAGE_BYTES = 400 * 1024
MAX_MODEL_IMAGE_EDGE = 1024
MAX_IMAGE_PIXELS = 50_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "HEIC"}
EBAY_IMAGE_HOSTS = {"i.ebayimg.com"}


class MediaStorageError(ValueError):
    pass


def _settings() -> dict[str, str]:
    values = {
        "account": os.getenv("R2_ACCOUNT_ID", ""),
        "access": os.getenv("R2_ACCESS_KEY_ID", ""),
        "secret": os.getenv("R2_SECRET_ACCESS_KEY", ""),
        "bucket": os.getenv("R2_BUCKET_NAME", "ebay-listing-staging"),
    }
    if not all(values.values()):
        raise MediaStorageError("Private image staging is not configured on this server.")
    return values


def _client():
    cfg = _settings()
    return boto3.client(
        "s3", endpoint_url=f"https://{cfg['account']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["access"], aws_secret_access_key=cfg["secret"], region_name="auto",
    )


def _scope() -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", os.getenv("EBAY_USER_ID", "seller"))[:80]


def _safe_name(name: str | None) -> str:
    stem = Path(name or "image").stem
    stem = re.sub(r"[^a-zA-Z0-9_.-]", "_", stem).strip("._") or "image"
    return stem[:80] + ".jpg"


def normalize_image(data: bytes, filename: str | None = None) -> tuple[bytes, int, int]:
    if not data or len(data) > MAX_INPUT_BYTES:
        raise MediaStorageError("Image must be between 1 byte and 12 MiB.")
    try:
        with Image.open(BytesIO(data)) as source:
            if (source.format or "").upper() not in ALLOWED_FORMATS:
                raise MediaStorageError("Only JPEG, PNG, WebP and HEIC images are accepted.")
            image = ImageOps.exif_transpose(source)
            if image.mode not in ("RGB", "L"):
                background = Image.new("RGB", image.size, "white")
                if "A" in image.getbands():
                    background.paste(image, mask=image.getchannel("A"))
                else:
                    background.paste(image.convert("RGB"))
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((4000, 4000), Image.Resampling.LANCZOS)
            for quality in (90, 85, 80, 75):
                output = BytesIO()
                image.save(output, "JPEG", quality=quality, optimize=True, progressive=True, icc_profile=None, exif=b"")
                result = output.getvalue()
                if len(result) <= MAX_OUTPUT_BYTES:
                    return result, image.width, image.height
    except MediaStorageError:
        raise
    except Exception as exc:
        raise MediaStorageError(f"Could not decode {filename or 'image'} as an image.") from exc
    raise MediaStorageError("Normalized image remains larger than 12 MiB.")


def prepare_model_image(
    data: bytes,
    filename: str | None = None,
    max_edge: int = MAX_MODEL_IMAGE_EDGE,
) -> tuple[bytes, int, int]:
    """Create a compact, metadata-free JPEG suitable for an MCP image content block."""
    if not data or len(data) > MAX_INPUT_BYTES:
        raise MediaStorageError("Image must be between 1 byte and 12 MiB.")
    if max_edge not in {512, 768, 1024}:
        raise MediaStorageError("Model images must use a 512, 768 or 1024 pixel maximum edge.")
    try:
        with Image.open(BytesIO(data)) as source:
            if (source.format or "").upper() not in ALLOWED_FORMATS:
                raise MediaStorageError("Only JPEG, PNG, WebP and HEIC images are accepted.")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise MediaStorageError("Image dimensions are too large to inspect safely.")
            image = ImageOps.exif_transpose(source)
            if image.mode not in ("RGB", "L"):
                background = Image.new("RGB", image.size, "white")
                if "A" in image.getbands():
                    background.paste(image, mask=image.getchannel("A"))
                else:
                    background.paste(image.convert("RGB"))
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            for quality in (85, 75, 65, 55, 45):
                output = BytesIO()
                image.save(output, "JPEG", quality=quality, optimize=True, progressive=True, icc_profile=None, exif=b"")
                result = output.getvalue()
                if len(result) <= MAX_MODEL_IMAGE_BYTES:
                    return result, image.width, image.height
    except MediaStorageError:
        raise
    except Exception as exc:
        raise MediaStorageError(f"Could not decode {filename or 'image'} as an image.") from exc
    raise MediaStorageError("Image remains too large for model inspection after normalization.")


def stage_bytes(data: bytes, filename: str | None = None) -> StagedImage:
    normalized, width, height = normalize_image(data, filename)
    name = _safe_name(filename)
    key = f"staging/{_scope()}/{uuid.uuid4().hex}/{name}"
    uploaded_at = datetime.now(timezone.utc).isoformat()
    _client().put_object(
        Bucket=_settings()["bucket"], Key=key, Body=normalized, ContentType="image/jpeg",
        Metadata={"width": str(width), "height": str(height), "filename": name, "uploaded-at": uploaded_at},
    )
    return StagedImage(image_ref=f"r2:{key}", filename=name, size=len(normalized), width=width, height=height, uploaded_at=uploaded_at)


def get_staged_bytes(image_ref: str) -> tuple[bytes, str]:
    prefix = f"r2:staging/{_scope()}/"
    if not image_ref.startswith(prefix) or ".." in image_ref:
        raise MediaStorageError("Unknown or inaccessible image reference.")
    key = image_ref[3:]
    response = _client().get_object(Bucket=_settings()["bucket"], Key=key)
    data = response["Body"].read(MAX_OUTPUT_BYTES + 1)
    if len(data) > MAX_OUTPUT_BYTES:
        raise MediaStorageError("Staged image is unexpectedly large.")
    return data, Path(key).name


def list_staged() -> list[StagedImage]:
    prefix = f"staging/{_scope()}/"
    response = _client().list_objects_v2(Bucket=_settings()["bucket"], Prefix=prefix, MaxKeys=100)
    results = []
    for item in response.get("Contents", []):
        head = _client().head_object(Bucket=_settings()["bucket"], Key=item["Key"])
        meta = head.get("Metadata", {})
        results.append(StagedImage(image_ref=f"r2:{item['Key']}", filename=meta.get("filename", Path(item["Key"]).name),
            size=item["Size"], width=int(meta.get("width", 0)), height=int(meta.get("height", 0)),
            uploaded_at=meta.get("uploaded-at", item["LastModified"].isoformat())))
    return sorted(results, key=lambda image: image.uploaded_at)


def put_manifest(sku: str, digest: str, value: dict) -> None:
    key = f"manifests/{_scope()}/{re.sub(r'[^a-zA-Z0-9_.-]', '_', sku)}/{digest}.json"
    _client().put_object(Bucket=_settings()["bucket"], Key=key, Body=json.dumps(value).encode(), ContentType="application/json")


def get_manifest(sku: str, digest: str) -> dict | None:
    key = f"manifests/{_scope()}/{re.sub(r'[^a-zA-Z0-9_.-]', '_', sku)}/{digest}.json"
    try:
        response = _client().get_object(Bucket=_settings()["bucket"], Key=key)
    except Exception as exc:
        if getattr(exc, "response", {}).get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
            return None
        raise
    return json.loads(response["Body"].read())


def _validate_public_host(host: str) -> None:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise MediaStorageError("Image host could not be resolved.") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise MediaStorageError("Image URL resolves to a private or unsafe network address.")


async def download_public_image(
    url: str,
    allowed_hosts: set[str] | None = None,
) -> tuple[bytes, str]:
    current = url
    async with httpx.AsyncClient(follow_redirects=False, timeout=20) as client:
        for _ in range(4):
            parsed = urlparse(current)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise MediaStorageError("Image URLs must be public HTTPS URLs without credentials.")
            if allowed_hosts is not None and parsed.hostname.casefold() not in allowed_hosts:
                raise MediaStorageError("Image URL is not hosted on an approved image domain.")
            await asyncio.to_thread(_validate_public_host, parsed.hostname)
            async with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise MediaStorageError("Image redirect had no destination.")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                if not response.headers.get("content-type", "").lower().startswith("image/"):
                    raise MediaStorageError("URL did not return an image.")
                declared = response.headers.get("content-length")
                if declared and int(declared) > MAX_INPUT_BYTES:
                    raise MediaStorageError("Remote image exceeds 12 MiB.")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_INPUT_BYTES:
                        raise MediaStorageError("Remote image exceeds 12 MiB.")
                return bytes(content), Path(parsed.path).name or "image"
    raise MediaStorageError("Image URL redirected too many times.")


async def stage_source(source: ImageSource) -> StagedImage:
    if source.kind == ImageSourceKind.URL:
        data, inferred = await download_public_image(source.value)
        return await asyncio.to_thread(stage_bytes, data, source.filename or inferred)
    roots = {
        Path(os.getenv("EBAY_IMAGE_IMPORT_DIR", "~/Pictures/eBay Listing Inbox")).expanduser().resolve(),
        Path(
            os.getenv(
                "EBAY_LISTING_STUDIO_IMPORT_DIR",
                "~/Library/Application Support/eBay Listing Studio/images/ebay",
            )
        ).expanduser().resolve(),
    }
    roots.update(
        Path(value).expanduser().resolve()
        for value in os.getenv("EBAY_IMAGE_IMPORT_DIRS", "").split(os.pathsep)
        if value.strip()
    )
    path = Path(source.value).expanduser().resolve()
    if not any(path.is_relative_to(root) for root in roots) or not path.is_file():
        raise MediaStorageError("Local image must be a file inside an approved import directory.")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise MediaStorageError("Local image exceeds 12 MiB.")
    return await asyncio.to_thread(stage_bytes, path.read_bytes(), source.filename or path.name)
