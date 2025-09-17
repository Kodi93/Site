"""Persistence layer for products stored in JSON."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import DATA_DIR, DEFAULT_CATEGORIES, CategoryDefinition
from .models import Category, CooldownEntry, Product
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
            default={"last_updated": None, "products": [], "cooldowns": []},
        )
        if not isinstance(data, dict):
            data = {}
        data.setdefault("last_updated", None)
        data.setdefault("products", [])
        data.setdefault("cooldowns", [])
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
        payload = {
            "last_updated": timestamp(),
            "products": [product.to_dict() for product in products],
            "cooldowns": data.get("cooldowns", []),
        }
        dump_json(self.data_file, payload)

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
                keywords=definition.keywords,
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


def get_category_definition(slug: str) -> CategoryDefinition | None:
    for definition in DEFAULT_CATEGORIES:
        if definition.slug == slug:
            return definition
    return None
