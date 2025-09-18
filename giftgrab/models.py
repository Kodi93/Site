"""Domain models used throughout the project."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

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

    def record_price(self, price: str | None) -> None:
        """Append a price snapshot to the history if it changed."""

        self.price = price
        parsed = parse_price_string(price)
        if parsed is None:
            return
        value, currency = parsed
        value = round(value, 2)
        if self.price_history:
            last = self.price_history[-1]
            if abs(last.amount - value) < 0.01 and last.currency == currency:
                last.display = price or last.display
                last.captured_at = timestamp()
                self.touch()
                return
        self.price_history.append(
            PricePoint(amount=value, currency=currency, display=price or "")
        )
        self.touch()

    def merge_from(self, other: "Product") -> None:
        """Merge updated fields and price history from another product."""

        if other.title:
            self.title = other.title
        if other.link:
            self.link = other.link
        if other.image:
            self.image = other.image
        if other.price is not None:
            self.record_price(other.price)
        if other.rating is not None:
            self.rating = other.rating
        if other.total_reviews is not None:
            self.total_reviews = other.total_reviews
        if other.summary:
            self.summary = other.summary
        if other.blog_content:
            self.blog_content = other.blog_content
        if other.brand:
            self.brand = other.brand
        if other.retailer_slug:
            self.retailer_slug = other.retailer_slug
        if other.retailer_name:
            self.retailer_name = other.retailer_name
        if other.retailer_homepage:
            self.retailer_homepage = other.retailer_homepage
        if other.call_to_action:
            self.call_to_action = other.call_to_action
        if other.click_count is not None:
            self.click_count = other.click_count
        combined_keywords: List[str] = []
        for keyword in list(self.keywords) + list(other.keywords):
            if keyword and keyword not in combined_keywords:
                combined_keywords.append(keyword)
        if combined_keywords:
            self.keywords = combined_keywords
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

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "blurb": self.blurb,
            "keywords": self.keywords,
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
