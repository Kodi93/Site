"""Helpers that pick products for editorial roundups and weekly posts."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Sequence

from .models import Product
from .utils import parse_price_string, slugify


RECENCY_WINDOW_DAYS = 30

GUIDE_HOLIDAY_CATEGORY_HINTS: dict[str, list[str]] = {
    "valentine": ["gifts-for-her", "gifts-for-him"],
    "mother": ["gifts-for-her", "home-and-kitchen"],
    "father": ["gifts-for-him", "tech-and-gadgets"],
    "prime": ["tech-and-gadgets", "home-and-kitchen"],
    "school": ["office-and-productivity", "kids-and-family"],
    "halloween": ["entertainment-and-games", "fandom-and-collectibles"],
    "black friday": ["tech-and-gadgets", "home-and-kitchen"],
    "holiday": ["gifts-for-her", "gifts-for-him", "home-and-kitchen"],
}


@dataclass
class SelectionResult:
    items: List[Product]
    related: List[Product]
    hub_slugs: List[str]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _score_product(
    product: Product,
    *,
    now: datetime,
    price_cap: float | None = None,
    preferred_categories: Iterable[str] | None = None,
) -> float:
    updated = _parse_datetime(product.updated_at)
    recency_score = 0.0
    if updated:
        delta = now - updated
        days = max(0.0, min(RECENCY_WINDOW_DAYS, delta.total_seconds() / 86400))
        recency_score = max(0.0, RECENCY_WINDOW_DAYS - days) * 4.0
    click_score = float(product.click_count or 0)
    rating = float(product.rating or 0.0)
    reviews = float(product.total_reviews or 0)
    sentiment_score = rating * reviews
    price_score = 0.0
    amount_currency = parse_price_string(product.price)
    if price_cap is not None and amount_currency:
        amount, _ = amount_currency
        if amount <= price_cap:
            price_score = 120.0 - (price_cap - amount)
        else:
            price_score = max(0.0, 80.0 - (amount - price_cap) * 2.5)
    category_score = 0.0
    if preferred_categories:
        preferred = set(preferred_categories)
        if product.category_slug in preferred:
            category_score = 40.0
    return recency_score + click_score + sentiment_score + price_score + category_score


def _dedupe_products(products: Sequence[Product]) -> List[Product]:
    seen: dict[str, Product] = {}
    for product in products:
        brand = (product.brand or "").strip().lower()
        key = slugify(f"{brand}-{product.title.split('(')[0]}")
        if key not in seen:
            seen[key] = product
    return list(seen.values())


def _filter_recent(products: Iterable[Product], *, now: datetime) -> List[Product]:
    cutoff = now - timedelta(days=RECENCY_WINDOW_DAYS)
    recent: List[Product] = []
    for product in products:
        updated = _parse_datetime(product.updated_at)
        if updated is None or updated >= cutoff:
            recent.append(product)
    return recent


def _ensure_images(products: Iterable[Product]) -> List[Product]:
    return [product for product in products if (product.image or "").strip()]


def _select_with_related(
    candidates: Sequence[Product],
    *,
    limit: int,
    related_limit: int = 12,
) -> tuple[List[Product], List[Product]]:
    chosen = list(candidates[:limit])
    related_pool = [product for product in candidates if product not in chosen]
    return chosen, related_pool[:related_limit]


def select_roundup(
    topic: str,
    price_cap: float,
    products: Sequence[Product],
    *,
    now: datetime | None = None,
) -> SelectionResult:
    """Return top scoring roundup products for the supplied topic."""

    reference = now or datetime.now(timezone.utc)
    recent = _filter_recent(products, now=reference)
    recent = _ensure_images(recent)
    scores = [
        (
            product,
            _score_product(
                product,
                now=reference,
                price_cap=price_cap,
            ),
        )
        for product in recent
    ]
    scores.sort(key=lambda pair: pair[1], reverse=True)
    ranked = _dedupe_products([pair[0] for pair in scores])
    items, related = _select_with_related(ranked, limit=15, related_limit=18)
    category_counts = Counter(product.category_slug for product in items if product.category_slug)
    hub_slugs = [slug for slug, _ in category_counts.most_common(3)]
    return SelectionResult(items=items, related=related, hub_slugs=hub_slugs)


def select_weekly(
    week_number: int,
    products: Sequence[Product],
    *,
    now: datetime | None = None,
) -> SelectionResult:
    reference = now or datetime.now(timezone.utc)
    recent = _filter_recent(products, now=reference)
    recent = _ensure_images(recent)
    scores = [
        (
            product,
            _score_product(
                product,
                now=reference,
                price_cap=None,
            ),
        )
        for product in recent
    ]
    scores.sort(key=lambda pair: pair[1], reverse=True)
    ranked = _dedupe_products([pair[0] for pair in scores])
    items, related = _select_with_related(ranked, limit=12, related_limit=16)
    category_counts = Counter(product.category_slug for product in items if product.category_slug)
    hub_slugs = [slug for slug, _ in category_counts.most_common(3)]
    return SelectionResult(items=items, related=related, hub_slugs=hub_slugs)


def select_seasonal(
    holiday: str,
    categories: Sequence[str],
    products: Sequence[Product],
    *,
    now: datetime | None = None,
) -> SelectionResult:
    reference = now or datetime.now(timezone.utc)
    recent = _filter_recent(products, now=reference)
    recent = _ensure_images(recent)
    scores = [
        (
            product,
            _score_product(
                product,
                now=reference,
                price_cap=None,
                preferred_categories=categories,
            ),
        )
        for product in recent
    ]
    scores.sort(key=lambda pair: pair[1], reverse=True)
    ranked = _dedupe_products([pair[0] for pair in scores])
    items, related = _select_with_related(ranked, limit=15, related_limit=18)
    category_counts = Counter(product.category_slug for product in items if product.category_slug)
    hub_slugs = [slug for slug, _ in category_counts.most_common(3)]
    return SelectionResult(items=items, related=related, hub_slugs=hub_slugs)


def _holiday_category_preferences(holiday: str | None) -> List[str]:
    if not holiday:
        return []
    lowered = holiday.lower()
    for key, categories in GUIDE_HOLIDAY_CATEGORY_HINTS.items():
        if key in lowered:
            return categories
    return []


def _holiday_bonus(product: Product, holiday: str | None) -> float:
    if not holiday:
        return 0.0
    lowered = holiday.lower()
    bonus = 0.0
    title = (product.title or "").lower()
    if lowered in title:
        bonus += 65.0
    keyword_blob = " ".join((product.keywords or []))
    if lowered in keyword_blob.lower():
        bonus += 55.0
    return bonus


def select_spouse_guide(
    price_cap: float,
    products: Sequence[Product],
    *,
    now: datetime | None = None,
    preferred_categories: Sequence[str] | None = None,
    holiday: str | None = None,
) -> SelectionResult:
    reference = now or datetime.now(timezone.utc)
    recent = _filter_recent(products, now=reference)
    recent = _ensure_images(recent)
    category_preferences: List[str] = []
    if preferred_categories:
        for slug in preferred_categories:
            normalized = slug.strip()
            if normalized and normalized not in category_preferences:
                category_preferences.append(normalized)
    for slug in _holiday_category_preferences(holiday):
        if slug not in category_preferences:
            category_preferences.append(slug)
    scores = [
        (
            product,
            _score_product(
                product,
                now=reference,
                price_cap=price_cap,
                preferred_categories=category_preferences or None,
            )
            + _holiday_bonus(product, holiday),
        )
        for product in recent
    ]
    scores.sort(key=lambda pair: pair[1], reverse=True)
    ranked = _dedupe_products([pair[0] for pair in scores])
    items, related = _select_with_related(ranked, limit=15, related_limit=18)
    category_counts = Counter(product.category_slug for product in items if product.category_slug)
    hub_slugs = [slug for slug, _ in category_counts.most_common(3)]
    return SelectionResult(items=items, related=related, hub_slugs=hub_slugs)
