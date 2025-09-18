from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from giftgrab.articles import Article
from giftgrab.content_gen import make_roundup, make_seasonal, make_weekly_picks
from giftgrab.generator import SiteGenerator
from giftgrab.models import Category, Product
from giftgrab.select import select_roundup, select_seasonal, select_weekly
from giftgrab.config import SiteSettings


def build_product(index: int, *, category_slug: str = "edc") -> Product:
    product = Product(
        asin=f"ASIN{index}",
        title=f"Everyday Carry Gadget {index}",
        link=f"https://example.com/products/{index}",
        image=f"https://example.com/images/{index}.jpg",
        price="$24.99",
        rating=4.4 + (index % 3) * 0.1,
        total_reviews=120 + index * 5,
        category_slug=category_slug,
        keywords=["compact", f"feature-{index}", "daily carry"],
        summary="A handy gadget for daily use.",
        retailer_slug="amazon",
        retailer_name="Amazon",
        click_count=index * 10,
    )
    product.updated_at = "2025-10-15T00:00:00+00:00"
    return product


@pytest.mark.parametrize("price_cap", [30.0])
def test_make_roundup_generates_article(tmp_path: Path, price_cap: float) -> None:
    products = [build_product(i) for i in range(1, 15)]
    now = datetime.now(timezone.utc)
    selection = select_roundup("EDC", price_cap, products, now=now)
    assert len(selection.items) >= 10
    article = make_roundup(
        "EDC",
        price_cap,
        selection.items,
        related_products=selection.related,
        hub_slugs=selection.hub_slugs,
        now=now,
    )
    assert isinstance(article, Article)
    article.ensure_quality(min_items=10)
    assert article.body_length >= 800
    assert len(article.items) >= 10
    article.mark_published(now)
    category = Category(
        slug="edc",
        name="Everyday Carry",
        blurb="Tools and gadgets built for daily adventure.",
        keywords=["edc", "gadget"],
    )
    settings = SiteSettings(site_name="Test Gifts", base_url="https://example.com")
    generator = SiteGenerator(settings, output_dir=tmp_path)
    generator.build([category], products, articles=[article])
    output_file = tmp_path / article.path
    assert output_file.exists()
    html = output_file.read_text(encoding="utf-8")
    assert "This Week" not in article.title  # sanity check
    assert "BlogPosting" in html
    assert html.count('class="guide-item"') >= len(article.items)
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert article.path.replace("index.html", "") in sitemap


def _build_varied_products(count: int) -> list[Product]:
    categories = ["edc", "tech", "coffee", "pets"]
    return [
        build_product(index, category_slug=categories[index % len(categories)])
        for index in range(1, count + 1)
    ]


def test_make_weekly_picks_produces_editorial_article() -> None:
    products = _build_varied_products(14)
    now = datetime(2025, 9, 18, tzinfo=timezone.utc)
    week_number = now.isocalendar().week
    selection = select_weekly(week_number, products, now=now)
    article = make_weekly_picks(
        week_number,
        selection.items,
        year=now.isocalendar().year,
        related_products=selection.related,
        hub_slugs=selection.hub_slugs,
        now=now,
    )
    article.ensure_quality(min_items=8)
    intro_words = sum(len(paragraph.split()) for paragraph in article.intro)
    assert 120 <= intro_words <= 200
    assert article.slug == f"week-{week_number}-{now.isocalendar().year}"
    assert article.related_product_slugs
    assert len(article.related_product_slugs) == 6
    assert len(article.tags) >= 3
    assert article.body_length >= 800


def test_make_seasonal_uses_calendar_context() -> None:
    products = _build_varied_products(16)
    categories = ["tech", "coffee", "edc"]
    now = datetime(2025, 11, 5, tzinfo=timezone.utc)
    selection = select_seasonal("Holiday", categories, products, now=now)
    article = make_seasonal(
        "Holiday",
        now.year,
        categories,
        selection.items,
        related_products=selection.related,
        now=now,
    )
    article.ensure_quality(min_items=10)
    intro_words = sum(len(paragraph.split()) for paragraph in article.intro)
    assert 120 <= intro_words <= 200
    assert article.slug.startswith("holiday-")
    assert article.hub_slugs[: len(categories)] == categories[: len(article.hub_slugs)]
    assert len(article.related_product_slugs) == 6
    assert "holiday" in {tag.lower() for tag in article.tags}
    assert article.body_length >= 800
