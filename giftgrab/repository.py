"""Persistence layer for products stored in JSON."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import DATA_DIR, DEFAULT_CATEGORIES, CategoryDefinition
from .models import Category, CooldownEntry, GeneratedProduct, Product
from .utils import dump_json, load_json, timestamp

logger = logging.getLogger(__name__)


class ProductRepository:
    """Store and retrieve product data from a JSON document."""

    def __init__(self, data_file: Path | None = None) -> None:
        self.data_file = data_file or DATA_DIR / "products.json"
        self._ensure_file_exists()

    def _load_raw_data(self) -> Dict[str, object]:
        data = load_json(
            self.data_file,
            default={
                "last_updated": None,
                "products": [],
                "cooldowns": [],
                "generated_products": [],
            },
        )
        if not isinstance(data, dict):
            data = {}
        data.setdefault("last_updated", None)
        data.setdefault("products", [])
        data.setdefault("cooldowns", [])
        data.setdefault("generated_products", [])
        return data

    def _ensure_file_exists(self) -> None:
        if not self.data_file.exists():
            logger.debug("Creating new data file at %s", self.data_file)
            dump_json(
                self.data_file,
                {
                    "last_updated": None,
                    "products": [],
                    "cooldowns": [],
                    "generated_products": [],
                },
            )

    def load_products(self) -> List[Product]:
        data = self._load_raw_data()
        products = [
            Product.from_dict(raw)
            for raw in data.get("products", [])
            if isinstance(raw, dict)
        ]
        return products

    def save_products(self, products: Iterable[Product]) -> None:
        data = self._load_raw_data()
        data["products"] = [product.to_dict() for product in products]
        data["last_updated"] = timestamp()
        dump_json(self.data_file, data)

    def upsert_products(self, products: Iterable[Product]) -> List[Product]:
        existing = {
            (product.retailer_slug, product.asin): product
            for product in self.load_products()
        }
        for product in products:
            key = (product.retailer_slug, product.asin)
            if not product.price_history and product.price:
                product.record_price(product.price)
            stored = existing.get(key)
            if stored:
                stored.merge_from(product)
                existing[key] = stored
            else:
                product.touch()
                existing[key] = product
        merged = list(existing.values())
        self.save_products(merged)
        return merged

    def load_cooldowns(self) -> List[CooldownEntry]:
        data = self._load_raw_data()
        entries = []
        for raw in data.get("cooldowns", []):
            if isinstance(raw, dict) and raw.get("asin"):
                entries.append(CooldownEntry.from_dict(raw))
        return entries

    def save_cooldowns(self, cooldowns: Iterable[CooldownEntry]) -> None:
        data = self._load_raw_data()
        data["cooldowns"] = [entry.to_dict() for entry in cooldowns]
        dump_json(self.data_file, data)

    def prune_cooldowns(
        self, retention_days: int, now: datetime | None = None
    ) -> List[CooldownEntry]:
        return self.update_cooldowns(
            [], retention_days=retention_days, now=now
        )

    def update_cooldowns(
        self,
        new_entries: Iterable[CooldownEntry],
        *,
        retention_days: int,
        now: datetime | None = None,
    ) -> List[CooldownEntry]:
        reference = now or datetime.now(timezone.utc)
        cutoff = reference - timedelta(days=retention_days)
        active: Dict[tuple[str, str], CooldownEntry] = {}
        for entry in self.load_cooldowns():
            if entry.added_at_datetime() >= cutoff:
                active[entry.key] = entry
        for entry in new_entries:
            active[entry.key] = entry
        remaining = [
            entry
            for entry in active.values()
            if entry.added_at_datetime() >= cutoff
        ]
        remaining.sort(key=lambda entry: entry.added_at, reverse=True)
        self.save_cooldowns(remaining)
        return remaining

    def list_categories(self) -> List[Category]:
        return [
            Category(
                slug=definition.slug,
                name=definition.name,
                blurb=definition.blurb,
                keywords=list(definition.keywords),
                image=definition.image,
                card_image=definition.card_image,
                hero_image=definition.hero_image,
            )
            for definition in DEFAULT_CATEGORIES
        ]

    def get_products_by_category(self, category_slug: str) -> List[Product]:
        return [
            product
            for product in self.load_products()
            if product.category_slug == category_slug
        ]

    def find_by_asin(self, asin: str) -> Optional[Product]:
        for product in self.load_products():
            if product.asin == asin:
                return product
        return None

    def get_last_updated(self) -> Optional[datetime]:
        raw = load_json(self.data_file, default={})
        ts = raw.get("last_updated")
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Generated product helpers

    def load_generated_products(self) -> List[GeneratedProduct]:
        data = self._load_raw_data()
        products: List[GeneratedProduct] = []
        for raw in data.get("generated_products", []):
            if isinstance(raw, dict):
                try:
                    products.append(GeneratedProduct.from_dict(raw))
                except Exception as error:  # pragma: no cover - log for visibility
                    logger.debug("Skipping invalid generated product payload: %s", error)
        return products

    def save_generated_products(self, products: Iterable[GeneratedProduct]) -> None:
        data = self._load_raw_data()
        data["generated_products"] = [product.to_dict() for product in products]
        dump_json(self.data_file, data)

    def upsert_generated_products(
        self, products: Iterable[GeneratedProduct]
    ) -> List[GeneratedProduct]:
        existing = {product.slug: product for product in self.load_generated_products()}
        for product in products:
            stored = existing.get(product.slug)
            if stored:
                product.created_at = stored.created_at
                if stored.published_at and not product.published_at:
                    product.published_at = stored.published_at
                if stored.status == "published" and product.status != "published":
                    product.status = stored.status
                existing[product.slug] = product
            else:
                if product.status == "published" and not product.published_at:
                    product.published_at = timestamp()
                existing[product.slug] = product
        merged = sorted(existing.values(), key=lambda item: item.updated_at, reverse=True)
        self.save_generated_products(merged)
        return merged

    def find_generated_product(self, slug: str) -> GeneratedProduct | None:
        slug = (slug or "").strip().lower()
        for product in self.load_generated_products():
            if product.slug == slug:
                return product
        return None

    def recent_generated_products(
        self, *, days: int = 7, now: datetime | None = None
    ) -> List[GeneratedProduct]:
        reference = now or datetime.now(timezone.utc)
        cutoff = reference - timedelta(days=days)
        recent: List[GeneratedProduct] = []
        for product in self.load_generated_products():
            published_raw = product.published_at or product.updated_at
            try:
                published_dt = datetime.fromisoformat(published_raw)
            except (TypeError, ValueError):
                continue
            if published_dt.tzinfo is None:
                published_dt = published_dt.replace(tzinfo=timezone.utc)
            published_dt = published_dt.astimezone(timezone.utc)
            if published_dt >= cutoff:
                recent.append(product)
        recent.sort(key=lambda item: (item.score, item.updated_at), reverse=True)
        return recent

    def best_generated_product(
        self, *, days: int = 7, now: datetime | None = None
    ) -> GeneratedProduct | None:
        candidates = self.recent_generated_products(days=days, now=now)
        return candidates[0] if candidates else None


def get_category_definition(slug: str) -> CategoryDefinition | None:
    for definition in DEFAULT_CATEGORIES:
        if definition.slug == slug:
            return definition
    return None
