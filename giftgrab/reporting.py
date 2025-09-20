"""Reporting helpers for summarizing catalog and guide health."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from .models import Guide, Product


@dataclass
class InventoryStats:
    """Aggregate metrics describing the current product catalog."""

    total_products: int
    sources: list[tuple[str, int]]
    top_categories: list[tuple[str, int]]
    min_price: float | None
    max_price: float | None
    average_price: float | None
    priced_products: int
    missing_images: int
    missing_descriptions: int


@dataclass
class GuideStats:
    """Summaries for the generated roundup guides."""

    total_guides: int
    total_products: int
    average_products: float | None
    recent_count: int
    recent_days: int
    latest_created_at: str | None


def summarize_inventory(products: Sequence[Product], *, top_categories: int = 5) -> InventoryStats:
    """Compute aggregate statistics for the provided catalog."""

    total = len(products)
    source_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    prices: list[float] = []
    missing_images = 0
    missing_descriptions = 0

    for product in products:
        source = (product.source or "unknown").strip() or "unknown"
        source_counter[source] += 1
        if product.category:
            category_counter[str(product.category)] += 1
        if product.price is not None:
            prices.append(float(product.price))
        if not product.image:
            missing_images += 1
        description = (product.description or "").strip()
        if not description:
            missing_descriptions += 1

    priced_products = len(prices)
    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None
    average_price = (sum(prices) / priced_products) if priced_products else None

    sources = sorted(source_counter.items(), key=lambda item: (-item[1], item[0]))
    category_limit = max(top_categories, 0)
    categories_sorted = sorted(
        category_counter.items(), key=lambda item: (-item[1], item[0])
    )
    if category_limit:
        categories_sorted = categories_sorted[:category_limit]
    else:
        categories_sorted = []

    return InventoryStats(
        total_products=total,
        sources=sources,
        top_categories=categories_sorted,
        min_price=min_price,
        max_price=max_price,
        average_price=average_price,
        priced_products=priced_products,
        missing_images=missing_images,
        missing_descriptions=missing_descriptions,
    )


def summarize_guides(
    guides: Sequence[Guide], *, recent_days: int = 7, now: datetime | None = None
) -> GuideStats:
    """Compute aggregate metrics for generated guides."""

    total_guides = len(guides)
    total_products = sum(len(guide.products) for guide in guides)
    average_products = (total_products / total_guides) if total_guides else None

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    cutoff = reference - timedelta(days=max(recent_days, 0))

    recent_count = 0
    latest_created: datetime | None = None
    for guide in guides:
        created = _parse_iso_datetime(guide.created_at)
        if not created:
            continue
        if created >= cutoff:
            recent_count += 1
        if latest_created is None or created > latest_created:
            latest_created = created

    latest_text = latest_created.isoformat() if latest_created else None
    return GuideStats(
        total_guides=total_guides,
        total_products=total_products,
        average_products=average_products,
        recent_count=recent_count,
        recent_days=recent_days,
        latest_created_at=latest_text,
    )


def generate_stats_report(
    *,
    products: Sequence[Product],
    guides: Sequence[Guide],
    top_categories: int = 5,
    recent_days: int = 7,
    now: datetime | None = None,
) -> str:
    """Return a formatted report summarizing catalog and guide health."""

    inventory = summarize_inventory(products, top_categories=top_categories)
    guide_stats = summarize_guides(guides, recent_days=recent_days, now=now)

    lines: list[str] = ["Inventory Summary"]
    if inventory.total_products == 0:
        lines.append("  No products available.")
    else:
        lines.append(f"  Total products: {inventory.total_products}")
        if inventory.sources:
            sources_text = ", ".join(
                f"{name} ({count})" for name, count in inventory.sources
            )
            lines.append(f"  Sources: {sources_text}")
        if inventory.top_categories:
            categories_text = ", ".join(
                f"{category} ({count})" for category, count in inventory.top_categories
            )
            lines.append(f"  Top categories: {categories_text}")
        if inventory.priced_products:
            price_line = _format_price_summary(
                inventory.min_price, inventory.max_price, inventory.average_price
            )
            item_label = "item" if inventory.priced_products == 1 else "items"
            lines.append(
                f"  Pricing: {price_line} across {inventory.priced_products} {item_label}"
            )
        lines.append(f"  Missing images: {inventory.missing_images}")
        lines.append(f"  Missing descriptions: {inventory.missing_descriptions}")

    lines.append("")
    lines.append("Guide Summary")
    if guide_stats.total_guides == 0:
        lines.append("  No guides have been generated yet.")
    else:
        lines.append(f"  Total guides: {guide_stats.total_guides}")
        lines.append(f"  Total referenced products: {guide_stats.total_products}")
        if guide_stats.average_products is not None:
            lines.append(
                f"  Avg products per guide: {guide_stats.average_products:.1f}"
            )
        lines.append(
            f"  Guides updated in last {guide_stats.recent_days} days: {guide_stats.recent_count}"
        )
        if guide_stats.latest_created_at:
            lines.append(
                f"  Most recent guide published: {guide_stats.latest_created_at}"
            )

    return "\n".join(lines)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_price_summary(
    min_price: float | None, max_price: float | None, average_price: float | None
) -> str:
    parts: list[str] = []
    if min_price is not None and max_price is not None:
        if abs(min_price - max_price) < 1e-9:
            parts.append(_format_currency(min_price))
        else:
            parts.append(f"{_format_currency(min_price)}–{_format_currency(max_price)}")
    elif min_price is not None:
        parts.append(f"from {_format_currency(min_price)}")
    elif max_price is not None:
        parts.append(f"up to {_format_currency(max_price)}")

    if average_price is not None:
        parts.append(f"(avg {_format_currency(average_price)})")

    return " ".join(parts) if parts else "no pricing data"


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"
