"""Integration tests for article rendering via the site generator."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from giftgrab.content_gen import make_spouse_guide, make_weekly_picks
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


def build_categories() -> list[Category]:
    return [
        Category(slug="tech", name="Tech", blurb="Tech gear.", keywords=["tech"]),
        Category(slug="coffee", name="Coffee", blurb="Coffee gear.", keywords=["coffee"]),
        Category(slug="fitness", name="Fitness", blurb="Fitness gear.", keywords=["fitness"]),
        Category(slug="pets", name="Pets", blurb="Pet gear.", keywords=["pets"]),
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
    assert '<a href="/guides/index.html">Guides</a>' in html

    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert f"weekly/{now.isocalendar().year}/week-{week_number}/" in sitemap


def test_guides_index_lists_articles(tmp_path: Path) -> None:
    products = build_inventory(14)
    now = datetime(2025, 2, 10, tzinfo=timezone.utc)
    guide = make_spouse_guide(
        audience_slug="partner",
        audience_label="partner",
        tone="romance-forward surprises",
        price_cap=50.0,
        products=products,
        now=now,
        holiday="Valentine's Day",
        holiday_date=date(2025, 2, 14),
        related_products=products[10:],
        hub_slugs=["gifts-for-her", "gifts-for-him"],
    )
    guide.mark_published(now)

    categories = [
        Category(slug="gifts-for-her", name="For Her", blurb="For her", keywords=["her"]),
        Category(slug="gifts-for-him", name="For Him", blurb="For him", keywords=["him"]),
    ]
    settings = SiteSettings(
        site_name="Test Gifts",
        base_url="https://example.com",
    )
    generator = SiteGenerator(settings, output_dir=tmp_path)
    generator.build(categories, products, articles=[guide])

    index_file = tmp_path / "guides" / "index.html"
    assert index_file.exists()
    index_html = index_file.read_text(encoding="utf-8")
    assert "Guides &amp; gift playbooks" in index_html
    assert guide.title in index_html
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "guides/index.html" in sitemap


def test_shortlist_page_contains_status_and_nav(tmp_path: Path) -> None:
    products = build_inventory(8)
    categories = build_categories()
    settings = SiteSettings(
        site_name="Test Gifts",
        base_url="https://example.com",
    )
    generator = SiteGenerator(settings, output_dir=tmp_path)
    generator.build(categories, products)

    shortlist_file = tmp_path / "shortlist.html"
    assert shortlist_file.exists()
    shortlist_html = shortlist_file.read_text(encoding="utf-8")
    assert "data-shortlist-grid" in shortlist_html
    assert "data-shortlist-status" in shortlist_html

    index_html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<a href="/shortlist.html">Shortlist</a>' in index_html


def test_latest_page_exposes_all_products_and_controls(tmp_path: Path) -> None:
    products = build_inventory(75)
    categories = build_categories()
    settings = SiteSettings(
        site_name="Test Gifts",
        base_url="https://example.com",
    )
    generator = SiteGenerator(settings, output_dir=tmp_path)
    generator.build(categories, products)

    latest_html = (tmp_path / "latest.html").read_text(encoding="utf-8")
    assert "data-latest-sentinel" in latest_html
    assert "data-latest-more" in latest_html
    assert "Editor Pick 70" in latest_html


def test_search_page_includes_fallback_and_pagination(tmp_path: Path) -> None:
    products = build_inventory(12)
    categories = build_categories()
    settings = SiteSettings(
        site_name="Test Gifts",
        base_url="https://example.com",
    )
    generator = SiteGenerator(settings, output_dir=tmp_path)
    generator.build(categories, products)

    search_html = (tmp_path / "search.html").read_text(encoding="utf-8")
    assert "<li class='search-result'>" in search_html
    assert "data-search-sentinel" in search_html
    assert "Show more results" in search_html
    assert "slice(0, 60)" not in search_html
