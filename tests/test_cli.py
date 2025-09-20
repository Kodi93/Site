import argparse
from datetime import datetime, timezone

import pytest

from giftgrab.cli import handle_stats
from giftgrab.models import Guide, Product
from giftgrab.repository import ProductRepository


def build_sample_product(product_id: str) -> Product:
    return Product(
        id=product_id,
        title=f"Sample {product_id}",
        url=f"https://example.com/{product_id}",
        image="https://example.com/image.jpg",
        price=19.99,
        price_text="$19.99",
        currency="USD",
        brand="Brand",
        category="Gifts",
        rating=4.5,
        rating_count=10,
        source="amazon",
        description="Sample product",
    )


def test_handle_stats_prints_report(monkeypatch, tmp_path, capsys):
    data_dir = tmp_path / "data"
    repository = ProductRepository(base_dir=data_dir)
    products = [build_sample_product("p1")]
    repository.save_products(products)
    guides = [
        Guide(
            slug="guide-1",
            title="Guide One",
            description="Desc",
            products=products,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
        )
    ]
    repository.save_guides(guides)

    monkeypatch.setattr("giftgrab.cli.ProductRepository", lambda: repository)

    captured = {}

    def fake_generate_stats_report(*, products, guides, top_categories, recent_days):
        captured["products"] = products
        captured["guides"] = guides
        captured["top_categories"] = top_categories
        captured["recent_days"] = recent_days
        return "REPORT"

    monkeypatch.setattr("giftgrab.cli.generate_stats_report", fake_generate_stats_report)

    args = argparse.Namespace(top_categories=3, recent_days=10)
    handle_stats(args)

    output = capsys.readouterr().out.strip()
    assert output == "REPORT"
    assert len(captured["products"]) == 1
    assert captured["guides"][0].slug == "guide-1"
    assert captured["top_categories"] == 3
    assert captured["recent_days"] == 10


def test_handle_stats_validates_arguments():
    args = argparse.Namespace(top_categories=-1, recent_days=7)
    with pytest.raises(SystemExit) as excinfo:
        handle_stats(args)
    assert "--top-categories cannot be negative" in str(excinfo.value)

    args = argparse.Namespace(top_categories=1, recent_days=0)
    with pytest.raises(SystemExit) as excinfo:
        handle_stats(args)
    assert "--recent-days must be at least 1" in str(excinfo.value)
