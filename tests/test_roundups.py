from __future__ import annotations

from datetime import date
from pathlib import Path

from giftgrab.article_repository import ArticleRepository
from giftgrab.repository import ProductRepository
from giftgrab.roundups import generate_roundups_for_span, run_daily_roundups


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "roundups.json"


def test_generate_roundups_for_span_year_scale() -> None:
    roundups, products = generate_roundups_for_span(
        config_path=CONFIG_PATH,
        start_date=date(2024, 1, 1),
        days=365,
        limit=2,
        seed="unit-test",
    )

    assert len(roundups) == 365 * 2
    assert len(products) == 365 * 2 * 10
    assert all(roundup.items for roundup in roundups[:10])
    assert all(product.bullets for product in products[:10])
    assert all(product.caveats for product in products[:10])
    assert all(roundup.published_at for roundup in roundups[:10])
    assert all(product.published_at for product in products[:10])
    # Title should include the edition year to differentiate entries.
    assert "2024" in roundups[0].title


def test_run_daily_roundups_persists_multiple_days(tmp_path) -> None:
    repo = ProductRepository(data_file=tmp_path / "products.json")
    article_repo = ArticleRepository(tmp_path / "articles.json")

    roundups, products = run_daily_roundups(
        repository=repo,
        article_repository=article_repo,
        limit=2,
        days=3,
        seed="calendar",
        start_date=date(2024, 5, 1),
    )

    assert len(roundups) == 6
    assert len(products) == 60

    stored_generated = repo.load_generated_products()
    assert len(stored_generated) == len(products)
    stored_roundups = article_repo.load_roundups()
    assert len(stored_roundups) == len(roundups)
    assert stored_roundups[0].items
