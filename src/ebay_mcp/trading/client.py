"""Shared, OAuth-backed XML client for eBay's Trading API."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import httpx

from ebay_auth.ebay_auth import refresh_access_token
from ebay_service import get_ebay_access_token
from models.ebay.trading import TradingIssue
from utils.api_utils import is_token_error

logger = logging.getLogger(__name__)

NS = "urn:ebay:apis:eBLBaseComponents"
ENDPOINT = "https://api.ebay.com/ws/api.dll"
SITE_ID = "3"
DEFAULT_VERSION = "1455"


def qname(name: str) -> str:
    return f"{{{NS}}}{name}"


def element(name: str, text: object | None = None, parent: ET.Element | None = None) -> ET.Element:
    node = ET.SubElement(parent, qname(name)) if parent is not None else ET.Element(qname(name))
    if text is not None:
        if isinstance(text, bool):
            node.text = "true" if text else "false"
        else:
            node.text = str(text)
    return node


def find(node: ET.Element | None, path: str) -> ET.Element | None:
    if node is None:
        return None
    return node.find("/".join(qname(part) for part in path.split("/")))


def findall(node: ET.Element | None, path: str) -> list[ET.Element]:
    if node is None:
        return []
    return list(node.findall("/".join(qname(part) for part in path.split("/"))))


def value(node: ET.Element | None, path: str, default: str | None = None) -> str | None:
    found = find(node, path)
    return found.text if found is not None and found.text is not None else default


@dataclass
class TradingResponse:
    root: ET.Element
    ack: str
    errors: list[TradingIssue]

    @property
    def successful(self) -> bool:
        return self.ack in {"Success", "Warning"} and not any(issue.severity.lower() == "error" for issue in self.errors)

    @property
    def warnings(self) -> list[TradingIssue]:
        return [issue for issue in self.errors if issue.severity.lower() != "error"]

    @property
    def blocking_errors(self) -> list[TradingIssue]:
        return [issue for issue in self.errors if issue.severity.lower() == "error"]


class TradingAPIError(RuntimeError):
    def __init__(self, message: str, issues: list[TradingIssue] | None = None,
                 status_code: int | None = None, root: ET.Element | None = None):
        super().__init__(message)
        self.issues = issues or []
        self.status_code = status_code
        self.root = root


def parse_issues(root: ET.Element) -> list[TradingIssue]:
    issues = []
    for error in findall(root, "Errors"):
        issues.append(TradingIssue(
            code=value(error, "ErrorCode", "unknown") or "unknown",
            severity=value(error, "SeverityCode", "Error") or "Error",
            message=(value(error, "LongMessage") or value(error, "ShortMessage") or "eBay rejected the request."),
        ))
    return issues


def _is_expired_token_response(issues: list[TradingIssue]) -> bool:
    """Recognize Trading API auth failures returned inside an HTTP 200 XML body."""
    auth_phrases = ("iaf token", "access token", "oauth token")
    expiry_phrases = ("expired", "invalid", "not valid")
    return any(
        any(auth in issue.message.casefold() for auth in auth_phrases)
        and any(expiry in issue.message.casefold() for expiry in expiry_phrases)
        for issue in issues
    )


class TradingClient:
    def __init__(self, client: httpx.AsyncClient | None = None, access_token: str | None = None):
        self.client = client or httpx.AsyncClient(timeout=30)
        self.access_token = access_token
        self.owned_client = client is None

    async def __aenter__(self):
        if not self.access_token:
            self.access_token = await get_ebay_access_token()
        if is_token_error(self.access_token):
            raise TradingAPIError("Seller authentication is unavailable; run the eBay login tool.")
        return self

    async def __aexit__(self, *_):
        if self.owned_client:
            await self.client.aclose()

    async def _refresh_access_token(self) -> None:
        token = await asyncio.to_thread(refresh_access_token)
        if not token or is_token_error(token):
            raise TradingAPIError("Seller authentication expired and could not be refreshed; run the eBay login tool.")
        self.access_token = token
        logger.info("Refreshed seller authentication after an eBay Trading API auth failure.")

    async def _call_once(self, call_name: str, payload: bytes) -> TradingResponse:
        if not self.access_token:
            raise TradingAPIError("TradingClient must be entered before making a request.")
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "X-EBAY-API-CALL-NAME": call_name,
            "X-EBAY-API-COMPATIBILITY-LEVEL": os.getenv("EBAY_TRADING_API_VERSION", DEFAULT_VERSION),
            "X-EBAY-API-SITEID": SITE_ID,
            "X-EBAY-API-IAF-TOKEN": self.access_token,
            "Accept-Language": os.getenv("EBAY_LOCALE", "en-GB"),
        }
        logger.info("Calling eBay Trading API operation %s.", call_name)
        try:
            response = await self.client.post(ENDPOINT, headers=headers, content=payload)
        except httpx.RequestError as exc:
            raise TradingAPIError(f"eBay Trading API could not be reached: {exc.__class__.__name__}.") from exc
        if response.status_code >= 400:
            raise TradingAPIError(f"eBay Trading API returned HTTP {response.status_code}.", status_code=response.status_code)
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise TradingAPIError("eBay Trading API returned an invalid XML response.") from exc
        result = TradingResponse(root=root, ack=value(root, "Ack", "Failure") or "Failure", errors=parse_issues(root))
        if not result.successful:
            message = result.blocking_errors[0].message if result.blocking_errors else "eBay rejected the Trading API request."
            raise TradingAPIError(message, result.errors, root=root)
        return result

    async def call(self, call_name: str, request: ET.Element) -> TradingResponse:
        payload = ET.tostring(request, encoding="utf-8", xml_declaration=True)
        try:
            return await self._call_once(call_name, payload)
        except TradingAPIError as exc:
            if exc.status_code != 401 and not _is_expired_token_response(exc.issues):
                raise
        await self._refresh_access_token()
        return await self._call_once(call_name, payload)
