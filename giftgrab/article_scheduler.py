"""Automation helpers that generate roundup, seasonal, and weekly articles."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import List, Sequence, Tuple

from .article_repository import ArticleRepository
from .articles import Article
from .config import DEFAULT_CATEGORIES
from .content_gen import make_roundup, make_seasonal, make_spouse_guide, make_weekly_picks
from .models import Product
from .select import select_roundup, select_seasonal, select_spouse_guide, select_weekly
from .utils import slugify

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuideProfile:
    slug: str
    label: str
    tone: str
    categories: Tuple[str, ...]


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


GUIDE_PRICE_CAPS: List[float] = [25.0, 35.0, 50.0, 75.0, 100.0, 150.0]

GUIDE_PROFILES: List[GuideProfile] = [
    GuideProfile(
        slug="partner",
        label="partner",
        tone="romance-forward surprises",
        categories=("gifts-for-her", "gifts-for-him"),
    ),
    GuideProfile(
        slug="wife",
        label="wife",
        tone="romantic wow-factor gifts",
        categories=("gifts-for-her", "home-and-kitchen"),
    ),
    GuideProfile(
        slug="husband",
        label="husband",
        tone="everyday hero upgrades",
        categories=("gifts-for-him", "tech-and-gadgets"),
    ),
    GuideProfile(
        slug="girlfriend",
        label="girlfriend",
        tone="date-night energy",
        categories=("gifts-for-her", "entertainment-and-games"),
    ),
    GuideProfile(
        slug="boyfriend",
        label="boyfriend",
        tone="weekend adventure fuel",
        categories=("gifts-for-him", "outdoors-and-adventure"),
    ),
    GuideProfile(
        slug="spouse",
        label="spouse",
        tone="anniversary-ready finds",
        categories=("gifts-for-her", "gifts-for-him", "home-and-kitchen"),
    ),
    GuideProfile(
        slug="fiance",
        label="fiancé",
        tone="engagement-season sparkle",
        categories=("gifts-for-her", "gifts-for-him", "home-and-kitchen"),
    ),
]

GUIDE_ROTATION: List[tuple[GuideProfile, float]] = [
    (profile, price)
    for price in GUIDE_PRICE_CAPS
    for profile in GUIDE_PROFILES
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
    guide: Article | None


class ArticleAutomation:
    """Coordinate product selection and article creation."""

    def __init__(self, repository: ArticleRepository) -> None:
        self.repository = repository

    def _select_roundup_topic(self) -> tuple[str, float]:
        index = self.repository.get_roundup_index()
        topic = ROUNDUP_TOPICS[index % len(ROUNDUP_TOPICS)]
        self.repository.set_roundup_index(index + 1)
        return topic

    def _guide_rotation(self, index: int) -> tuple[GuideProfile, float]:
        if not GUIDE_ROTATION:
            raise RuntimeError("Guide rotation configuration is empty")
        profile, price_cap = GUIDE_ROTATION[index % len(GUIDE_ROTATION)]
        return profile, price_cap

    @staticmethod
    def _parse_iso(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def ensure_spouse_guide(
        self,
        products: Sequence[Product],
        *,
        now: datetime,
        ignore_cadence: bool = False,
        update_last_published: bool = True,
    ) -> Article | None:
        if not products:
            return None
        index = self.repository.get_guide_index()
        profile, price_cap = self._guide_rotation(index)
        last_iso = self.repository.get_guide_last_published()
        last_published = self._parse_iso(last_iso)
        if (
            not ignore_cadence
            and last_published is not None
            and (now - last_published) < timedelta(days=3)
        ):
            logger.debug("Skipping partner guide; cadence window not met")
            return None
        upcoming = _nearest_event(now.date(), window_days=60)
        holiday = None
        holiday_date: date | None = None
        if upcoming:
            holiday, holiday_date = upcoming
        selection = select_spouse_guide(
            price_cap,
            products,
            now=now,
            preferred_categories=profile.categories,
            holiday=holiday,
        )
        if len(selection.items) < 10:
            logger.warning("Skipping partner guide; insufficient qualifying products")
            return None
        slug = slugify(
            f"{profile.slug}-gifts-under-{int(price_cap)}-{now.date().isoformat()}"
        )
        existing = self.repository.find_by_slug(slug)
        article = make_spouse_guide(
            audience_slug=profile.slug,
            audience_label=profile.label,
            tone=profile.tone,
            price_cap=price_cap,
            products=selection.items,
            now=now,
            holiday=holiday,
            holiday_date=holiday_date,
            related_products=selection.related,
            hub_slugs=selection.hub_slugs,
        )
        if existing:
            article = article.copy_with(
                id=existing.id,
                created_at=existing.created_at,
            )
        article.mark_published(now)
        self.repository.upsert(article)
        self.repository.set_guide_index(index + 1)
        if update_last_published:
            self.repository.set_guide_last_published(article.published_at or now.isoformat())
        return article

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
        guide = self.ensure_spouse_guide(products, now=reference)
        return GeneratedArticles(
            roundup=roundup,
            weekly=weekly,
            seasonal=seasonal,
            guide=guide,
        )

    def backfill_guides(
        self,
        products: Sequence[Product],
        *,
        days: int,
        end_date: date | None = None,
    ) -> List[Article]:
        if not products or days <= 0:
            return []
        end = end_date or datetime.now(timezone.utc).date()
        start = end - timedelta(days=days - 1)
        existing_dates: dict[date, Article] = {}
        for article in self.repository.load_articles():
            if article.kind != "guide" or article.status != "published":
                continue
            published = self._parse_iso(article.published_at)
            if published is None:
                continue
            existing_dates[published.date()] = article
        created: List[Article] = []
        original_last_iso = self.repository.get_guide_last_published()
        latest = self._parse_iso(original_last_iso)
        current = start
        while current <= end:
            if current in existing_dates:
                current += timedelta(days=3)
                continue
            reference = datetime(current.year, current.month, current.day, tzinfo=timezone.utc)
            article = self.ensure_spouse_guide(
                products,
                now=reference,
                ignore_cadence=True,
                update_last_published=False,
            )
            if article is not None:
                created.append(article)
                published = self._parse_iso(article.published_at)
                if published and (latest is None or published > latest):
                    latest = published
            current += timedelta(days=3)
        if latest is not None:
            self.repository.set_guide_last_published(latest.isoformat())
        else:
            self.repository.set_guide_last_published(None)
        return created
