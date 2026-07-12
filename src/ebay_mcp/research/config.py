from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True, slots=True)
class Settings:
    client_id: str | None
    client_secret: str | None
    marketplace_id: str = "EBAY_GB"
    locale: str = "en-GB"
    currency: str = "GBP"
    delivery_country: str = "GB"
    delivery_postal_code: str | None = None
    api_base_url: str = "https://api.ebay.com"
    token_safety_margin_seconds: int = 60
    request_timeout_seconds: float = 20.0
    image_max_bytes: int = 10 * 1024 * 1024

    @classmethod
    def from_env(cls) -> Settings:
        file_values: dict[str, str | None] = {}
        credentials_file = os.getenv("EBAY_CREDENTIALS_FILE")
        if credentials_file:
            path = Path(credentials_file).expanduser()
            if path.is_file():
                parsed = dotenv_values(path)
                # Deliberately select only application credentials. Never load
                # seller/user OAuth values from a shared dotenv file.
                file_values = {
                    "EBAY_CLIENT_ID": parsed.get("EBAY_CLIENT_ID"),
                    "EBAY_CLIENT_SECRET": parsed.get("EBAY_CLIENT_SECRET"),
                }

        def value(name: str, default: str | None = None) -> str | None:
            return os.getenv(name) or file_values.get(name) or default

        return cls(
            client_id=value("EBAY_CLIENT_ID"),
            client_secret=value("EBAY_CLIENT_SECRET"),
            marketplace_id=value("EBAY_MARKETPLACE_ID", "EBAY_GB") or "EBAY_GB",
            locale=value("EBAY_LOCALE", "en-GB") or "en-GB",
            currency=value("EBAY_CURRENCY", "GBP") or "GBP",
            delivery_country=value("EBAY_DELIVERY_COUNTRY", "GB") or "GB",
            delivery_postal_code=value("EBAY_DELIVERY_POSTAL_CODE"),
            api_base_url=value("EBAY_API_BASE_URL", "https://api.ebay.com")
            or "https://api.ebay.com",
        )

    def require_credentials(self) -> tuple[str, str]:
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "eBay application credentials are not configured. Set "
                "EBAY_CLIENT_ID and EBAY_CLIENT_SECRET, or EBAY_CREDENTIALS_FILE."
            )
        return self.client_id, self.client_secret
