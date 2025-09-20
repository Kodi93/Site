from datetime import datetime, timedelta, timezone

import pytest

from giftgrab.models import Product, merge_products
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


def test_merge_products_updates_textual_price_fields_without_numeric_change():
    existing_product = make_product(1)
    original_updated_at = existing_product.updated_at
    incoming = make_product(1)
    incoming.price = None
    incoming.price_text = "£21.00"
    incoming.currency = "GBP"

    merged = merge_products([existing_product], [incoming])
    merged_product = merged[0]

    assert merged_product.price == existing_product.price
    assert merged_product.price_text == "£21.00"
    assert merged_product.currency == "GBP"
    assert merged_product.updated_at != original_updated_at


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


def test_ingest_failure_does_not_persist_files(tmp_path):
    repo = ProductRepository(base_dir=tmp_path)
    items_before = repo.items_file.read_text(encoding="utf-8")
    seen_before = repo.seen_file.read_text(encoding="utf-8")

    products = [make_product(i) for i in range(40)]
    with pytest.raises(RuntimeError):
        repo.ingest(products)

    assert repo.items_file.read_text(encoding="utf-8") == items_before
    assert repo.seen_file.read_text(encoding="utf-8") == seen_before


def test_ingest_dedupes_affiliate_variants(tmp_path):
    repo = ProductRepository(base_dir=tmp_path)
    affiliate_one = Product.from_dict(
        {
            "id": "ebay-033901618",
            "title": "Inspired Chia Pet Hedgehog",
            "url": "https://www.ebay.com/itm/chia-pet-hedgehog-with-seed-pack-decorative-pottery-"
            "planter-?mkevt=1&mkcid=1&mkrid=711-53200-19255-0&campid=BESTGIFTS&customid=033901618",
            "image": "https://i.ebayimg.com/images/g/example/s-l1600.jpg",
            "price": 24.99,
            "currency": "USD",
            "rating": 4.4,
            "category": "For Adventurers",
            "source": "curated",
        }
    )
    affiliate_two = Product.from_dict(
        {
            "id": "ebay-033801617",
            "title": "Inspired Chia Pet Hedgehog",
            "url": "https://www.ebay.com/itm/chia-pet-hedgehog-with-seed-pack-decorative-pottery-"
            "planter-?mkevt=1&mkcid=1&mkrid=711-53200-19255-0&campid=BESTGIFTS&customid=033801617",
            "image": "https://i.ebayimg.com/images/g/example/s-l1600.jpg",
            "price": 24.99,
            "currency": "USD",
            "rating": 4.4,
            "category": "For Adventurers",
            "source": "curated",
        }
    )

    assert affiliate_one.id == affiliate_two.id
    assert "?" not in affiliate_one.url

    filler = [make_product(i + 100) for i in range(59)]
    stored = repo.ingest([affiliate_one, affiliate_two, *filler])

    stored_ids = [product.id for product in stored]
    assert stored_ids.count(affiliate_one.id) == 1
    assert len(stored) == len(filler) + 1
