"""Automation helpers that generate roundup, seasonal, and weekly articles."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import List, Sequence

from .article_repository import ArticleRepository
from .articles import Article
from .config import DEFAULT_CATEGORIES
from .content_gen import make_roundup, make_seasonal, make_weekly_picks
from .models import Product
from .select import select_roundup, select_seasonal, select_weekly
from .utils import slugify

logger = logging.getLogger(__name__)


ROUNDUP_TOPICS: List[tuple[str, float]] = [
    ("EDC", 25.0),
    ("Camper Gadgets", 50.0),
    ("Coworker Gag", 30.0),
    ("Tech Stocking Stuffers", 40.0),
    ("Gifts for Gamers", 60.0),
    ("Fitness Gifts", 55.0),
    ("Coffee Lover Gear", 45.0),
    ("Pet Owner", 35.0),
]


SEASONAL_EVENTS: List[tuple[str, int, int]] = [
    ("Valentine's Day", 2, 14),
    ("Mother's Day", 5, 12),
    ("Father's Day", 6, 16),
    ("Prime Day", 7, 12),
    ("Back to School", 8, 5),
    ("Halloween", 10, 31),
    ("Black Friday", 11, 29),
    ("Holiday", 12, 5),
]


def _nearest_event(now: date, window_days: int = 60) -> tuple[str, date] | None:
    events: List[tuple[str, date]] = []
    year = now.year
    for name, month, day in SEASONAL_EVENTS:
        event_date = date(year, month, day)
        if event_date < now:
            event_date = date(year + 1, month, day)
        events.append((name, event_date))
    events.sort(key=lambda item: item[1])
    for name, event_date in events:
        delta = event_date - now
        if delta <= timedelta(days=window_days):
            return name, event_date
    return None


@dataclass
class GeneratedArticles:
    roundup: Article | None
    weekly: Article | None
    seasonal: Article | None


class ArticleAutomation:
    """Coordinate product selection and article creation."""

    def __init__(self, repository: ArticleRepository) -> None:
        self.repository = repository

    def _select_roundup_topic(self) -> tuple[str, float]:
        index = self.repository.get_roundup_index()
        topic = ROUNDUP_TOPICS[index % len(ROUNDUP_TOPICS)]
        self.repository.set_roundup_index(index + 1)
        return topic

    def ensure_roundup(
        self,
        products: Sequence[Product],
        *,
        now: datetime,
    ) -> Article | None:
        if not products:
            return None
        topic, price_cap = self._select_roundup_topic()
        selection = select_roundup(topic, price_cap, products, now=now)
        if len(selection.items) < 10:
            logger.warning("Skipping roundup creation; not enough products available")
            return None
        slug = slugify(
            f"{topic}-gifts-under-{int(price_cap)}-{now.date().isoformat()}"
        )
        existing = self.repository.find_by_slug(slug)
        article = make_roundup(
            f"{topic}",
            price_cap,
            selection.items,
            related_products=selection.related,
            hub_slugs=selection.hub_slugs,
            now=now,
        )
        if existing:
            article = article.copy_with(
                id=existing.id,
                created_at=existing.created_at,
            )
        article.mark_published(now)
        self.repository.upsert(article)
        return article

    def ensure_weekly(
        self,
        products: Sequence[Product],
        *,
        now: datetime,
    ) -> Article | None:
        if not products:
            return None
        iso = now.isocalendar()
        week_number = iso.week
        year = iso.year
        existing = self.repository.find_by_slug(f"week-{week_number}-{year}")
        if existing and existing.status == "published":
            return existing
        selection = select_weekly(week_number, products, now=now)
        if len(selection.items) < 8:
            logger.warning("Skipping weekly picks; insufficient inventory")
            return None
        article = make_weekly_picks(
            week_number,
            selection.items,
            year=year,
            related_products=selection.related,
            hub_slugs=selection.hub_slugs,
            now=now,
        )
        article.mark_published(now)
        self.repository.upsert(article)
        return article

    def ensure_seasonal(
        self,
        products: Sequence[Product],
        *,
        now: datetime,
    ) -> Article | None:
        today = now.date()
        upcoming = _nearest_event(today)
        if not upcoming:
            return None
        holiday, event_date = upcoming
        if (event_date - today).days < 0:
            return None
        categories = [definition.slug for definition in DEFAULT_CATEGORIES]
        selection = select_seasonal(holiday, categories, products, now=now)
        if len(selection.items) < 10:
            return None
        slug = slugify(f"{holiday}-{event_date.year}-gift-ideas")
        existing = self.repository.find_by_slug(slug)
        article = make_seasonal(
            holiday,
            event_date.year,
            categories,
            selection.items,
            related_products=selection.related,
            now=now,
        )
        if existing:
            article = article.copy_with(
                id=existing.id,
                created_at=existing.created_at,
            )
        article.mark_published(now)
        self.repository.upsert(article)
        return article

    def generate(self, products: Sequence[Product], *, now: datetime | None = None) -> GeneratedArticles:
        reference = now or datetime.now(timezone.utc)
        roundup = self.ensure_roundup(products, now=reference)
        weekly = self.ensure_weekly(products, now=reference)
        seasonal = self.ensure_seasonal(products, now=reference)
        return GeneratedArticles(roundup=roundup, weekly=weekly, seasonal=seasonal)
