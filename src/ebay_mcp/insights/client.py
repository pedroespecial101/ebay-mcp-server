"""Small authenticated REST client for seller reporting endpoints.

Only fixed eBay paths supplied by this package are called. Error bodies and
tokens are deliberately excluded from exceptions and logs.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ebay_auth.ebay_auth import refresh_access_token
from ebay_service import get_ebay_access_token
from utils.api_utils import is_token_error


class SellerInsightsError(RuntimeError):
    pass


class SellerInsightsClient:
    BASE = "https://api.ebay.com"

    def __init__(self, client: httpx.AsyncClient | None = None, access_token: str | None = None):
        self.client = client or httpx.AsyncClient(timeout=45)
        self.access_token = access_token
        self.owned_client = client is None

    async def __aenter__(self):
        if not self.access_token:
            self.access_token = await get_ebay_access_token()
        if not self.access_token or is_token_error(self.access_token):
            raise SellerInsightsError("Seller authentication is unavailable; reauthorize the seller account.")
        return self

    async def __aexit__(self, *_):
        if self.owned_client:
            await self.client.aclose()

    async def request(
        self, method: str, path: str, *, params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        if not path.startswith("/sell/") or ".." in path or "://" in path:
            raise ValueError("Only fixed eBay Sell API paths are allowed.")
        if method not in {"GET", "POST"} or (method == "POST" and path != "/sell/marketing/v1/ad_report_task"):
            raise ValueError("Only reporting reads and report-task creation are allowed.")
        for attempt in range(2):
            try:
                response = await self.client.request(
                    method, self.BASE + path, params=params, json=json,
                    headers={"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"},
                )
            except httpx.RequestError as exc:
                raise SellerInsightsError(f"eBay reporting request failed: {exc.__class__.__name__}.") from exc
            if response.status_code == 401 and attempt == 0:
                token = await asyncio.to_thread(refresh_access_token)
                if not token or is_token_error(token):
                    raise SellerInsightsError("Seller authentication expired; reauthorize the seller account.")
                self.access_token = token
                continue
            if response.status_code == 403:
                raise SellerInsightsError("eBay denied this read. Check reporting OAuth scopes and seller authorization.")
            if response.status_code >= 400:
                raise SellerInsightsError(f"eBay reporting API returned HTTP {response.status_code}.")
            return response
        raise SellerInsightsError("Seller authentication is unavailable after one refresh.")

    async def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self.request("GET", path, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise SellerInsightsError("eBay returned invalid reporting JSON.") from exc
        if not isinstance(payload, dict):
            raise SellerInsightsError("eBay returned an unexpected reporting payload.")
        return payload
