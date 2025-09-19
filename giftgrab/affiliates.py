"""Affiliate helpers for constructing tagged outbound URLs."""
from __future__ import annotations

from urllib.parse import quote_plus

from .utils import DEFAULT_AMAZON_ASSOCIATE_TAG

AMAZON_ASSOCIATE_TAG = DEFAULT_AMAZON_ASSOCIATE_TAG


def amazon_search_link(query: str, host: str = "www.amazon.com") -> str:
    """Return an Amazon search URL decorated with the associate tag."""

    encoded = quote_plus(query.strip())
    host = (host or "www.amazon.com").strip() or "www.amazon.com"
    return f"https://{host}/s?k={encoded}&tag={AMAZON_ASSOCIATE_TAG}"
