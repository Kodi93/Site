from datetime import datetime, timedelta, timezone

import pytest

from giftgrab.models import Guide, Product
from giftgrab.reporting import (
    generate_stats_report,
    summarize_guides,
    summarize_inventory,
)


def build_products() -> list[Product]:
    return [
        Product(
            id="p1",
            title="Item One",
            url="https://example.com/1",
            image="https://example.com/1.jpg",
            price=25.0,
            price_text="$25.00",
            currency="USD",
            brand="BrandA",
            category="Cozy Home",
            rating=4.5,
            rating_count=10,
            source="amazon",
            description="Great gift",
        ),
        Product(
            id="p2",
            title="Item Two",
            url="https://example.com/2",
            image=None,
            price=40.0,
            price_text="$40.00",
            currency="USD",
            brand="BrandB",
            category="Cozy Home",
            rating=4.0,
            rating_count=5,
            source="amazon",
            description="",
        ),
        Product(
            id="p3",
            title="Item Three",
            url="https://example.com/3",
            image=None,
            price=None,
            price_text=None,
            currency=None,
            brand="BrandC",
            category="Desk Gear",
            rating=None,
            rating_count=None,
            source="ebay",
            description=None,
        ),
    ]


def test_summarize_inventory_counts_categories_and_missing_fields():
    products = build_products()
    stats = summarize_inventory(products, top_categories=3)

    assert stats.total_products == 3
    assert stats.sources == [("amazon", 2), ("ebay", 1)]
    assert stats.top_categories == [("Cozy Home", 2), ("Desk Gear", 1)]
    assert stats.priced_products == 2
    assert stats.missing_images == 2
    assert stats.missing_descriptions == 2
    assert stats.min_price == pytest.approx(25.0)
    assert stats.max_price == pytest.approx(40.0)
    assert stats.average_price == pytest.approx(32.5)


def test_summarize_guides_tracks_recent_activity():
    products = build_products()
    now = datetime(2024, 1, 15, tzinfo=timezone.utc)
    guides = [
        Guide(
            slug="guide-1",
            title="Guide One",
            description="A great set",
            products=[products[0], products[1]],
            created_at=(now - timedelta(days=2)).isoformat(),
        ),
        Guide(
            slug="guide-2",
            title="Guide Two",
            description="Another",
            products=[products[2]],
            created_at=(now - timedelta(days=10)).isoformat(),
        ),
    ]

    stats = summarize_guides(guides, recent_days=7, now=now)

    assert stats.total_guides == 2
    assert stats.total_products == 3
    assert stats.average_products == pytest.approx(1.5)
    assert stats.recent_count == 1
    assert stats.latest_created_at == (now - timedelta(days=2)).isoformat()


def test_generate_stats_report_formats_summary_sections():
    products = build_products()
    now = datetime(2024, 1, 15, tzinfo=timezone.utc)
    guides = [
        Guide(
            slug="guide-1",
            title="Guide One",
            description="A great set",
            products=[products[0], products[1]],
            created_at=(now - timedelta(days=2)).isoformat(),
        ),
        Guide(
            slug="guide-2",
            title="Guide Two",
            description="Another",
            products=[products[2]],
            created_at=(now - timedelta(days=10)).isoformat(),
        ),
    ]

    report = generate_stats_report(
        products=products,
        guides=guides,
        top_categories=2,
        recent_days=7,
        now=now,
    )

    assert "Inventory Summary" in report
    assert "Total products: 3" in report
    assert "Sources: amazon (2), ebay (1)" in report
    assert "Top categories: Cozy Home (2), Desk Gear (1)" in report
    assert "Pricing: $25.00–$40.00 (avg $32.50) across 2 items" in report
    assert "Missing images: 2" in report
    assert "Guide Summary" in report
    assert "Total guides: 2" in report
    assert "Guides updated in last 7 days: 1" in report
    assert (now - timedelta(days=2)).isoformat() in report
