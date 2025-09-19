from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from giftgrab.article_repository import ArticleRepository, RoundupHistoryEntry
from giftgrab.repository import ProductRepository
from giftgrab.roundups import generate_roundups_for_span, run_daily_roundups


CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "step1.roundups.json"
)


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


def test_run_daily_roundups_respects_cooldown(tmp_path) -> None:
    repo = ProductRepository(data_file=tmp_path / "products.json")
    article_repo = ArticleRepository(tmp_path / "articles.json")
    recent_entry = RoundupHistoryEntry(
        topic="funny gifts",
        cap=10,
        slug="top-10-funny-gifts-under-10",
        last_published=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
    )
    article_repo.save_roundup_history([recent_entry])

    roundups, _ = run_daily_roundups(
        repository=repo,
        article_repository=article_repo,
        limit=3,
        days=1,
        seed="cooldown",
    )

    assert roundups
    assert all(
        not (roundup.topic == "funny gifts" and roundup.price_cap == 10)
        for roundup in roundups
    )


def test_versioned_slug_for_reused_pairing(tmp_path) -> None:
    repo = ProductRepository(data_file=tmp_path / "products.json")
    article_repo = ArticleRepository(tmp_path / "articles.json")
    old_entry = RoundupHistoryEntry(
        topic="funny gifts",
        cap=10,
        slug="top-10-funny-gifts-under-10",
        last_published=(datetime.now(timezone.utc) - timedelta(days=120)).isoformat(),
    )
    article_repo.save_roundup_history([old_entry])

    config_path = tmp_path / "config.json"
    config_path.write_text('[{"topic": "funny gifts", "caps": [10]}]', encoding="utf-8")

    start_day = datetime.now(timezone.utc).date()
    roundups, _ = run_daily_roundups(
        config_path=config_path,
        repository=repo,
        article_repository=article_repo,
        limit=1,
        days=1,
        seed="version",
        start_date=start_day,
    )

    assert len(roundups) == 1
    generated = roundups[0]
    assert generated.topic == "funny gifts"
    assert generated.price_cap == 10
    expected_week = start_day.isocalendar()[1]
    assert generated.slug.endswith(f"-w{expected_week:02d}")

    history = article_repo.load_roundup_history()
    assert len(history) == 1
    assert history[0].slug == generated.slug
    parsed = datetime.fromisoformat(history[0].last_published)
    assert parsed.date() >= date(2024, 1, 1)
