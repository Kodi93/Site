"""Domain models used throughout the project."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

from .utils import parse_price_string, slugify, timestamp


@dataclass
class PricePoint:
    """Represents a captured product price at a point in time."""

    amount: float
    currency: str | None
    display: str
    captured_at: str = field(default_factory=timestamp)

    def to_dict(self) -> dict:
        return {
            "amount": self.amount,
            "currency": self.currency,
            "display": self.display,
            "captured_at": self.captured_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PricePoint":
        return cls(
            amount=float(data["amount"]),
            currency=data.get("currency"),
            display=data.get("display", ""),
            captured_at=data.get("captured_at", timestamp()),
        )


@dataclass
class Product:
    """Represents an Amazon product aggregated for the site."""

    asin: str
    title: str
    link: str
    image: Optional[str]
    price: Optional[str]
    rating: Optional[float]
    total_reviews: Optional[int]
    category_slug: str
    brand: str | None = None
    keywords: List[str] = field(default_factory=list)
    summary: str | None = None
    blog_content: str | None = None
    retailer_slug: str = "amazon"
    retailer_name: str = "Amazon"
    retailer_homepage: str | None = None
    call_to_action: str | None = None
    click_count: int | None = None
    price_history: List[PricePoint] = field(default_factory=list)
    created_at: str = field(default_factory=timestamp)
    updated_at: str = field(default_factory=timestamp)

    @property
    def slug(self) -> str:
        return slugify(f"{self.title}-{self.asin}")

    def to_dict(self) -> dict:
        return {
            "asin": self.asin,
            "title": self.title,
            "link": self.link,
            "image": self.image,
            "price": self.price,
            "rating": self.rating,
            "total_reviews": self.total_reviews,
            "category_slug": self.category_slug,
            "brand": self.brand,
            "keywords": self.keywords,
            "summary": self.summary,
            "blog_content": self.blog_content,
            "retailer_slug": self.retailer_slug,
            "retailer_name": self.retailer_name,
            "retailer_homepage": self.retailer_homepage,
            "call_to_action": self.call_to_action,
            "click_count": self.click_count,
            "price_history": [point.to_dict() for point in self.price_history],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(
            asin=data["asin"],
            title=data["title"],
            link=data["link"],
            image=data.get("image"),
            price=data.get("price"),
            rating=data.get("rating"),
            total_reviews=data.get("total_reviews"),
            category_slug=data["category_slug"],
            brand=data.get("brand"),
            keywords=list(data.get("keywords") or []),
            summary=data.get("summary"),
            blog_content=data.get("blog_content"),
            retailer_slug=data.get("retailer_slug", "amazon"),
            retailer_name=data.get("retailer_name", "Amazon"),
            retailer_homepage=data.get("retailer_homepage"),
            call_to_action=data.get("call_to_action"),
            click_count=data.get("click_count"),
            price_history=[
                PricePoint.from_dict(point)
                for point in data.get("price_history", [])
                if isinstance(point, dict) and "amount" in point
            ],
            created_at=data.get("created_at", timestamp()),
            updated_at=data.get("updated_at", timestamp()),
        )

    def touch(self) -> None:
        """Update the timestamp whenever the record changes."""

        self.updated_at = timestamp()

    def record_price(self, price: str | None) -> bool:
        """Append a price snapshot to the history when it changes.

        Returns ``True`` when the captured price differs from the previous
        snapshot. Callers can use this to decide whether ``updated_at`` should
        be refreshed.
        """

        changed = price != self.price
        self.price = price
        parsed = parse_price_string(price)
        if parsed is None:
            return changed
        value, currency = parsed
        value = round(value, 2)
        if self.price_history:
            last = self.price_history[-1]
            if abs(last.amount - value) < 0.01 and last.currency == currency:
                display = price or last.display
                if display != last.display:
                    last.display = display
                    changed = True
                last.captured_at = timestamp()
                return changed
        self.price_history.append(
            PricePoint(amount=value, currency=currency, display=price or "")
        )
        return True

    def merge_from(self, other: "Product") -> None:
        """Merge updated fields and price history from another product."""

        changed = False
        if other.title and other.title != self.title:
            self.title = other.title
            changed = True
        if other.link and other.link != self.link:
            self.link = other.link
            changed = True
        if other.image and other.image != self.image:
            self.image = other.image
            changed = True
        if other.price is not None and self.record_price(other.price):
            changed = True
        if other.rating is not None and other.rating != self.rating:
            self.rating = other.rating
            changed = True
        if (
            other.total_reviews is not None
            and other.total_reviews != self.total_reviews
        ):
            self.total_reviews = other.total_reviews
            changed = True
        if other.summary and other.summary != self.summary:
            self.summary = other.summary
            changed = True
        if other.blog_content and other.blog_content != self.blog_content:
            self.blog_content = other.blog_content
            changed = True
        if other.brand and other.brand != self.brand:
            self.brand = other.brand
            changed = True
        if other.retailer_slug and other.retailer_slug != self.retailer_slug:
            self.retailer_slug = other.retailer_slug
            changed = True
        if other.retailer_name and other.retailer_name != self.retailer_name:
            self.retailer_name = other.retailer_name
            changed = True
        if (
            other.retailer_homepage
            and other.retailer_homepage != self.retailer_homepage
        ):
            self.retailer_homepage = other.retailer_homepage
            changed = True
        if other.call_to_action and other.call_to_action != self.call_to_action:
            self.call_to_action = other.call_to_action
            changed = True
        if other.click_count is not None and other.click_count != self.click_count:
            self.click_count = other.click_count
            changed = True
        combined_keywords: List[str] = []
        for keyword in list(self.keywords) + list(other.keywords):
            if keyword and keyword not in combined_keywords:
                combined_keywords.append(keyword)
        if combined_keywords and combined_keywords != self.keywords:
            self.keywords = combined_keywords
            changed = True
        if changed:
            self.touch()

    @property
    def latest_price_point(self) -> PricePoint | None:
        if not self.price_history:
            return None
        return self.price_history[-1]

    @property
    def previous_price_point(self) -> PricePoint | None:
        if len(self.price_history) < 2:
            return None
        for point in reversed(self.price_history[:-1]):
            return point
        return None

    def price_change_amount(self) -> float | None:
        latest = self.latest_price_point
        previous = self.previous_price_point
        if not latest or not previous:
            return None
        delta = round(latest.amount - previous.amount, 2)
        if abs(delta) < 0.01:
            return None
        return delta

    def price_drop_percent(self) -> float | None:
        delta = self.price_change_amount()
        previous = self.previous_price_point
        if delta is None or not previous or previous.amount == 0:
            return None
        if delta >= 0:
            return None
        return round(abs(delta) / previous.amount * 100, 2)

    def price_drop_amount(self) -> float | None:
        delta = self.price_change_amount()
        if delta is None or delta >= 0:
            return None
        return round(abs(delta), 2)

    def lowest_price_point(self) -> PricePoint | None:
        if not self.price_history:
            return None
        return min(self.price_history, key=lambda point: point.amount)

    def price_history_summary(self, limit: int = 5) -> List[PricePoint]:
        if not self.price_history:
            return []
        return self.price_history[-limit:]


@dataclass
class Category:
    slug: str
    name: str
    blurb: str
    keywords: List[str]
    image: str | None = None
    card_image: str | None = None
    hero_image: str | None = None

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "blurb": self.blurb,
            "keywords": self.keywords,
            "image": self.image,
            "card_image": self.card_image,
            "hero_image": self.hero_image,
        }


@dataclass
class SiteState:
    products: List[Product]
    last_updated: datetime


@dataclass
class CooldownEntry:
    """Represents a product that is temporarily suppressed from re-posting."""

    retailer_slug: str
    asin: str
    added_at: str = field(default_factory=timestamp)
    category_slug: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.retailer_slug, self.asin)

    def to_dict(self) -> dict:
        return {
            "retailer_slug": self.retailer_slug,
            "asin": self.asin,
            "added_at": self.added_at,
            "category_slug": self.category_slug,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CooldownEntry":
        return cls(
            retailer_slug=data.get("retailer_slug", "amazon"),
            asin=data.get("asin", ""),
            added_at=data.get("added_at", timestamp()),
            category_slug=data.get("category_slug"),
        )

    def added_at_datetime(self) -> datetime:
        raw = self.added_at or timestamp()
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def is_active(self, cooldown_days: int, now: datetime | None = None) -> bool:
        reference = now or datetime.now(timezone.utc)
        return reference - self.added_at_datetime() < timedelta(days=cooldown_days)


GENERATED_PRODUCT_STATUSES = {"draft", "published"}


def _coerce_status(value: str, *, default: str = "draft") -> str:
    normalized = (value or "").strip().lower()
    if normalized not in GENERATED_PRODUCT_STATUSES:
        return default
    return normalized


def _clean_lines(values: Iterable[str] | None) -> List[str]:
    cleaned: List[str] = []
    if not values:
        return cleaned
    for value in values:
        if not value:
            continue
        text = str(value).strip()
        if text:
            cleaned.append(text)
    return cleaned


@dataclass
class GeneratedProduct:
    """Synthetic product detail used for roundup landing pages."""

    slug: str
    name: str
    query: str
    affiliate_url: str
    intro: str
    bullets: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)
    category: Optional[str] = None
    price_cap: Optional[int] = None
    image: Optional[str] = None
    status: str = "draft"
    score: int = 0
    created_at: str = field(default_factory=timestamp)
    updated_at: str = field(default_factory=timestamp)
    published_at: Optional[str] = None

    def __post_init__(self) -> None:
        self.slug = slugify(self.slug)
        self.status = _coerce_status(self.status)
        self.bullets = _clean_lines(self.bullets)
        self.caveats = _clean_lines(self.caveats)
        if self.published_at is not None and not self.published_at.strip():
            self.published_at = None

    def mark_published(self, when: Optional[str] = None) -> None:
        when_value = when or timestamp()
        self.status = "published"
        self.published_at = when_value
        self.updated_at = when_value

    def touch(self) -> None:
        self.updated_at = timestamp()

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "query": self.query,
            "affiliate_url": self.affiliate_url,
            "intro": self.intro,
            "bullets": list(self.bullets),
            "caveats": list(self.caveats),
            "category": self.category,
            "price_cap": self.price_cap,
            "image": self.image,
            "status": self.status,
            "score": self.score,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "published_at": self.published_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GeneratedProduct":
        return cls(
            slug=data.get("slug", ""),
            name=data.get("name", ""),
            query=data.get("query", ""),
            affiliate_url=data.get("affiliate_url", ""),
            intro=data.get("intro", ""),
            bullets=list(data.get("bullets") or []),
            caveats=list(data.get("caveats") or []),
            category=data.get("category"),
            price_cap=data.get("price_cap"),
            image=data.get("image"),
            status=data.get("status", "draft"),
            score=int(data.get("score", 0) or 0),
            created_at=data.get("created_at", timestamp()),
            updated_at=data.get("updated_at", timestamp()),
            published_at=data.get("published_at"),
        )


@dataclass
class RoundupItem:
    """Represents a single ranked item inside a roundup article."""

    rank: int
    title: str
    product_slug: str
    summary: str

    def __post_init__(self) -> None:
        self.rank = int(self.rank)
        self.product_slug = slugify(self.product_slug)
        self.summary = self.summary.strip()

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "title": self.title,
            "product_slug": self.product_slug,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoundupItem":
        return cls(
            rank=data.get("rank", 0),
            title=data.get("title", ""),
            product_slug=data.get("product_slug", ""),
            summary=data.get("summary", ""),
        )


@dataclass
class RoundupArticle:
    """Simplified roundup article referencing generated product pages."""

    slug: str
    title: str
    description: str
    topic: str
    price_cap: Optional[int]
    intro: str
    amazon_search_url: str
    items: List[RoundupItem] = field(default_factory=list)
    status: str = "draft"
    created_at: str = field(default_factory=timestamp)
    updated_at: str = field(default_factory=timestamp)
    published_at: Optional[str] = None

    def __post_init__(self) -> None:
        self.slug = slugify(self.slug)
        self.status = _coerce_status(self.status)
        self.items = [item for item in self.items if item.product_slug]
        if self.published_at is not None and not self.published_at.strip():
            self.published_at = None

    def mark_published(self, when: Optional[str] = None) -> None:
        when_value = when or timestamp()
        self.status = "published"
        self.published_at = when_value
        self.updated_at = when_value

    def touch(self) -> None:
        self.updated_at = timestamp()

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "topic": self.topic,
            "price_cap": self.price_cap,
            "intro": self.intro,
            "amazon_search_url": self.amazon_search_url,
            "items": [item.to_dict() for item in self.items],
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "published_at": self.published_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoundupArticle":
        return cls(
            slug=data.get("slug", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            topic=data.get("topic", ""),
            price_cap=data.get("price_cap"),
            intro=data.get("intro", ""),
            amazon_search_url=data.get("amazon_search_url", ""),
            items=[
                RoundupItem.from_dict(item)
                for item in (data.get("items") or [])
                if isinstance(item, dict)
            ],
            status=data.get("status", "draft"),
            created_at=data.get("created_at", timestamp()),
            updated_at=data.get("updated_at", timestamp()),
            published_at=data.get("published_at"),
        )

    @property
    def body_markdown(self) -> str:
        sections = [self.intro.strip()]
        for item in self.items:
            summary = item.summary.strip()
            sections.append(f"{item.rank}. **{item.title}** — {summary}")
        sections.append(f"Amazon searches: {self.amazon_search_url}")
        return "\n\n".join(section for section in sections if section).strip()
