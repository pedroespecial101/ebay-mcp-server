"""Tests for FastMCP OAuth integration.

These tests mock the underlying OAuth helper so they can run in CI / offline
without requiring a real browser flow.
"""
import pytest
import os, sys
from unittest.mock import AsyncMock, patch

# Ensure 'src' directory is on PYTHONPATH so we can import ebay_service
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, 'src')
sys.path.append(src_dir)

# Import the helper we want to test
from ebay_service import get_ebay_access_token


@pytest.mark.asyncio
async def test_get_ebay_access_token_returns_token():
    """get_ebay_access_token should return whatever the OAuth helper returns."""
    with patch("ebay_mcp.auth.ebay_oauth.get_access_token", new_callable=AsyncMock) as mock_get_token:
        mock_get_token.return_value = "FAKE_TOKEN_123"
        token = await get_ebay_access_token()
        assert token == "FAKE_TOKEN_123"
        mock_get_token.assert_awaited_once()
