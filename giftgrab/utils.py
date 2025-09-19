"""General utility helpers."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

DEFAULT_AMAZON_ASSOCIATE_TAG = "kayce25-20"


SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Return an SEO-friendly slug for the provided value."""

    value = value.lower().strip()
    value = SLUG_PATTERN.sub("-", value)
    value = value.strip("-")
    return value or "item"


def load_json(path: Path, default: Dict[str, Any] | list | None = None) -> Any:
    """Load a JSON file returning a default value if it does not exist."""

    if not path.exists():
        return default if default is not None else {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, data: Any) -> None:
    """Persist JSON data to disk, ensuring the parent folder exists."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def timestamp() -> str:
    """Return an ISO-8601 timestamp in UTC."""

    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


PRICE_CURRENCY_SYMBOLS: Dict[str, str] = {
    "C$": "CAD",
    "A$": "AUD",
    "£": "GBP",
    "€": "EUR",
    "¥": "JPY",
    "$": "USD",
}


def parse_price_string(price: str | None) -> Tuple[float, str | None] | None:
    """Extract a numeric value and ISO currency code from a price string."""

    if not price:
        return None
    currency = None
    for symbol, code in PRICE_CURRENCY_SYMBOLS.items():
        if symbol in price:
            currency = code
            break
    match = re.search(r"(\d+[\d.,]*)", price)
    if not match:
        return None
    numeric = match.group(1).replace(" ", "")
    if "." in numeric and "," in numeric:
        if numeric.rfind(",") > numeric.rfind("."):
            numeric = numeric.replace(".", "").replace(",", ".")
        else:
            numeric = numeric.replace(",", "")
    elif "," in numeric:
        decimals = numeric.split(",")[-1]
        if len(decimals) in {2, 3}:
            numeric = numeric.replace(",", ".")
        else:
            numeric = numeric.replace(",", "")
    else:
        numeric = numeric.replace(",", "")
    try:
        value = float(numeric)
    except ValueError:
        return None
    return value, currency


def apply_partner_tag(url: str | None, partner_tag: str | None) -> str:
    """Ensure the provided URL contains the Amazon partner tag required by the site."""

    effective_url = url or "https://www.amazon.com/"
    tag = DEFAULT_AMAZON_ASSOCIATE_TAG
    if partner_tag:
        candidate = partner_tag.strip()
        if candidate:
            if candidate.lower() == DEFAULT_AMAZON_ASSOCIATE_TAG:
                tag = candidate
            else:
                logger.debug(
                    "Ignoring affiliate tag %s in favor of required %s", candidate, DEFAULT_AMAZON_ASSOCIATE_TAG
                )
    parsed = urlparse(effective_url)
    query = dict(parse_qsl(parsed.query))
    query["tag"] = tag
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
