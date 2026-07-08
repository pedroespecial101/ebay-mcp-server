from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_auth_config_reads_credentials_file(tmp_path, monkeypatch):
    credentials = tmp_path / "seller.env"
    credentials.write_text(
        "\n".join(
            [
                "EBAY_CLIENT_ID=file-client-id",
                "EBAY_CLIENT_SECRET=file-client-secret",
                "EBAY_RU_NAME=file-runame",
                "EBAY_APP_CONFIGURED_REDIRECT_URI=https://example.test/oauth/callback",
                "EBAY_USER_ACCESS_TOKEN=file-access-token",
                "EBAY_USER_REFRESH_TOKEN=file-refresh-token",
                "EBAY_USER_ID=file-user-id",
                "EBAY_USER_NAME=file-user-name",
            ]
        )
    )

    for key in [
        "EBAY_CLIENT_ID",
        "EBAY_CLIENT_SECRET",
        "EBAY_RU_NAME",
        "EBAY_APP_CONFIGURED_REDIRECT_URI",
        "EBAY_USER_ACCESS_TOKEN",
        "EBAY_USER_REFRESH_TOKEN",
        "EBAY_USER_ID",
        "EBAY_USER_NAME",
    ]:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("EBAY_CREDENTIALS_FILE", str(credentials))

    from models.config.settings import EbayAuthConfig

    config = EbayAuthConfig.from_env()

    assert config.client_id == "file-client-id"
    assert config.client_secret == "file-client-secret"
    assert config.ru_name == "file-runame"
    assert config.redirect_uri == "https://example.test/oauth/callback"
    assert config.user_access_token == "file-access-token"
    assert config.user_refresh_token == "file-refresh-token"
    assert config.user_id == "file-user-id"
    assert config.user_name == "file-user-name"


def test_offer_defaults_are_uk(monkeypatch):
    monkeypatch.setenv("EBAY_PAYMENT_POLICY_ID", "payment-policy")
    monkeypatch.setenv("EBAY_RETURN_POLICY_ID", "return-policy")
    monkeypatch.setenv("EBAY_FULFILLMENT_POLICY_ID", "fulfillment-policy")
    monkeypatch.setenv("EBAY_MERCHANT_LOCATION_KEY", "merchant-location")
    monkeypatch.delenv("EBAY_MARKETPLACE_ID", raising=False)

    module = importlib.import_module("ebay_mcp.config")
    module = importlib.reload(module)

    assert module.ebay_offer_defaults.EBAY_MARKETPLACE_ID == "EBAY_GB"
    assert module.ebay_offer_defaults.EBAY_LOCALE == "en-GB"
    assert module.ebay_offer_defaults.EBAY_CURRENCY == "GBP"
    assert module.ebay_offer_defaults.EBAY_DELIVERY_COUNTRY == "GB"
    assert module.ebay_offer_defaults.EBAY_LISTING_FORMAT == "FIXED_PRICE"
    assert module.ebay_offer_defaults.EBAY_LISTING_DURATION == "GTC"
    assert module.ebay_offer_defaults.EBAY_LISTING_INCLUDE_CATALOG_PRODUCT_DETAILS is True


def test_standard_headers_use_uk_defaults(monkeypatch):
    for key in ["EBAY_MARKETPLACE_ID", "EBAY_LOCALE"]:
        monkeypatch.delenv(key, raising=False)

    from utils.api_utils import get_standard_ebay_headers

    headers = get_standard_ebay_headers("not-a-real-token")

    assert headers["Content-Language"] == "en-GB"
    assert headers["Accept-Language"] == "en-GB"
    assert headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"
