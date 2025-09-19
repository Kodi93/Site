"""Product ingestion pipeline for the static catalog."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, List, Sequence

from . import amazon, ebay
from .models import Product
from .repository import ProductRepository
from .utils import load_json, parse_price_string

LOGGER = logging.getLogger(__name__)

CONFIG_ROUNDUPS = Path("config/roundups.json")
CURATED_DIR = Path("data/retailers")


class GiftPipeline:
    def __init__(self, repository: ProductRepository | None = None) -> None:
        self.repository = repository or ProductRepository()

    # ------------------------------------------------------------------
    # Data discovery

    def _load_search_terms(self) -> List[str]:
        if not CONFIG_ROUNDUPS.exists():
            return ["gift ideas", "kitchen gadgets", "desk accessories"]
        payload = load_json(CONFIG_ROUNDUPS, default=[]) or []
        terms: List[str] = []
        for entry in payload:
            if isinstance(entry, dict):
                topic = entry.get("topic")
                if isinstance(topic, str) and topic.strip():
                    terms.append(topic.strip())
        return terms or ["gift ideas"]

    def _load_curated_products(self) -> List[Product]:
        products: list[Product] = []
        if not CURATED_DIR.exists():
            return products
        for path in CURATED_DIR.rglob("*.json"):
            try:
                data = load_json(path, default=None)
            except json.JSONDecodeError:  # pragma: no cover - invalid files
                LOGGER.warning("Skipping malformed curated feed: %s", path)
                continue
            if not isinstance(data, dict) or "id" not in data:
                continue
            product = self._build_product(data, source="curated")
            if product:
                products.append(product)
        return products

    # ------------------------------------------------------------------
    # External API fetches

    def _fetch_ebay(self, queries: Sequence[str]) -> List[Product]:
        token = ebay.get_token()
        if not token:
            return []
        results: List[Product] = []
        for query in queries:
            for item in ebay.search(query, limit=30, token=token):
                product = self._build_product(item, source="ebay")
                if product:
                    results.append(product)
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
        rating = data.get("rating")
        if isinstance(rating, str):
            try:
                rating = float(rating)
            except ValueError:
                rating = None
        rating_count = data.get("rating_count") or data.get("total_reviews")
        if isinstance(rating_count, str):
            try:
                rating_count = int(rating_count.replace(",", ""))
            except ValueError:
                rating_count = None
        description = data.get("description")
        if not description:
            features = data.get("features")
            if isinstance(features, list):
                description = " ".join(str(item) for item in features[:2] if item)
        return Product(
            id=str(raw_id),
            title=str(title),
            url=str(url),
            image=data.get("image"),
            price=numeric_price,
            price_text=str(price_text) if price_text else None,
            currency=str(currency) if currency else None,
            brand=str(brand) if brand else None,
            category=str(category) if category else None,
            rating=rating if isinstance(rating, (int, float)) else None,
            rating_count=int(rating_count) if isinstance(rating_count, int) else None,
            source=source,
            description=str(description) if description else None,
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
        ebay_results = self._fetch_ebay(queries)
        LOGGER.info("Fetched %s items from eBay", len(ebay_results))
        amazon_results = self._fetch_amazon(queries)
        LOGGER.info("Fetched %s items from Amazon", len(amazon_results))
        combined = self._dedupe(curated + ebay_results + amazon_results)
        LOGGER.info("Ingesting %s total items", len(combined))
        stored = self.repository.ingest(combined)
        LOGGER.info("Repository now tracks %s items", len(stored))
        return stored
