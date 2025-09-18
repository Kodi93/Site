#!/usr/bin/env python3
"""Refresh price, rating, and review counts for SiteStripe records."""
from __future__ import annotations

import json
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

ITEMS_DIR = Path(__file__).resolve().parents[1] / "data" / "retailers" / "amazon-sitestripe" / "items"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15A372 Safari/604.1"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}
PRICE_FALLBACKS = (
    re.compile(r"id=\"sns-base-price\"[^$]*\$([0-9,.]+)", re.S),
    re.compile(r"class=\"a-offscreen\">\s*\$([0-9,.]+)", re.S),
)
RATING_RE = re.compile(r"a-icon-alt\">([0-9.]+) out of 5 stars<")
REVIEWS_RE = re.compile(r"aria-label=\"([0-9,.]+) (?:Reviews|ratings)\"")
REVIEW_DIGITS_RE = re.compile(r"([0-9][0-9,]*)")
ASIN_RE = re.compile(r"/([A-Z0-9]{10})(?:[/?]|$)")


@dataclass
class ListingMetrics:
    price: Optional[str]
    rating: Optional[float]
    reviews: Optional[int]


class MetricsError(RuntimeError):
    """Raised when a product page cannot be parsed."""


class MetricsFetcher:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._asin_cache: dict[str, str] = {}

    def resolve_asin(self, url: str) -> str:
        if url in self._asin_cache:
            return self._asin_cache[url]
        try:
            response = self._session.head(
                url,
                allow_redirects=True,
                headers=HEADERS,
                timeout=20,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise MetricsError(f"Failed to resolve ASIN for {url}: {exc}") from exc
        match = ASIN_RE.search(response.url)
        if not match:
            raise MetricsError(f"Could not locate ASIN in redirect chain for {url}")
        asin = match.group(1)
        self._asin_cache[url] = asin
        return asin

    def fetch_listing(self, asin: str) -> str:
        for attempt in range(5):
            try:
                response = self._session.get(
                    f"https://www.amazon.com/gp/aw/d/{asin}",
                    headers=HEADERS,
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:  # pragma: no cover - network failure
                if attempt == 4:
                    raise MetricsError(f"Failed to fetch listing for {asin}: {exc}") from exc
                time.sleep(2.0)
                continue
            if "automated access" in response.text.lower():
                # Amazon occasionally serves a bot challenge; wait and retry.
                if attempt == 4:
                    raise MetricsError(f"Bot challenge detected for {asin}")
                time.sleep(4.0)
                continue
            return response.text
        raise MetricsError(f"Unable to load listing for {asin}")

    def parse_metrics(self, html: str) -> ListingMetrics:
        price = self._extract_price(html)
        rating = self._extract_rating(html)
        reviews = self._extract_reviews(html)
        return ListingMetrics(price=price, rating=rating, reviews=reviews)

    def _extract_price(self, html: str) -> Optional[str]:
        idx = html.find("priceToPay")
        if idx != -1:
            window = html[idx: idx + 400]
            whole_match = re.search(r"a-price-whole\">([0-9,]+)", window)
            if whole_match:
                fraction_match = re.search(r"a-price-fraction\">([0-9]{2})", window)
                fraction = fraction_match.group(1) if fraction_match else "00"
                value = f"{whole_match.group(1).replace(',', '')}.{fraction}"
                return f"${float(value):.2f}"
        for pattern in PRICE_FALLBACKS:
            fallback_match = pattern.search(html)
            if fallback_match:
                raw = fallback_match.group(1).replace(",", "")
                try:
                    return f"${float(raw):.2f}"
                except ValueError:  # pragma: no cover - unexpected formatting
                    continue
        return None

    def _extract_rating(self, html: str) -> Optional[float]:
        rating_match = RATING_RE.search(html)
        if rating_match:
            try:
                return round(float(rating_match.group(1)), 1)
            except ValueError:  # pragma: no cover
                return None
        return None

    def _extract_reviews(self, html: str) -> Optional[int]:
        index = html.find("acrCustomerReviewLink")
        snippet = html[index: index + 300] if index != -1 else html
        reviews_match = REVIEWS_RE.search(snippet)
        if not reviews_match:
            reviews_match = REVIEWS_RE.search(html)
        if reviews_match:
            digits_match = REVIEW_DIGITS_RE.search(reviews_match.group(1))
            if digits_match:
                try:
                    return int(digits_match.group(1).replace(",", ""))
                except ValueError:  # pragma: no cover
                    return None
        return None


def update_file(path: Path, fetcher: MetricsFetcher) -> bool:
    data = json.loads(path.read_text())
    asin = fetcher.resolve_asin(data["url"])
    html = fetcher.fetch_listing(asin)
    metrics = fetcher.parse_metrics(html)
    updated = False
    if metrics.price and data.get("price") != metrics.price:
        data["price"] = metrics.price
        updated = True
    if metrics.rating and not math.isclose(data.get("rating", 0.0), metrics.rating):
        data["rating"] = metrics.rating
        updated = True
    if metrics.reviews is not None and data.get("total_reviews") != metrics.reviews:
        data["total_reviews"] = metrics.reviews
        updated = True
    if updated:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return updated


def main() -> int:
    fetcher = MetricsFetcher()
    paths = sorted(p for p in ITEMS_DIR.glob("*.json"))
    touched = 0
    for idx, path in enumerate(paths, start=1):
        try:
            if update_file(path, fetcher):
                touched += 1
                status = "updated"
            else:
                status = "unchanged"
            print(f"[{idx}/{len(paths)}] {path.name}: {status}")
        except MetricsError as exc:
            print(f"[{idx}/{len(paths)}] {path.name}: ERROR {exc}", file=sys.stderr)
        time.sleep(1.5)
    print(f"Updated {touched} listings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
