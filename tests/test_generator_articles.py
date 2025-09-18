"""Integration tests for article rendering via the site generator."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from giftgrab.content_gen import make_weekly_picks
from giftgrab.generator import SiteGenerator
from giftgrab.models import Category, Product
from giftgrab.select import select_weekly
from giftgrab.config import SiteSettings


def build_product(index: int, *, category_slug: str = "tech") -> Product:
    return Product(
        asin=f"ASIN{index}",
        title=f"Editor Pick {index}",
        link=f"https://example.com/products/{index}",
        image=f"https://example.com/images/{index}.jpg",
        price="$24.99",
        rating=4.1 + (index % 4) * 0.2,
        total_reviews=90 + index * 4,
        category_slug=category_slug,
        keywords=["gift", f"keyword-{index}", "weekly"],
        retailer_slug="amazon",
        retailer_name="Amazon",
        click_count=5 * index,
    )


def build_inventory(count: int) -> list[Product]:
    categories = ["tech", "coffee", "fitness", "pets"]
    return [
        build_product(i, category_slug=categories[i % len(categories)])
        for i in range(1, count + 1)
    ]


def test_weekly_article_renders_with_adsense(tmp_path: Path) -> None:
    products = build_inventory(14)
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
    article.mark_published(now)

    categories = [
        Category(slug="tech", name="Tech", blurb="Tech gear.", keywords=["tech"]),
        Category(slug="coffee", name="Coffee", blurb="Coffee gear.", keywords=["coffee"]),
    ]
    settings = SiteSettings(
        site_name="Test Gifts",
        base_url="https://example.com",
        adsense_client_id="ca-pub-123",
        adsense_slot="987654",
    )
    generator = SiteGenerator(settings, output_dir=tmp_path)
    generator.build(categories, products, articles=[article])

    output_file = tmp_path / article.path
    assert output_file.exists()
    html = output_file.read_text(encoding="utf-8")
    assert "BlogPosting" in html
    assert html.count('class="guide-ad"') == 2
    assert "This Week's Cool Finds" in html
    assert "Related picks" in html
    assert "guide-toc" in html

    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert f"weekly/{now.isocalendar().year}/week-{week_number}/" in sitemap
