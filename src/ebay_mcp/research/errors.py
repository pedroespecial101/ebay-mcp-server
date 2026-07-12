from __future__ import annotations


class EbayError(RuntimeError):
    """Safe, user-facing eBay client error."""


class EbayAuthenticationError(EbayError):
    pass


class EbayRateLimitError(EbayError):
    pass


class ImageDownloadError(EbayError):
    pass
