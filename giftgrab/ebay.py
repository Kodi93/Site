"""Minimal eBay Browse API client used by the aggregation pipeline."""
from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import Iterable, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .utils import slugify

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
_DEFAULT_SCOPES = (
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/buy.browse",
)
_CURRENCY_SYMBOLS = {
    "USD": "$",
    "CAD": "C$",
    "AUD": "A$",
    "NZD": "NZ$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}


@dataclass
class EbayCredentials:
    """Credentials required for authenticating with the eBay APIs."""

    client_id: str
    client_secret: str
    developer_id: str
    affiliate_campaign_id: str | None = None


class EbayProductClient:
    """Client that fetches listings from the eBay Browse API."""

    def __init__(self, credentials: EbayCredentials) -> None:
        self.credentials = credentials
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

    def _build_token_request(self) -> Request:
        payload = urlencode(
            {
                "grant_type": "client_credentials",
                "scope": " ".join(_DEFAULT_SCOPES),
            }
        ).encode("ascii")
        auth_header = base64.b64encode(
            f"{self.credentials.client_id}:{self.credentials.client_secret}".encode(
                "utf-8"
            )
        ).decode("ascii")
        request = Request(
            _TOKEN_URL,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {auth_header}",
                "Accept": "application/json",
                "X-EBAY-C-DEV-ID": self.credentials.developer_id,
            },
            method="POST",
        )
        return request

    def _ensure_token(self) -> str | None:
        now = time.time()
        if self._access_token and now < (self._token_expiry - 60):
            return self._access_token
        request = self._build_token_request()
        try:
            with urlopen(request, timeout=15) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            logger.error(
                "eBay OAuth error %s: %s", exc.code, exc.read().decode("utf-8", "ignore")
            )
            return None
        except URLError as exc:
            logger.error("eBay OAuth request failed: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover - unexpected network issues
            logger.exception("Unexpected eBay OAuth error: %s", exc)
            return None

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Unable to decode eBay OAuth response: %s", payload[:200])
            return None
        token = data.get("access_token")
        expires_in = data.get("expires_in", 0)
        if not token:
            logger.error("eBay OAuth response missing access token: %s", payload[:200])
            return None
        if isinstance(expires_in, (int, float)):
            self._token_expiry = now + float(expires_in)
        else:
            self._token_expiry = now + 3600
        self._access_token = str(token)
        return self._access_token

    @staticmethod
    def _format_price(price_info: object) -> str | None:
        if not isinstance(price_info, dict):
            return None
        value = price_info.get("value")
        currency = price_info.get("currency")
        if value in (None, ""):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            value_text = str(value).strip()
            if not value_text:
                return None
            return f"{value_text} {currency}".strip()
        formatted = f"{numeric:,.2f}"
        if currency:
            symbol = _CURRENCY_SYMBOLS.get(str(currency).upper())
            if symbol:
                return f"{symbol}{formatted}"
            return f"{formatted} {currency}"
        return formatted

    @staticmethod
    def _extract_image(item: dict) -> str | None:
        image = item.get("image")
        if isinstance(image, dict):
            candidate = image.get("imageUrl")
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        additional = item.get("additionalImages")
        if isinstance(additional, list):
            for entry in additional:
                if isinstance(entry, dict):
                    candidate = entry.get("imageUrl")
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate
        return None

    @staticmethod
    def _extract_features(item: dict) -> list[str]:
        features: list[str] = []
        aspects = item.get("localizedAspects")
        if isinstance(aspects, list):
            for aspect in aspects:
                if not isinstance(aspect, dict):
                    continue
                name = str(aspect.get("name") or "").strip()
                value = str(aspect.get("value") or "").strip()
                if name and value:
                    features.append(f"{name}: {value}")
                elif value:
                    features.append(value)
        short_description = item.get("shortDescription")
        if isinstance(short_description, str):
            for line in short_description.splitlines():
                text = line.strip()
                if text:
                    features.append(text)
        if len(features) > 10:
            features = features[:10]
        return features

    @staticmethod
    def _extract_keywords(item: dict, brand: str | None) -> list[str]:
        keywords: list[str] = []
        category_path = item.get("categoryPath")
        if isinstance(category_path, str):
            for part in category_path.split(">"):
                text = part.strip()
                if text:
                    keywords.append(text)
        categories = item.get("categories")
        if isinstance(categories, list):
            for category in categories:
                if isinstance(category, dict):
                    name = category.get("categoryName")
                    if isinstance(name, str) and name.strip():
                        keywords.append(name.strip())
        if brand:
            keywords.append(brand)
        return list(dict.fromkeys(keyword for keyword in keywords if keyword))

    def _normalize_item(self, item: object) -> dict | None:
        if not isinstance(item, dict):
            return None
        item_id = item.get("itemId") or item.get("legacyItemId")
        if not item_id:
            return None
        item_id = str(item_id)
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            title = f"eBay listing {item_id}"
        url = item.get("itemWebUrl")
        if isinstance(url, str) and url.strip():
            url_value = url
        else:
            url_value = "https://www.ebay.com/"
        image = self._extract_image(item)
        price_info = item.get("price") or {}
        if not isinstance(price_info, dict) or not price_info.get("value"):
            marketing_price = item.get("marketingPrice")
            if isinstance(marketing_price, dict):
                discounted = marketing_price.get("discountedPrice")
                if isinstance(discounted, dict):
                    price_info = discounted
        price = self._format_price(price_info)
        features = self._extract_features(item)
        rating_value = None
        total_reviews = None
        review_info = item.get("reviewRating")
        if isinstance(review_info, dict):
            average = review_info.get("averageRating")
            try:
                rating_value = float(average)
            except (TypeError, ValueError):
                rating_value = None
            count = review_info.get("ratingCount") or review_info.get("reviewCount")
            try:
                total_reviews = int(count)
            except (TypeError, ValueError):
                try:
                    total_reviews = int(float(count))
                except (TypeError, ValueError):
                    total_reviews = None
        brand = item.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("value")
        if isinstance(brand, (list, tuple)):
            brand = brand[0] if brand else None
        brand_value = str(brand).strip() if isinstance(brand, str) else None
        keywords = self._extract_keywords(item, brand_value)
        category_slug = None
        category_path = item.get("categoryPath")
        if isinstance(category_path, str):
            if ">" in category_path:
                last = category_path.split(">")[-1].strip()
            else:
                last = category_path.strip()
            if last:
                category_slug = slugify(last)
        normalized: dict = {
            "id": item_id,
            "title": title,
            "url": url_value,
            "image": image,
            "price": price,
            "features": features,
            "rating": rating_value,
            "total_reviews": total_reviews,
            "brand": brand_value,
            "keywords": keywords,
        }
        if category_slug:
            normalized["category_slug"] = category_slug
        return normalized

    def search_items(self, *, keywords: Iterable[str], item_count: int) -> List[dict]:
        token = self._ensure_token()
        if not token:
            return []
        query = " ".join(str(keyword) for keyword in keywords if keyword)
        params = {
            "q": query or "gift ideas",
            "limit": max(1, min(int(item_count or 0) or 1, 100)),
        }
        request = Request(
            f"{_SEARCH_URL}?{urlencode(params)}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "X-EBAY-C-DEV-ID": self.credentials.developer_id,
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            logger.error(
                "eBay search error %s: %s", exc.code, exc.read().decode("utf-8", "ignore")
            )
            return []
        except URLError as exc:
            logger.error("eBay search request failed: %s", exc)
            return []
        except Exception as exc:  # pragma: no cover - unexpected network issues
            logger.exception("Unexpected eBay search error: %s", exc)
            return []
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Unable to decode eBay search response: %s", payload[:200])
            return []
        items = data.get("itemSummaries")
        normalized: List[dict] = []
        if isinstance(items, list):
            for item in items:
                normalized_item = self._normalize_item(item)
                if normalized_item:
                    normalized.append(normalized_item)
        return normalized
