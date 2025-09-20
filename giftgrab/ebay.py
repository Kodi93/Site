"""Minimal eBay Browse API client built on the Python standard library."""
from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)


@dataclass
class EbayCredentials:
    client_id: str
    client_secret: str
    affiliate_campaign_id: Optional[str] = None


class EbayProductClient:
    """Minimal wrapper around the Browse API for retailer adapters."""

    def __init__(self, credentials: EbayCredentials) -> None:
        self.credentials = credentials
        self._token: Optional[str] = None

    def _ensure_token(self) -> Optional[str]:
        if self._token:
            return self._token
        token = get_token(self.credentials.client_id, self.credentials.client_secret)
        self._token = token
        return token

    def search_items(self, *, keywords: Iterable[str], item_count: int) -> List[dict]:
        token = self._ensure_token()
        if not token:
            return []
        query = " ".join(str(keyword) for keyword in keywords if keyword).strip()
        if not query:
            query = "gifts"
        return search(query, limit=item_count, token=token)

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def get_token(client_id: Optional[str] = None, client_secret: Optional[str] = None) -> Optional[str]:
    """Request an OAuth access token using the client-credentials flow."""

    cid = (client_id or os.getenv("EBAY_CLIENT_ID") or "").strip()
    secret = (client_secret or os.getenv("EBAY_CLIENT_SECRET") or "").strip()
    if not cid or not secret:
        LOGGER.warning("Missing eBay credentials; Browse API disabled")
        return None
    payload = urlencode({"grant_type": "client_credentials", "scope": SCOPE}).encode("ascii")
    request = Request(
        TOKEN_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {_basic_auth_header(cid, secret)}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        LOGGER.error("eBay OAuth error %s: %s", exc.code, detail)
        return None
    except URLError as exc:
        LOGGER.error("eBay OAuth network error: %s", exc)
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        LOGGER.error("Unable to decode eBay OAuth response: %s", body[:200])
        return None
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        LOGGER.error("eBay OAuth response missing access_token")
        return None
    return token


def _format_price(value: object, currency: object) -> tuple[Optional[float], Optional[str], Optional[str]]:
    if value in (None, ""):
        return None, None, None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None, None, None
    currency_code = str(currency).upper() if isinstance(currency, str) else "USD"
    display = f"${numeric:,.2f}" if currency_code == "USD" else f"{numeric:,.2f} {currency_code}"
    return numeric, currency_code, display


def _extract_category(path: object) -> Optional[str]:
    if isinstance(path, str):
        parts = [segment.strip() for segment in path.split(">") if segment.strip()]
        if parts:
            return parts[-1]
    return None


def _parse_item(item: object) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    item_id = item.get("itemId")
    if not item_id:
        return None
    item_id = str(item_id)
    title = str(item.get("title") or item_id)
    url = str(item.get("itemWebUrl") or "https://www.ebay.com/")
    image_info = item.get("image")
    image_url = None
    if isinstance(image_info, dict):
        image_url = image_info.get("imageUrl")
    if not isinstance(image_url, str):
        image_url = None
    price_info = item.get("price") if isinstance(item.get("price"), dict) else None
    price = None
    currency = None
    display = None
    if isinstance(price_info, dict):
        price, currency, display = _format_price(
            price_info.get("value"), price_info.get("currency")
        )
    brand = item.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("value")
    if isinstance(brand, (list, tuple)) and brand:
        brand = brand[0]
    brand_text = str(brand).strip() if isinstance(brand, str) else None
    category = _extract_category(item.get("categoryPath"))
    return {
        "id": item_id,
        "title": title,
        "url": url,
        "image": image_url,
        "price": price,
        "price_text": display,
        "currency": currency or "USD",
        "brand": brand_text,
        "category": category,
        "rating": None,
        "rating_count": None,
        "source": "ebay",
    }


def search(query: str, limit: int = 30, token: Optional[str] = None) -> List[dict]:
    """Search the Browse API and return normalized product dictionaries."""

    auth_token = token or get_token()
    if not auth_token:
        return []
    params = {"q": query or "gifts", "limit": max(1, min(int(limit or 0) or 1, 100))}
    request = Request(
        f"{SEARCH_URL}?{urlencode(params)}",
        headers={"Authorization": f"Bearer {auth_token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        LOGGER.error("eBay search error %s: %s", exc.code, detail)
        return []
    except URLError as exc:
        LOGGER.error("eBay search network error: %s", exc)
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        LOGGER.error("Unable to decode eBay search response: %s", payload[:200])
        return []
    items = data.get("itemSummaries")
    results: List[dict] = []
    if isinstance(items, list):
        for entry in items:
            parsed = _parse_item(entry)
            if parsed:
                results.append(parsed)
    return results
