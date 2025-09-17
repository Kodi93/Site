from __future__ import annotations

from pathlib import Path

import json
import re

from giftgrab.config import SiteSettings
from giftgrab.generator import SiteGenerator
from giftgrab.models import Category, PricePoint, Product


def make_product(index: int, category: Category, *, drop: bool) -> Product:
    previous_amount = 100.0 + index
    drop_amount = 8.0 + index if drop else 0.0
    latest_amount = previous_amount - drop_amount
    latest_display = f"${latest_amount:,.2f}"
    previous_display = f"${previous_amount:,.2f}"
    history = [
        PricePoint(
            amount=previous_amount,
            currency="USD",
            display=previous_display,
            captured_at=f"2024-01-{index:02d}T00:00:00Z",
        ),
        PricePoint(
            amount=latest_amount,
            currency="USD",
            display=latest_display,
            captured_at=f"2024-02-{index:02d}T00:00:00Z",
        ),
    ]
    return Product(
        asin=f"ASIN{index}",
        title=f"Product {index}",
        link="https://example.com/product",
        image="https://example.com/image.jpg",
        price=latest_display,
        rating=4.6,
        total_reviews=120,
        category_slug=category.slug,
        brand=f"Brand {index}",
        summary=f"Summary for product {index}",
        price_history=history,
        updated_at=f"2024-02-{index:02d}T00:00:00",
    )


def build_products(category: Category) -> list[Product]:
    return [make_product(index, category, drop=index % 2 == 0) for index in range(1, 13)]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_jsonld(html: str) -> list[dict]:
    pattern = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)
    blocks = pattern.findall(html)
    return [json.loads(block) for block in blocks]


def test_adsense_layout_and_deals_page(tmp_path: Path) -> None:
    settings = SiteSettings(
        site_name="Test Radar",
        base_url="https://example.com",
        adsense_client_id="pub-test",
        adsense_slot="inline-slot",
        adsense_rail_slot="rail-slot",
    )
    category = Category(slug="testing", name="Testing", blurb="Test blurb", keywords=["test"])
    generator = SiteGenerator(settings, output_dir=tmp_path)
    products = build_products(category)

    generator.build([category], products)

    index_html = read(tmp_path / "index.html")
    category_html = read(tmp_path / "categories" / category.slug / "index.html")
    latest_html = read(tmp_path / "latest.html")
    deals_html = read(tmp_path / "deals.html")
    feed_xml = read(tmp_path / "feed.xml")
    sitemap_xml = read(tmp_path / "sitemap.xml")
    robots_txt = read(tmp_path / "robots.txt")

    # Inline ads appear after every five products across grids
    assert index_html.count("card card--ad") == 2
    assert category_html.count("card card--ad") == 2
    assert latest_html.count("card card--ad") == 2
    assert deals_html.count("card card--ad") >= 1

    # Navigation and footer link to the deals page
    assert index_html.count('href="/deals.html"') >= 2

    # Right rail renders when the dedicated slot is configured
    assert "adsense-slot--rail" in index_html
    assert "aria-label=\"Sponsored placements\"" in index_html

    # Footer placement uses the new footer variant class
    assert "adsense-slot--footer" in index_html

    # Deals page structured data and hero content render
    assert "Today's best gift deals" in deals_html
    assert "Top gift deals" in deals_html

    # Syndicated surfaces reference the new page
    assert "Today's gift deals" in feed_xml
    assert "deals.html" in sitemap_xml

    # Robots file references sitemap for crawlers
    assert "User-agent: *" in robots_txt
    assert "Sitemap: https://example.com/sitemap.xml" in robots_txt

    # Category pages expose collection metadata
    category_jsonld = extract_jsonld(category_html)
    collection_entries = [entry for entry in category_jsonld if entry.get("@type") == "CollectionPage"]
    assert collection_entries
    collection = collection_entries[0]
    assert collection["url"] == "https://example.com/categories/testing/index.html"
    has_part = collection.get("hasPart")
    if isinstance(has_part, list):
        assert has_part
        has_part_entry = has_part[0]
    else:
        has_part_entry = has_part
    assert has_part_entry.get("@type") == "ItemList"

    # Product structured data includes brand metadata
    product_page = read(tmp_path / "products" / products[0].slug / "index.html")
    product_jsonld = extract_jsonld(product_page)
    product_entries = [entry for entry in product_jsonld if entry.get("@type") == "Product"]
    assert product_entries
    assert product_entries[0]["brand"] == {"@type": "Brand", "name": products[0].brand}


def test_site_without_adsense_has_no_ad_slots(tmp_path: Path) -> None:
    settings = SiteSettings(
        site_name="No Ads",
        base_url="https://example.com",
    )
    category = Category(slug="testing", name="Testing", blurb="Test blurb", keywords=["test"])
    generator = SiteGenerator(settings, output_dir=tmp_path)
    products = build_products(category)

    generator.build([category], products)

    index_html = read(tmp_path / "index.html")
    deals_html = read(tmp_path / "deals.html")
    feed_xml = read(tmp_path / "feed.xml")
    sitemap_xml = read(tmp_path / "sitemap.xml")
    robots_txt = read(tmp_path / "robots.txt")

    # No AdSense markup is rendered without configuration
    assert "card card--ad" not in index_html
    assert "adsense-slot--footer" not in index_html
    assert "adsense-slot--rail" not in index_html
    assert "googlesyndication" not in index_html

    # Deals experiences still build and are discoverable
    assert "Today's best gift deals" in deals_html
    assert "Today's gift deals" in feed_xml
    assert "deals.html" in sitemap_xml
    assert index_html.count('href="/deals.html"') >= 2
    assert "Allow: /" in robots_txt
