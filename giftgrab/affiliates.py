"""Affiliate helper utilities for outbound product links."""
from __future__ import annotations

import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .utils import DEFAULT_AMAZON_ASSOCIATE_TAG

_REL = "sponsored nofollow noopener"


def affiliate_rel() -> str:
    """Return the rel attribute applied to affiliate anchors."""

    return _REL


def _apply_query_param(url: str, **params: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({key: value for key, value in params.items() if value})
    new_query = urlencode(query)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


def ensure_amazon_tag(url: str) -> str:
    """Ensure an Amazon URL carries the correct associate tag."""

    tag = os.getenv("AMAZON_ASSOCIATE_TAG", DEFAULT_AMAZON_ASSOCIATE_TAG).strip() or DEFAULT_AMAZON_ASSOCIATE_TAG
    return _apply_query_param(url, tag=tag)


def ensure_ebay_campaign(url: str) -> str:
    """Append the eBay campaign identifier when provided."""

    campaign = (os.getenv("EBAY_CAMPAIGN_ID") or "").strip()
    if not campaign:
        return url
    return _apply_query_param(url, campid=campaign)


def prepare_affiliate_url(url: str, source: str | None = None) -> str:
    """Return the affiliate-safe URL for the given retailer source."""

    normalized = url or ""
    source_value = (source or "").lower()
    host = urlparse(normalized).netloc.lower()
    if source_value == "amazon" or "amazon." in host or host.startswith("amzn.") or host.endswith("amzn.to"):
        return ensure_amazon_tag(normalized)
    if source_value == "ebay" or "ebay." in host:
        return ensure_ebay_campaign(normalized)
    return normalized
