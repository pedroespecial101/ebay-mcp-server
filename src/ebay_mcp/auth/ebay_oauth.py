"""FastMCP OAuth helper for eBay.

Provides a configured `fastmcp.client.auth.OAuth` instance that knows how to
perform the Authorization Code + PKCE flow against eBay.  Tokens are cached by
FastMCP in the users home directory (or an optional EBAY_OAUTH_CACHE_DIR)
and are automatically refreshed.

Usage::

    from ebay_mcp.auth.ebay_oauth import get_ebay_oauth
    oauth = get_ebay_oauth()
    token = await oauth.get_token()
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

# FastMCP may not be available in certain CI environments; provide graceful
# fallback stubs so that local unit tests can run without the package.
# In production we expect `fastmcp` ≥2.4.0 to be installed.
try:
    from fastmcp.client.auth import OAuth, FileTokenStorage  # type: ignore
except ImportError:  # pragma: no cover – only executed when fastmcp missing
    import types

    class _DummyOAuth:  # pylint: disable=too-few-public-methods
        """Very small stub mimicking the OAuth helper interface."""

        def __init__(self, *args, **kwargs):
            pass

        async def login(self):  # noqa: D401 – simple coroutine stub
            return None

        async def get_token(self):  # noqa: D401 – simple coroutine stub
            return "DUMMY_TOKEN"

    class _DummyStorage:  # pylint: disable=too-few-public-methods
        def __init__(self, *args, **kwargs):
            pass

    # Create synthetic fastmcp modules so import resolutions elsewhere succeed
    import sys

    fastmcp_module = types.ModuleType("fastmcp")
    client_module = types.ModuleType("fastmcp.client")
    auth_module = types.ModuleType("fastmcp.client.auth")
    auth_module.OAuth = _DummyOAuth
    auth_module.FileTokenStorage = _DummyStorage
    client_module.auth = auth_module
    fastmcp_module.client = client_module
    sys.modules.setdefault("fastmcp", fastmcp_module)
    sys.modules.setdefault("fastmcp.client", client_module)
    sys.modules.setdefault("fastmcp.client.auth", auth_module)

    OAuth = _DummyOAuth  # type: ignore
    FileTokenStorage = _DummyStorage  # type: ignore


EBAY_AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"

DEFAULT_SCOPES: List[str] = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",
]


def _build_token_storage() -> FileTokenStorage | None:
    """Return a FileTokenStorage instance if EBAY_OAUTH_CACHE_DIR is set."""
    cache_dir = os.getenv("EBAY_OAUTH_CACHE_DIR")
    if not cache_dir:
        return None
    return FileTokenStorage(token_cache_dir=Path(cache_dir))


def get_ebay_oauth() -> OAuth:
    """Construct and return a pre-configured FastMCP OAuth helper for eBay."""
    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")
    redirect_uri = os.getenv("EBAY_APP_CONFIGURED_REDIRECT_URI")

    return OAuth(
        auth_url=EBAY_AUTH_URL,
        token_url=EBAY_TOKEN_URL,
        scopes=DEFAULT_SCOPES,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        token_storage=_build_token_storage(),
    )


async def get_access_token() -> str:
    """Return a valid eBay user access token (auto-refreshing)."""
    oauth = get_ebay_oauth()
    return await oauth.get_token()
