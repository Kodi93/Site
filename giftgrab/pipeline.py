"""Product ingestion pipeline for the static catalog."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Iterable, List, Sequence
from urllib.parse import urlparse

from . import amazon
from .ebay import EbayCredentials, EbayProductClient
from .models import Product
from .repository import ProductRepository
from .retailers import StaticRetailerAdapter
from .text import clean_text
from .utils import load_json, parse_price_string

LOGGER = logging.getLogger(__name__)

CONFIG_ROUNDUPS = Path("config/roundups.json")
CONFIG_SEARCH_TERMS = Path("config/search_terms.json")
DEFAULT_SEARCH_TERMS = ["gift ideas", "kitchen gadgets", "desk accessories"]
DEFAULT_EBAY_RESULTS_PER_QUERY = 100
DEFAULT_EBAY_TARGET_ITEMS = 2400
CURATED_DIR = Path("data/retailers")

_PLACEHOLDER_IMAGE_PREFIXES = ("/assets/amazon-sitestripe/",)
_PLACEHOLDER_IMAGE_HOSTS = {
    "images.unsplash.com",
    "source.unsplash.com",
    "picsum.photos",
    "placekitten.com",
}


def _looks_like_placeholder_image(value: object) -> bool:
    if not value:
        return True
    text = str(value).strip()
    if not text:
        return True
    lowered = text.lower()
    if lowered.startswith("data:image/svg"):
        return True
    for prefix in _PLACEHOLDER_IMAGE_PREFIXES:
        if lowered.startswith(prefix):
            return True
    if lowered.endswith(".svg") and "amazon" in lowered:
        return True
    if "placeholder" in lowered:
        return True
    if lowered.startswith("http://") or lowered.startswith("https://"):
        try:
            host = urlparse(lowered).netloc
        except ValueError:
            return False
        if host in _PLACEHOLDER_IMAGE_HOSTS:
            return True
    return False


def _normalize_sentence(text: object) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    cleaned = clean_text(raw)
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."
    first = cleaned[0]
    if first.islower():
        cleaned = f"{first.upper()}{cleaned[1:]}"
    return cleaned


def _clean_feature_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    # Remove leading bullet characters and decorative brackets from Amazon exports.
    text = re.sub(r"^[\s\u2022•\-–—]+", "", text)
    if "】" in text:
        text = text.split("】", 1)[1].strip()
    text = text.strip("\"'“”[](){} ")
    normalized = _normalize_sentence(text)
    return normalized


def _feature_sentences(payload: dict) -> List[str]:
    features = payload.get("features")
    sentences: List[str] = []
    if isinstance(features, list):
        seen: set[str] = set()
        for entry in features:
            normalized = _clean_feature_text(entry)
            if not normalized or normalized in seen:
                continue
            sentences.append(normalized)
            seen.add(normalized)
            if len(sentences) >= 3:
                break
    return sentences


def _meta_sentences(*, price_text: str | None, rating: float | None, rating_count: int | None) -> List[str]:
    sentences: List[str] = []
    if rating is not None and rating_count:
        sentences.append(
            _normalize_sentence(
                f"Rated {rating:.1f}/5 by {rating_count:,} verified shoppers"
            )
        )
    elif rating is not None:
        sentences.append(_normalize_sentence(f"Rated {rating:.1f}/5 overall"))
    elif rating_count:
        sentences.append(
            _normalize_sentence(f"Backed by {rating_count:,} shopper reviews")
        )
    if price_text:
        sentences.append(
            _normalize_sentence(
                f"Check the listing for today's price (about {price_text})"
            )
        )
    return [sentence for sentence in sentences if sentence]


def _build_description(data: dict, *, title: str, price_text: str | None, rating: float | None, rating_count: int | None) -> str | None:
    sentences: List[str] = []
    raw_description = data.get("description")
    normalized_description = _normalize_sentence(raw_description)
    if normalized_description:
        sentences.append(normalized_description)
    for sentence in _feature_sentences(data):
        if sentence not in sentences:
            sentences.append(sentence)
        if len(sentences) >= 3:
            break
    if len(sentences) < 3:
        for sentence in _meta_sentences(
            price_text=price_text, rating=rating, rating_count=rating_count
        ):
            if sentence not in sentences:
                sentences.append(sentence)
            if len(sentences) >= 4:
                break
    if not sentences:
        fallback = _normalize_sentence(
            f"{title} is a ready-to-gift pick with practical details"
        )
        if fallback:
            sentences.append(fallback)
    description = clean_text(" ".join(sentences))
    return description or None


class GiftPipeline:
    def __init__(self, repository: ProductRepository | None = None) -> None:
        self.repository = repository or ProductRepository()
        self._ebay_client: EbayProductClient | None = None
        self._ebay_credentials_warning_logged = False

    def _load_ebay_credentials(self) -> EbayCredentials | None:
        client_id = (os.getenv("EBAY_CLIENT_ID") or "").strip()
        client_secret = (os.getenv("EBAY_CLIENT_SECRET") or "").strip()
        if not client_id or not client_secret:
            if not self._ebay_credentials_warning_logged:
                LOGGER.warning("Missing eBay credentials; Browse API disabled")
                self._ebay_credentials_warning_logged = True
            return None
        campaign = (os.getenv("EBAY_CAMPAIGN_ID") or "").strip() or None
        marketplace = (os.getenv("EBAY_MARKETPLACE_ID") or "").strip() or None
        return EbayCredentials(
            client_id=client_id,
            client_secret=client_secret,
            affiliate_campaign_id=campaign,
            marketplace_id=marketplace,
        )

    def _ensure_ebay_client(self) -> EbayProductClient | None:
        if self._ebay_client is not None:
            return self._ebay_client
        credentials = self._load_ebay_credentials()
        if not credentials:
            return None
        self._ebay_client = EbayProductClient(credentials)
        return self._ebay_client

    # ------------------------------------------------------------------
    # Data discovery

    def _load_search_terms(self) -> List[str]:
        seen: set[str] = set()
        terms: List[str] = []

        def _add_term(value: object) -> None:
            if not isinstance(value, str):
                return
            text = value.strip()
            if not text:
                return
            key = text.lower()
            if key in seen:
                return
            seen.add(key)
            terms.append(text)

        if CONFIG_SEARCH_TERMS.exists():
            payload = load_json(CONFIG_SEARCH_TERMS, default=[]) or []
            if isinstance(payload, list):
                for entry in payload:
                    if isinstance(entry, dict):
                        topic = entry.get("topic") or entry.get("query")
                        _add_term(topic if isinstance(topic, str) else None)
                    else:
                        _add_term(entry)

        if CONFIG_ROUNDUPS.exists():
            payload = load_json(CONFIG_ROUNDUPS, default=[]) or []
            if isinstance(payload, list):
                for entry in payload:
                    if isinstance(entry, dict):
                        topic = entry.get("topic")
                        _add_term(topic)

        if not terms:
            for fallback in DEFAULT_SEARCH_TERMS:
                _add_term(fallback)

        return terms

    def _ebay_items_per_query(self) -> int:
        configured = os.getenv("EBAY_ITEMS_PER_QUERY", "").strip()
        try:
            value = int(configured) if configured else 0
        except ValueError:
            value = 0
        if value <= 0:
            return DEFAULT_EBAY_RESULTS_PER_QUERY
        return max(1, min(value, 100))

    def _ebay_target_items(self) -> int:
        configured = os.getenv("EBAY_TARGET_ITEMS", "").strip()
        try:
            value = int(configured) if configured else 0
        except ValueError:
            value = 0
        if value <= 0:
            return DEFAULT_EBAY_TARGET_ITEMS
        return max(100, value)

    def _load_curated_products(self) -> List[Product]:
        products: list[Product] = []
        if not CURATED_DIR.exists():
            return products
        sources: list[Path] = []
        for entry in sorted(CURATED_DIR.iterdir()):
            name = entry.name.lower()
            if any(keyword in name for keyword in ("ebay", "amazon")):
                continue
            sources.append(entry)
        if not sources:
            return products
        adapter = StaticRetailerAdapter(
            slug="curated",
            name="Curated Picks",
            dataset=sources,
        )
        for entry in adapter.search_items(keywords=[], item_count=0):
            if not isinstance(entry, dict):
                continue
            product = self._build_product(entry, source="curated")
            if product:
                products.append(product)
        return products

    # ------------------------------------------------------------------
    # External API fetches

    def _fetch_ebay(self, queries: Sequence[str]) -> List[Product]:
        client = self._ensure_ebay_client()
        if client is None:
            return []
        results: List[Product] = []
        per_query = self._ebay_items_per_query()
        target = self._ebay_target_items()
        for query in queries:
            items = client.search_items(keywords=[query], item_count=per_query)
            for item in items:
                product = self._build_product(item, source="ebay")
                if product:
                    results.append(product)
            if target and len(results) >= target:
                LOGGER.info(
                    "Reached eBay target of %s items after query '%s'", target, query
                )
                break
        return results

    def _fetch_amazon(self, queries: Sequence[str]) -> List[Product]:
        results: List[Product] = []
        for query in queries:
            for item in amazon.search([query], limit=10):
                product = self._build_product(item, source="amazon")
                if product:
                    results.append(product)
        return results

    # ------------------------------------------------------------------
    # Helpers

    def _build_product(self, data: dict, *, source: str) -> Product | None:
        try:
            raw_id = data["id"]
            title = data["title"]
            url = data["url"]
        except KeyError:
            return None
        price_value = data.get("price")
        price_text = data.get("price_text") or data.get("price_display")
        currency = data.get("currency")
        if isinstance(price_value, str) and price_value.strip() and not price_text:
            price_text = price_value
        numeric_price = None
        if isinstance(price_value, (int, float)):
            numeric_price = float(price_value)
        elif isinstance(price_value, str):
            parsed = parse_price_string(price_value)
            if parsed:
                numeric_price, parsed_currency = parsed
                currency = currency or parsed_currency
        if numeric_price is None and isinstance(price_text, str):
            parsed = parse_price_string(price_text)
            if parsed:
                numeric_price, parsed_currency = parsed
                currency = currency or parsed_currency
        if isinstance(price_text, (int, float)):
            price_text = f"${float(price_text):,.2f}"
        brand = data.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name") or brand.get("value")
        category = data.get("category") or data.get("category_slug")
        if isinstance(category, str):
            category = category.replace("-", " ").title()
        rating_value = data.get("rating")
        if isinstance(rating_value, str):
            try:
                rating_value = float(rating_value)
            except ValueError:
                rating_value = None
        elif not isinstance(rating_value, (int, float)):
            rating_value = None
        rating_numeric = (
            float(rating_value) if isinstance(rating_value, (int, float)) else None
        )
        review_count = data.get("rating_count") or data.get("total_reviews")
        if isinstance(review_count, str):
            try:
                review_count = int(review_count.replace(",", ""))
            except ValueError:
                review_count = None
        elif isinstance(review_count, float):
            review_count = int(review_count)
        elif not isinstance(review_count, int):
            review_count = None
        image = data.get("image")
        if _looks_like_placeholder_image(image):
            image = None
        description_text = _build_description(
            data,
            title=str(title),
            price_text=str(price_text) if price_text else None,
            rating=rating_numeric,
            rating_count=review_count,
        )
        return Product(
            id=str(raw_id),
            title=str(title),
            url=str(url),
            image=image,
            price=numeric_price,
            price_text=str(price_text) if price_text else None,
            currency=str(currency) if currency else None,
            brand=str(brand) if brand else None,
            category=str(category) if category else None,
            rating=rating_numeric,
            rating_count=review_count,
            source=source,
            description=description_text,
        )

    def _dedupe(self, products: Iterable[Product]) -> List[Product]:
        seen: dict[str, Product] = {}
        for product in products:
            if product.id not in seen:
                seen[product.id] = product
                continue
            existing = seen[product.id]
            if product.updated_at > existing.updated_at:
                seen[product.id] = product
        return list(seen.values())

    # ------------------------------------------------------------------

    def run(self) -> List[Product]:
        queries = self._load_search_terms()
        curated = self._load_curated_products()
        LOGGER.info("Loaded %s curated products", len(curated))
        LOGGER.info("Loaded %s search queries", len(queries))
        ebay_results = self._fetch_ebay(queries)
        LOGGER.info("Fetched %s items from eBay", len(ebay_results))
        amazon_results = self._fetch_amazon(queries)
        LOGGER.info("Fetched %s items from Amazon", len(amazon_results))
        combined = self._dedupe(curated + ebay_results + amazon_results)
        LOGGER.info("Ingesting %s total items", len(combined))
        stored = self.repository.ingest(combined)
        LOGGER.info("Repository now tracks %s items", len(stored))
        return stored
