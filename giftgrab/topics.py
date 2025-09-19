"""Topic generation based on current inventory and cooldown history."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Sequence

from .models import Product
from .utils import slugify

FALLBACK_TOPICS = [
    "Weird but Useful Gifts",
    "Cozy Home Gifts",
    "Gifts for Coffee Lovers",
    "Desk Setups",
]

PRICE_BREAKS = (25, 50, 100)


@dataclass
class Topic:
    title: str
    slug: str
    category: str | None = None
    brand: str | None = None
    price_cap: float | None = None


def _recent_slugs(history: Sequence[dict], *, days: int = 30) -> set[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    slugs: set[str] = set()
    for entry in history:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        date_text = entry.get("date")
        if not isinstance(slug, str) or not isinstance(date_text, str):
            continue
        try:
            when = datetime.fromisoformat(date_text)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if when >= cutoff:
            slugs.add(slug)
    return slugs


def _eligible(products: Sequence[Product], threshold: float | None = None) -> List[Product]:
    if threshold is None:
        return list(products)
    filtered = [product for product in products if product.price is not None and product.price <= threshold]
    if len(filtered) >= 10:
        return filtered
    return []


def _add_topic(bucket: dict[str, Topic], title: str, *, category: str | None = None, brand: str | None = None, price_cap: float | None = None) -> None:
    slug = slugify(title)
    if slug in bucket:
        return
    bucket[slug] = Topic(title=title, slug=slug, category=category, brand=brand, price_cap=price_cap)


def generate_topics(products: Sequence[Product], *, history: Sequence[dict], limit: int = 15) -> List[Topic]:
    """Return a list of unique topics respecting the cooldown history."""

    recent_slugs = _recent_slugs(history)
    by_category: dict[str, List[Product]] = defaultdict(list)
    by_brand: dict[str, List[Product]] = defaultdict(list)
    for product in products:
        if product.category:
            by_category[product.category].append(product)
        if product.brand:
            by_brand[product.brand].append(product)
    candidates: dict[str, Topic] = {}
    for category, items in sorted(by_category.items(), key=lambda pair: len(pair[1]), reverse=True):
        if len(items) < 12:
            continue
        title = f"Top 20 {category} Gifts"
        _add_topic(candidates, title, category=category)
        _add_topic(candidates, f"Best {category} Gifts Right Now", category=category)
        for price in PRICE_BREAKS:
            eligible = _eligible(items, threshold=price)
            if eligible:
                _add_topic(candidates, f"Top 20 {category} Gifts Under ${price}", category=category, price_cap=float(price))
    for brand, items in sorted(by_brand.items(), key=lambda pair: len(pair[1]), reverse=True):
        if len(items) < 10:
            continue
        _add_topic(candidates, f"Top 20 Gifts from {brand}", brand=brand)
        cheap = _eligible(items, threshold=50)
        if cheap:
            _add_topic(candidates, f"{brand} Gifts Under $50", brand=brand, price_cap=50.0)
    for fallback in FALLBACK_TOPICS:
        _add_topic(candidates, fallback)
    available = [topic for slug, topic in candidates.items() if slug not in recent_slugs]
    if len(available) < limit:
        raise RuntimeError(f"Not enough topics available ({len(available)})")
    available.sort(key=lambda topic: topic.title)
    return available[: max(limit, 15)]
