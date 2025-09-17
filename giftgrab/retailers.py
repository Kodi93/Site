"""Retailer adapters used by the aggregation pipeline."""
from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .amazon import AmazonCredentials, AmazonProductClient
from .utils import apply_partner_tag, load_json


logger = logging.getLogger(__name__)


_PLACEHOLDER_TITLE_VALUES = {
    "grab gifts marketplace find",
    "generic pointer",
    "placeholder",
    "placeholder title",
    "untitled",
}

_PLACEHOLDER_TITLE_KEYWORDS = (
    "marketplace find",
    "placeholder",
    "lorem ipsum",
    "generic pointer",
    "coming soon",
    "tbd",
)

_PLACEHOLDER_IMAGE_HOSTS = (
    "source.unsplash.com",
    "images.unsplash.com",
    "picsum.photos",
    "placekitten.com",
)

_PLACEHOLDER_IMAGE_PREFIXES = (
    "/assets/amazon-sitestripe/",
)

_AMAZON_IMAGE_USER_AGENT = (
    "Mozilla/5.0 (compatible; GiftGrabBot/1.0; +https://giftgrab.example)"
)

_AMAZON_META_PATTERNS = [
    re.compile(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+name=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+property=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
]

_AMAZON_ATTRIBUTE_PATTERNS = [
    re.compile(r'data-old-hires=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'"hiRes"\s*:\s*"([^"\']+)"', re.IGNORECASE),
    re.compile(r'"large"\s*:\s*\{\s*"url"\s*:\s*"([^"\']+)"', re.IGNORECASE),
    re.compile(r'"mainUrl"\s*:\s*"([^"\']+)"', re.IGNORECASE),
    re.compile(r'"displayImageUri"\s*:\s*"([^"\']+)"', re.IGNORECASE),
]

_AMAZON_DYNAMIC_IMAGE_PATTERN = re.compile(
    r'data-a-dynamic-image=["\']({.+?})["\']', re.IGNORECASE
)

_AMAZON_DIRECT_IMAGE_PATTERN = re.compile(
    r'https?://[^"\']+m\.media-amazon\.com/images/[^"\']+', re.IGNORECASE
)


def _normalize_sequence(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]


def _looks_like_placeholder_text(value: object) -> bool:
    if value in (None, ""):
        return True
    text = str(value).strip()
    if not text:
        return True
    normalized = text.casefold()
    if normalized in _PLACEHOLDER_TITLE_VALUES:
        return True
    return any(keyword in normalized for keyword in _PLACEHOLDER_TITLE_KEYWORDS)


def _looks_like_placeholder_image(value: object) -> bool:
    if not value:
        return True
    text = str(value).strip()
    if not text:
        return True
    lowered = text.lower()
    try:
        parsed = urlparse(lowered)
    except ValueError:
        parsed = None
    if parsed and parsed.scheme in ("http", "https"):
        host = parsed.netloc
        if any(host.endswith(candidate) or candidate in host for candidate in _PLACEHOLDER_IMAGE_HOSTS):
            return True
    else:
        if any(lowered.startswith(prefix) for prefix in _PLACEHOLDER_IMAGE_PREFIXES):
            return True
    if lowered.endswith(".svg") and "amazon" in lowered:
        return True
    if lowered.startswith("data:image/svg"):
        return True
    return False


def _looks_like_amazon_link(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.netloc.lower()
    if not host:
        return False
    if host == "a.co" or "amzn.to" in host:
        return True
    if "amazon" in host or host.endswith("media-amazon.com") or host.endswith(
        "ssl-images-amazon.com"
    ):
        return True
    return False


def _extract_amazon_image_candidates(body: str, base_url: str) -> list[str]:
    candidates: list[str] = []
    for pattern in _AMAZON_META_PATTERNS:
        for match in pattern.finditer(body):
            candidate = html.unescape(match.group(1).strip())
            if not candidate:
                continue
            candidate = urljoin(base_url, candidate)
            if candidate not in candidates and _looks_like_amazon_link(candidate):
                candidates.append(candidate)
    for pattern in _AMAZON_ATTRIBUTE_PATTERNS:
        for match in pattern.finditer(body):
            candidate = html.unescape(match.group(1).strip())
            if not candidate:
                continue
            candidate = urljoin(base_url, candidate)
            if candidate not in candidates and _looks_like_amazon_link(candidate):
                candidates.append(candidate)
    for match in _AMAZON_DYNAMIC_IMAGE_PATTERN.finditer(body):
        raw = html.unescape(match.group(1))
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            for key in parsed:
                candidate = str(key).strip()
                if not candidate:
                    continue
                candidate = urljoin(base_url, candidate)
                if candidate not in candidates and _looks_like_amazon_link(candidate):
                    candidates.append(candidate)
    for match in _AMAZON_DIRECT_IMAGE_PATTERN.finditer(body):
        candidate = html.unescape(match.group(0).strip())
        if not candidate:
            continue
        candidate = urljoin(base_url, candidate)
        if candidate not in candidates and _looks_like_amazon_link(candidate):
            candidates.append(candidate)
    return candidates


def resolve_amazon_image_url(url: str, *, timeout: int = 15) -> str | None:
    if not url:
        return None
    url = str(url).strip()
    if not url or not _looks_like_amazon_link(url):
        return None
    request = Request(
        url,
        headers={
            "User-Agent": _AMAZON_IMAGE_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            final_url = response.geturl() or url
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type.startswith("image/") and _looks_like_amazon_link(final_url):
                return final_url
            payload = response.read(1_500_000)
    except (HTTPError, URLError, TimeoutError) as exc:
        logger.warning("Unable to resolve Amazon image from %s: %s", url, exc)
        return None
    except Exception as exc:  # pragma: no cover - unexpected network errors
        logger.exception("Unexpected error while resolving Amazon image from %s", url, exc)
        return None
    try:
        body = payload.decode("utf-8", errors="ignore")
    except Exception:
        body = payload.decode("latin-1", errors="ignore")
    for candidate in _extract_amazon_image_candidates(body, final_url):
        if not _looks_like_placeholder_image(candidate):
            return candidate
    return None


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
            image_cache: dict[str, str | None] = {}

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

            def resolve_image_for_entry(entry: dict, normalized: dict) -> tuple[bool, bool]:
                current_image = normalized.get("image")
                if current_image and not _looks_like_placeholder_image(current_image):
                    return False, True
                candidate_images: list[str] = []
                for key in ("image", "image_url"):
                    value = entry.get(key)
                    if isinstance(value, str):
                        text = value.strip()
                        if text:
                            candidate_images.append(text)
                had_placeholder = any(
                    _looks_like_placeholder_image(candidate) for candidate in candidate_images
                )
                candidates = list(dict.fromkeys(candidate_images))
                for key in ("url", "detail_page_url"):
                    value = entry.get(key)
                    if isinstance(value, str):
                        text = value.strip()
                        if text and text not in candidates:
                            candidates.append(text)
                for candidate in candidates:
                    if not _looks_like_amazon_link(candidate):
                        continue
                    if candidate in image_cache:
                        resolved = image_cache[candidate]
                    else:
                        resolved = resolve_amazon_image_url(candidate)
                        image_cache[candidate] = resolved
                    if resolved and not _looks_like_placeholder_image(resolved):
                        normalized["image"] = resolved
                        return had_placeholder, True
                if had_placeholder:
                    normalized["image"] = None
                return had_placeholder, bool(normalized.get("image"))

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
                    "features": _normalize_sequence(entry.get("features")),
                    "rating": entry.get("rating"),
                    "total_reviews": entry.get("total_reviews"),
                    "keywords": _normalize_sequence(entry.get("keywords")),
                    "category_slug": entry.get("category_slug"),
                    "category": entry.get("category"),
                    "brand": entry.get("brand"),
                }
                placeholder_detected, has_image = resolve_image_for_entry(entry, normalized)
                existing = merged.get(normalized["id"])
                if existing is None:
                    if placeholder_detected and not has_image:
                        logger.warning(
                            "Skipping %s because Amazon imagery could not be resolved", product_id
                        )
                        return
                    if _looks_like_placeholder_image(normalized.get("image")):
                        normalized["image"] = None
                    merged[normalized["id"]] = normalized
                    return

                def prefer_longer_string(key: str) -> None:
                    new_value = normalized.get(key)
                    if new_value is None:
                        return
                    new_text = str(new_value).strip()
                    if not new_text:
                        return
                    current_value = existing.get(key)
                    current_text = str(current_value or "").strip()
                    if key == "title" and _looks_like_placeholder_text(current_value):
                        existing[key] = new_text
                        return
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
                new_image = normalized.get("image")
                if new_image:
                    if _looks_like_placeholder_image(new_image):
                        if not existing.get("image") or _looks_like_placeholder_image(
                            existing.get("image")
                        ):
                            existing["image"] = new_image
                    else:
                        existing["image"] = new_image
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
