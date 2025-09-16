"""Retailer adapters used by the aggregation pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Protocol

from .amazon import AmazonCredentials, AmazonProductClient
from .utils import apply_partner_tag, load_json


class RetailerAdapter(Protocol):
    """Interface all retailer sources must implement."""

    slug: str
    name: str
    cta_label: str
    homepage: str | None

    def search_items(
        self, *, keywords: Iterable[str], item_count: int
    ) -> List[dict]:
        """Return normalized product dictionaries for the requested keywords."""

    def decorate_url(self, url: str | None) -> str:
        """Return an outbound URL augmented with affiliate tracking if necessary."""


class AmazonRetailerAdapter:
    """Adapter that wraps the Amazon Product Advertising API client."""

    slug = "amazon"
    name = "Amazon"
    cta_label = "Shop on Amazon"
    homepage = "https://www.amazon.com/"

    def __init__(self, credentials: AmazonCredentials) -> None:
        self.credentials = credentials
        self.client = AmazonProductClient(credentials)

    def search_items(
        self, *, keywords: Iterable[str], item_count: int
    ) -> List[dict]:
        raw_items = self.client.search_items(keywords=keywords, item_count=item_count)
        normalized: List[dict] = []
        for item in raw_items:
            asin = item.get("asin") or item.get("ASIN")
            if not asin:
                continue
            normalized.append(
                {
                    "id": asin,
                    "title": item.get("title") or "Untitled Amazon Find",
                    "url": item.get("detail_page_url"),
                    "image": item.get("image_url"),
                    "price": item.get("price"),
                    "features": item.get("features") or [],
                    "rating": item.get("rating"),
                    "total_reviews": item.get("total_reviews"),
                }
            )
        return normalized

    def decorate_url(self, url: str | None) -> str:
        return apply_partner_tag(url, self.credentials.partner_tag)


@dataclass
class StaticRetailerAdapter:
    """Adapter that reads pre-curated items from a JSON file on disk."""

    slug: str
    name: str
    dataset: Path
    cta_label: str = "Shop now"
    homepage: str | None = None

    def __post_init__(self) -> None:
        self._items: List[dict] | None = None

    def _load(self) -> List[dict]:
        if self._items is None:
            raw = load_json(self.dataset, default={}) or {}
            if isinstance(raw, dict):
                if raw.get("name"):
                    self.name = str(raw["name"])
                if not self.homepage and raw.get("homepage"):
                    self.homepage = raw.get("homepage")
                if raw.get("cta_label"):
                    self.cta_label = str(raw["cta_label"])
                items = raw.get("items", [])
            elif isinstance(raw, list):
                items = raw
            else:
                items = []
            normalized: List[dict] = []
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                product_id = entry.get("id") or entry.get("asin")
                if not product_id:
                    continue
                normalized.append(
                    {
                        "id": product_id,
                        "title": entry.get("title", "Curated marketplace find"),
                        "url": entry.get("url"),
                        "image": entry.get("image"),
                        "price": entry.get("price"),
                        "features": entry.get("features") or entry.get("keywords") or [],
                        "rating": entry.get("rating"),
                        "total_reviews": entry.get("total_reviews"),
                        "keywords": entry.get("keywords") or [],
                    }
                )
            self._items = normalized
        return self._items

    def search_items(
        self, *, keywords: Iterable[str], item_count: int
    ) -> List[dict]:
        dataset = self._load()
        needle = [keyword.lower() for keyword in keywords if keyword]
        if not needle:
            return dataset[:item_count]
        matches: List[dict] = []
        for entry in dataset:
            haystack = " ".join(
                [
                    entry.get("title", ""),
                    " ".join(entry.get("features", []) or []),
                    " ".join(entry.get("keywords", []) or []),
                ]
            ).lower()
            if all(fragment in haystack for fragment in needle):
                matches.append(entry)
            if len(matches) >= item_count:
                break
        if len(matches) < item_count:
            remainder = [item for item in dataset if item not in matches]
            matches.extend(remainder[: item_count - len(matches)])
        return matches[:item_count]

    def decorate_url(self, url: str | None) -> str:
        if url:
            return url
        if self.homepage:
            return self.homepage
        return "#"
