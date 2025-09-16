"""Domain models used throughout the project."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .utils import slugify, timestamp


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
    keywords: List[str] = field(default_factory=list)
    summary: str | None = None
    blog_content: str | None = None
    alternate_links: List[dict[str, str]] = field(default_factory=list)
    share_url: Optional[str] = None
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
            "keywords": self.keywords,
            "summary": self.summary,
            "blog_content": self.blog_content,
            "alternate_links": [dict(link) for link in self.alternate_links],
            "share_url": self.share_url,
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
            keywords=list(data.get("keywords") or []),
            summary=data.get("summary"),
            blog_content=data.get("blog_content"),
            alternate_links=[dict(link) for link in data.get("alternate_links", []) if link],
            share_url=data.get("share_url"),
            created_at=data.get("created_at", timestamp()),
            updated_at=data.get("updated_at", timestamp()),
        )

    def touch(self) -> None:
        """Update the timestamp whenever the record changes."""

        self.updated_at = timestamp()


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
