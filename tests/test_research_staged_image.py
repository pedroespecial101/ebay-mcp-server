from __future__ import annotations

import asyncio
import base64
import time

import httpx
from fastmcp import Client

from ebay_mcp.research.client import EbayClient
from ebay_mcp.research.config import Settings
from ebay_mcp.research.models import ImageSearchRequest, SearchResponse
from ebay_mcp.research import server as research_server


def test_private_bytes_are_sent_directly_to_browse_image_search():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "total": 1,
                "itemSummaries": [{"itemId": "v1|123|0", "title": "Visual match"}],
            },
        )

    async def run() -> SearchResponse:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = EbayClient(
                settings=Settings(
                    client_id=None,
                    client_secret=None,
                    api_base_url="https://api.ebay.test",
                ),
                http_client=http,
            )
            client._token = "test-token"
            client._token_expires_at = time.monotonic() + 60
            return await client.search_by_image_bytes(
                ImageSearchRequest(
                    image_url="https://private-staged-image.invalid/source.jpg",
                    category_id="9355",
                    limit=5,
                ),
                b"private-jpeg-bytes",
            )
        finally:
            await http.aclose()

    result = asyncio.run(run())
    assert result.items[0].title == "Visual match"
    assert len(requests) == 1
    request = requests[0]
    assert request.url.path.endswith("/search_by_image")
    assert request.url.params["category_ids"] == "9355"
    assert request.headers["Authorization"] == "Bearer test-token"
    assert request.read()
    assert base64.b64encode(b"private-jpeg-bytes") in request.content


def test_staged_image_tool_reads_private_ref_without_public_url(monkeypatch):
    class FakeEbayClient:
        def __init__(self) -> None:
            self.image: bytes | None = None

        async def search_by_image_bytes(
            self, request: ImageSearchRequest, image: bytes
        ) -> SearchResponse:
            self.image = image
            assert request.category_id == "9355"
            return SearchResponse(total=0, limit=request.limit, offset=request.offset)

    fake = FakeEbayClient()
    monkeypatch.setattr(
        research_server,
        "get_staged_bytes",
        lambda image_ref: (b"trusted-staged-image", "photo.jpg"),
    )

    async def run():
        async with Client(research_server.create_server(fake)) as client:
            tools = await client.list_tools()
            assert "search_by_staged_image" in {tool.name for tool in tools}
            return await client.call_tool(
                "search_by_staged_image",
                {"image_ref": "r2:staging/seller/ref/photo.jpg", "category_id": "9355"},
            )

    result = asyncio.run(run())
    assert not result.is_error
    assert fake.image == b"trusted-staged-image"
