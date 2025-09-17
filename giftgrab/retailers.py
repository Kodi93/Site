"""Retailer adapters used by the aggregation pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Protocol, Sequence

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
                    "brand": item.get("brand"),
                }
            )
        return normalized

    def decorate_url(self, url: str | None) -> str:
        return apply_partner_tag(url, self.credentials.partner_tag)


@dataclass
class StaticRetailerAdapter:
    """Adapter that reads pre-curated items from JSON datasets on disk."""

    slug: str
    name: str
    dataset: Path | Sequence[Path]
    cta_label: str = "Shop now"
    homepage: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.dataset, Path):
            self._sources: List[Path] = [self.dataset]
        else:
            self._sources = [Path(source) for source in self.dataset]
        self._items: List[dict] | None = None

    def _load(self) -> List[dict]:
        if self._items is None:
            merged: dict[str, dict] = {}
            seen_paths: set[Path] = set()

            def normalize_sequence(value: object) -> list[str]:
                if isinstance(value, (list, tuple, set)):
                    return [str(item) for item in value if item not in (None, "")]
                if value in (None, ""):
                    return []
                return [str(value)]

            def apply_metadata(payload: object) -> None:
                if not isinstance(payload, dict):
                    return
                name = payload.get("name")
                if name:
                    self.name = str(name)
                homepage = payload.get("homepage")
                if homepage:
                    self.homepage = homepage
                cta_label = payload.get("cta_label")
                if cta_label:
                    self.cta_label = str(cta_label)

            def add_entry(entry: dict) -> None:
                product_id = entry.get("id") or entry.get("asin")
                if not product_id:
                    return
                normalized = {
                    "id": str(product_id),
                    "title": entry.get("title") or "Grab Gifts marketplace find",
                    "url": entry.get("url"),
                    "image": entry.get("image"),
                    "price": entry.get("price"),
                    "features": normalize_sequence(entry.get("features")),
                    "rating": entry.get("rating"),
                    "total_reviews": entry.get("total_reviews"),
                    "keywords": normalize_sequence(entry.get("keywords")),
                    "category_slug": entry.get("category_slug"),
                    "category": entry.get("category"),
                    "brand": entry.get("brand"),
                }
                existing = merged.get(normalized["id"])
                if existing is None:
                    merged[normalized["id"]] = normalized
                    return

                def prefer_longer_string(key: str) -> None:
                    new_value = normalized.get(key)
                    if new_value is None:
                        return
                    new_text = str(new_value).strip()
                    if not new_text:
                        return
                    current_text = str(existing.get(key) or "").strip()
                    if not current_text or len(new_text) > len(current_text):
                        existing[key] = new_text

                def prefer_when_missing(key: str) -> None:
                    new_value = normalized.get(key)
                    if new_value in (None, ""):
                        return
                    if not existing.get(key):
                        existing[key] = new_value

                def merge_sequence(key: str) -> None:
                    combined: list[str] = []
                    for value in (existing.get(key) or []) + (normalized.get(key) or []):
                        if value in (None, ""):
                            continue
                        text = str(value)
                        if text not in combined:
                            combined.append(text)
                    if combined:
                        existing[key] = combined

                prefer_longer_string("title")
                prefer_when_missing("url")
                if normalized.get("image"):
                    existing["image"] = normalized["image"]
                if normalized.get("price"):
                    existing["price"] = normalized["price"]
                for key in ("rating", "total_reviews"):
                    value = normalized.get(key)
                    if value is not None:
                        existing[key] = value
                prefer_when_missing("category_slug")
                prefer_longer_string("category")
                prefer_longer_string("brand")
                merge_sequence("features")
                merge_sequence("keywords")

            def handle_payload(payload: object, source: Path) -> None:
                if isinstance(payload, list):
                    for entry in payload:
                        if isinstance(entry, dict):
                            add_entry(entry)
                    return
                if not isinstance(payload, dict):
                    return
                apply_metadata(payload)

                raw_items = payload.get("items")
                if isinstance(raw_items, dict):
                    raw_items = [raw_items]
                if isinstance(raw_items, list):
                    for entry in raw_items:
                        if isinstance(entry, dict):
                            add_entry(entry)
                elif payload.get("id") or payload.get("asin"):
                    add_entry(payload)

                base = Path(source).parent
                nested: list[Path] = []
                for key in ("items_dir", "items_path"):
                    value = payload.get(key)
                    if not value:
                        continue
                    values = value if isinstance(value, list) else [value]
                    for candidate in values:
                        candidate_path = (base / str(candidate)).resolve()
                        if candidate_path.exists():
                            nested.append(candidate_path)
                for key in ("items_file", "items_files"):
                    value = payload.get(key)
                    if not value:
                        continue
                    values = value if isinstance(value, list) else [value]
                    for candidate in values:
                        candidate_path = (base / str(candidate)).resolve()
                        if candidate_path.exists():
                            nested.append(candidate_path)
                for candidate in nested:
                    walk(candidate)

            def walk(source: Path) -> None:
                path = Path(source)
                resolved = path.resolve()
                if resolved in seen_paths or not resolved.exists():
                    return
                seen_paths.add(resolved)
                if resolved.is_dir():
                    for meta_name in ("meta.json", "metadata.json"):
                        meta_path = resolved / meta_name
                        if meta_path.exists():
                            handle_payload(load_json(meta_path, default={}) or {}, meta_path)
                            break
                    for child in sorted(resolved.iterdir()):
                        if child.name.lower() in {"meta.json", "metadata.json"}:
                            continue
                        walk(child)
                    return
                if resolved.is_file() and resolved.suffix.lower() == ".json":
                    handle_payload(load_json(resolved, default={}) or {}, resolved)

            for source in self._sources:
                walk(source)

            self._items = [merged[key] for key in sorted(merged)]
        return self._items

    def search_items(
        self, *, keywords: Iterable[str], item_count: int
    ) -> List[dict]:
        dataset = self._load()
        needle = [keyword.lower() for keyword in keywords if keyword]
        if not needle:
            if item_count <= 0:
                return list(dataset)
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
        if matches:
            return matches
        if item_count <= 0:
            return list(dataset)
        return dataset[:item_count]

    def decorate_url(self, url: str | None) -> str:
        if url:
            return url
        if self.homepage:
            return self.homepage
        return "#"
