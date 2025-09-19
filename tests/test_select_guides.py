from __future__ import annotations

from datetime import datetime, timezone

from giftgrab.models import Product
from giftgrab.select import select_spouse_guide


def make_product(
    index: int,
    *,
    category_slug: str,
    title: str | None = None,
    price: str = "$45.00",
    rating: float = 4.4,
    clicks: int = 40,
) -> Product:
    product = Product(
        asin=f"ASIN{index}",
        title=title or f"Gift Idea {index}",
        link=f"https://example.com/products/{index}",
        image=f"https://example.com/images/{index}.jpg",
        price=price,
        rating=rating,
        total_reviews=150 + index * 3,
        category_slug=category_slug,
        keywords=["gift", f"keyword-{index}"],
        retailer_slug="amazon",
        retailer_name="Amazon",
        click_count=clicks,
    )
    product.updated_at = "2025-01-10T00:00:00+00:00"
    return product


def test_select_spouse_guide_prefers_categories() -> None:
    products = []
    for index in range(1, 9):
        products.append(
            make_product(
                index,
                category_slug="gifts-for-her",
                rating=4.7,
                clicks=120 + index,
            )
        )
    for index in range(9, 20):
        products.append(
            make_product(
                index,
                category_slug="tech-and-gadgets",
                rating=4.3,
                clicks=30,
            )
        )
    now = datetime(2025, 1, 10, tzinfo=timezone.utc)
    selection = select_spouse_guide(
        60.0,
        products,
        now=now,
        preferred_categories=["gifts-for-her"],
    )
    assert len(selection.items) >= 10
    assert all(item.category_slug == "gifts-for-her" for item in selection.items[:5])


def test_select_spouse_guide_holiday_bonus() -> None:
    base_products = [
        make_product(index, category_slug="tech-and-gadgets", clicks=10)
        for index in range(1, 12)
    ]
    holiday_product = make_product(
        50,
        category_slug="home-and-kitchen",
        title="Valentine Chocolate Maker",
        rating=4.9,
        clicks=15,
    )
    holiday_product.keywords.append("Valentine")
    products = base_products + [holiday_product]
    now = datetime(2025, 1, 20, tzinfo=timezone.utc)
    selection = select_spouse_guide(
        80.0,
        products,
        now=now,
        preferred_categories=[],
        holiday="Valentine's Day",
    )
    assert selection.items[0].title.startswith("Valentine")
