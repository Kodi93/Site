"""Persistence helpers for catalog and history data."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

from .models import Guide, Product, merge_products
from .utils import dump_json, load_json, timestamp

LOGGER = logging.getLogger(__name__)

DEFAULT_COOLDOWN_DAYS = 30


class ProductRepository:
    """Store products and history in JSON files under ``data/``."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path("data")
        self.items_file = self.base_dir / "items.json"
        self.seen_file = self.base_dir / "seen_items.json"
        self.topics_file = self.base_dir / "topics_history.json"
        self.guides_file = self.base_dir / "guides.json"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for path, default in (
            (self.items_file, []),
            (self.seen_file, {}),
            (self.topics_file, []),
            (self.guides_file, []),
        ):
            if not path.exists():
                dump_json(path, default)

    # ------------------------------------------------------------------
    # Products

    def load_products(self) -> List[Product]:
        data = load_json(self.items_file, default=[]) or []
        products: List[Product] = []
        for entry in data:
            if isinstance(entry, dict) and "id" in entry:
                try:
                    products.append(Product.from_dict(entry))
                except Exception as error:  # pragma: no cover - log invalid payloads
                    LOGGER.warning("Skipping invalid product payload: %s", error)
        return products

    def save_products(self, products: Sequence[Product]) -> None:
        payload = [product.to_dict() for product in products]
        dump_json(self.items_file, payload)

    def ingest(
        self,
        incoming: Iterable[Product],
        *,
        cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
        now: datetime | None = None,
    ) -> List[Product]:
        reference = now or datetime.now(timezone.utc)
        existing = self.load_products()
        seen_map = self._load_seen()
        accepted: List[Product] = []
        cutoff = reference - timedelta(days=cooldown_days)
        for product in incoming:
            last_seen_text = seen_map.get(product.id)
            if last_seen_text:
                try:
                    last_seen = datetime.fromisoformat(last_seen_text)
                    if last_seen.tzinfo is None:
                        last_seen = last_seen.replace(tzinfo=timezone.utc)
                except ValueError:
                    last_seen = None
                if last_seen and last_seen >= cutoff:
                    LOGGER.debug("Skipping %s due to cooldown", product.id)
                    continue
            product.touch()
            accepted.append(product)
            seen_map[product.id] = reference.isoformat()
        merged = merge_products(existing, accepted)
        self.save_products(merged)
        self._save_seen(seen_map)
        count = len(merged)
        if count < 50:
            raise RuntimeError(f"Inventory too small: {count}")
        return merged

    def _load_seen(self) -> dict[str, str]:
        data = load_json(self.seen_file, default={}) or {}
        result: dict[str, str] = {}
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str) and isinstance(value, str):
                    result[key] = value
        return result

    def _save_seen(self, payload: dict[str, str]) -> None:
        dump_json(self.seen_file, payload)

    # ------------------------------------------------------------------
    # Topics

    def load_topic_history(self) -> List[dict]:
        data = load_json(self.topics_file, default=[]) or []
        history: List[dict] = []
        for entry in data:
            if isinstance(entry, dict) and entry.get("slug"):
                history.append(entry)
        return history

    def append_topic_history(self, slug: str, title: str, when: datetime | None = None) -> None:
        record = {
            "slug": slug,
            "title": title,
            "date": (when or datetime.now(timezone.utc)).isoformat(),
        }
        history = self.load_topic_history()
        history.append(record)
        dump_json(self.topics_file, history)

    # ------------------------------------------------------------------
    # Guides

    def save_guides(self, guides: Sequence[Guide]) -> None:
        dump_json(self.guides_file, [guide.to_dict() for guide in guides])

    def load_guides(self) -> List[Guide]:
        data = load_json(self.guides_file, default=[]) or []
        guides: List[Guide] = []
        for entry in data:
            if isinstance(entry, dict) and entry.get("slug"):
                try:
                    products = [
                        Product.from_dict(item)
                        for item in entry.get("products", [])
                        if isinstance(item, dict) and item.get("id")
                    ]
                    guides.append(
                        Guide(
                            slug=entry["slug"],
                            title=entry.get("title", entry["slug"]),
                            description=entry.get("description", ""),
                            products=products,
                            created_at=entry.get("created_at", timestamp()),
                        )
                    )
                except Exception as error:  # pragma: no cover - log invalid payloads
                    LOGGER.warning("Skipping invalid guide entry: %s", error)
        return guides

    def count_guides(self) -> int:
        return len(self.load_guides())

    def clear_guides(self) -> None:
        dump_json(self.guides_file, [])


def ensure_recent(entries: Sequence[dict], *, days: int) -> List[dict]:
    reference = datetime.now(timezone.utc)
    cutoff = reference - timedelta(days=days)
    results: List[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        date_text = entry.get("date")
        if not isinstance(date_text, str):
            continue
        try:
            value = datetime.fromisoformat(date_text)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if value >= cutoff:
            results.append(entry)
    return results
