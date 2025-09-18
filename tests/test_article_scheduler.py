"""Tests covering article automation behaviors."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from giftgrab.article_repository import ArticleRepository
from giftgrab.article_scheduler import ArticleAutomation
from giftgrab.models import Product


def build_product(index: int, *, category: str = "tech") -> Product:
    product = Product(
        asin=f"ASIN{index}",
        title=f"Gadget {index}",
        link=f"https://example.com/products/{index}",
        image=f"https://example.com/images/{index}.jpg",
        price="$29.99",
        rating=4.2 + (index % 2) * 0.3,
        total_reviews=110 + index * 3,
        category_slug=category,
        brand=f"Brand {index}",
        keywords=["gift", f"feature-{index}"],
        retailer_slug="amazon",
        retailer_name="Amazon",
        click_count=index * 5,
    )
    product.updated_at = "2025-10-15T00:00:00+00:00"
    return product


def make_products(count: int) -> list[Product]:
    categories = ["tech", "coffee", "fitness", "edc"]
    return [
        build_product(index, category=categories[index % len(categories)])
        for index in range(1, count + 1)
    ]


def test_seasonal_articles_reuse_existing_slug(tmp_path: Path) -> None:
    repo = ArticleRepository(tmp_path / "articles.json")
    automation = ArticleAutomation(repo)
    now = datetime(2025, 11, 1, tzinfo=timezone.utc)
    products = make_products(18)

    first = automation.ensure_seasonal(products, now=now)
    assert first is not None
    assert first.status == "published"
    assert first.slug == "black-friday-2025-gift-ideas"
    first_id = first.id

    again = automation.ensure_seasonal(products, now=now)
    assert again is not None
    assert again.id == first_id
    stored = repo.load_articles()
    assert len(stored) == 1
    assert stored[0].slug == "black-friday-2025-gift-ideas"


def test_generate_skips_when_no_products(tmp_path: Path) -> None:
    repo = ArticleRepository(tmp_path / "articles.json")
    automation = ArticleAutomation(repo)
    now = datetime(2025, 3, 1, tzinfo=timezone.utc)

    result = automation.generate([], now=now)
    assert result.roundup is None
    assert result.weekly is None
    assert result.seasonal is None


def test_seasonal_skips_outside_window(tmp_path: Path) -> None:
    repo = ArticleRepository(tmp_path / "articles.json")
    automation = ArticleAutomation(repo)
    products = make_products(18)
    now = datetime(2025, 3, 1, tzinfo=timezone.utc)

    seasonal = automation.ensure_seasonal(products, now=now)
    assert seasonal is None
