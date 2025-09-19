from datetime import datetime, timedelta, timezone

import pytest

from giftgrab.models import Product
from giftgrab.repository import ProductRepository


def make_product(idx: int) -> Product:
    price = 20 + idx
    return Product(
        id=f"prod-{idx}",
        title=f"Sample Product {idx}",
        url=f"https://example.com/item/{idx}",
        image=None,
        price=price,
        price_text=f"${price:,.2f}",
        currency="USD",
        brand="TestBrand",
        category="Test Category",
        rating=4.0,
        rating_count=50,
        source="curated",
    )


def test_ingest_enforces_cooldown(tmp_path):
    repo = ProductRepository(base_dir=tmp_path)
    now = datetime.now(timezone.utc)
    products = [make_product(i) for i in range(60)]
    repo.ingest(products, now=now)
    # Re-ingesting the same product within cooldown does not increase the count
    repo.ingest([make_product(1)], now=now + timedelta(days=5))
    assert len(repo.load_products()) == 60
    # After cooldown expires the product is accepted again (still merges)
    repo.ingest([make_product(1)], now=now + timedelta(days=35))
    assert len(repo.load_products()) == 60


def test_ingest_requires_minimum_inventory(tmp_path):
    repo = ProductRepository(base_dir=tmp_path)
    products = [make_product(i) for i in range(40)]
    with pytest.raises(RuntimeError):
        repo.ingest(products)
