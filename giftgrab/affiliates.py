"""Affiliate helpers for constructing tagged outbound URLs."""
from __future__ import annotations

from urllib.parse import quote_plus

AMAZON_ASSOCIATE_TAG = "kayce25-20"


def amazon_search_link(query: str, host: str = "www.amazon.com") -> str:
    """Return an Amazon search URL decorated with the associate tag."""

    encoded = quote_plus(query.strip())
    host = (host or "www.amazon.com").strip() or "www.amazon.com"
    return f"https://{host}/s?k={encoded}&tag={AMAZON_ASSOCIATE_TAG}"
