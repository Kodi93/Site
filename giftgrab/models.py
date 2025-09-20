"""Data models used by the GiftGrab pipeline."""
from __future__ import annotations

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from .utils import slugify, timestamp


@dataclass
class Product:
    """Represents a single catalog item sourced from a retailer."""

    id: str
    title: str
    url: str
    image: Optional[str]
    price: Optional[float]
    price_text: Optional[str]
    currency: Optional[str]
    brand: Optional[str]
    category: Optional[str]
    rating: Optional[float]
    rating_count: Optional[int]
    source: str
    description: Optional[str] = None
    created_at: str = field(default_factory=timestamp)
    updated_at: str = field(default_factory=timestamp)

    @property
    def slug(self) -> str:
        return slugify(f"{self.title}-{self.id}")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "image": self.image,
            "price": self.price,
            "price_text": self.price_text,
            "currency": self.currency,
            "brand": self.brand,
            "category": self.category,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "source": self.source,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Product":
        return cls(
            id=str(payload["id"]),
            title=str(payload["title"]),
            url=str(payload["url"]),
            image=payload.get("image"),
            price=payload.get("price"),
            price_text=payload.get("price_text"),
            currency=payload.get("currency"),
            brand=payload.get("brand"),
            category=payload.get("category"),
            rating=payload.get("rating"),
            rating_count=payload.get("rating_count"),
            source=str(payload.get("source", "curated")),
            description=payload.get("description"),
            created_at=payload.get("created_at", timestamp()),
            updated_at=payload.get("updated_at", timestamp()),
        )

    def touch(self) -> None:
        self.updated_at = timestamp()


@dataclass
class Guide:
    """Represents a generated roundup guide."""

    slug: str
    title: str
    description: str
    products: List[Product]
    created_at: str = field(default_factory=timestamp)

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "products": [product.to_dict() for product in self.products],
            "created_at": self.created_at,
        }


def merge_products(existing: Iterable[Product], incoming: Iterable[Product]) -> List[Product]:
    """Merge incoming products with existing ones, keeping the freshest copy."""

    lookup = {product.id: product for product in existing}
    for product in incoming:
        stored = lookup.get(product.id)
        if stored is None:
            lookup[product.id] = product
            continue
        updated = False
        if product.title and product.title != stored.title:
            stored.title = product.title
            updated = True
        if product.url and product.url != stored.url:
            stored.url = product.url
            updated = True
        if product.image and product.image != stored.image:
            stored.image = product.image
            updated = True
        if product.price is not None and product.price != stored.price:
            stored.price = product.price
            stored.price_text = product.price_text
            stored.currency = product.currency
            updated = True
        else:
            if product.price_text and product.price_text != stored.price_text:
                stored.price_text = product.price_text
                updated = True
            if product.currency and product.currency != stored.currency:
                stored.currency = product.currency
                updated = True
        if product.brand and product.brand != stored.brand:
            stored.brand = product.brand
            updated = True
        if product.category and product.category != stored.category:
            stored.category = product.category
            updated = True
        if product.rating is not None and product.rating != stored.rating:
            stored.rating = product.rating
            updated = True
        if (
            product.rating_count is not None
            and product.rating_count != stored.rating_count
        ):
            stored.rating_count = product.rating_count
            updated = True
        if product.description and product.description != stored.description:
            stored.description = product.description
            updated = True
        if updated:
            stored.touch()
    merged = sorted(lookup.values(), key=lambda item: item.updated_at, reverse=True)
    return merged


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
