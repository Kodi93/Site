import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from giftgrab.config import CategoryDefinition
from giftgrab.models import CooldownEntry
from giftgrab.pipeline import GiftPipeline
from giftgrab.repository import ProductRepository


class DummyGenerator:
    def __init__(self) -> None:
        self.calls = 0
        self.last_products = None

    def build(self, categories, products) -> None:  # pragma: no cover - simple stub
        self.calls += 1
        self.last_products = list(products)


class FakeRetailerAdapter:
    slug = "amazon"
    name = "Amazon"
    cta_label = "Shop now"
    homepage = "https://www.amazon.com/"

    def __init__(self, items):
        self.items = list(items)
        self.last_item_count = None
        self.search_calls = 0

    def search_items(self, *, keywords, item_count):
        self.last_item_count = item_count
        self.search_calls += 1
        return list(self.items[: item_count])

    def decorate_url(self, url):
        return url or "https://example.com/product"


TEST_CATEGORY = CategoryDefinition(
    slug="tech",
    name="Tech",
    keywords=["tech"],
    blurb="Gadgets and gear.",
)


def make_item(index: int) -> dict:
    return {
        "id": f"ASIN{index}",
        "title": f"Test Product {index}",
        "url": f"https://example.com/products/{index}",
        "image": None,
        "price": "$19.99",
        "features": ["feature"],
        "rating": 4.5,
        "total_reviews": 120,
        "brand": f"Brand {index}",
    }


def build_pipeline(repo: ProductRepository, items, minimum_daily_posts: int = 1):
    generator = DummyGenerator()
    retailer = FakeRetailerAdapter(items)
    pipeline = GiftPipeline(
        repository=repo,
        generator=generator,
        categories=[TEST_CATEGORY],
        retailers=[retailer],
        credentials=None,
        minimum_daily_posts=minimum_daily_posts,
    )
    return pipeline, generator, retailer


class PipelineCooldownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        data_file = Path(self.temp_dir.name) / "products.json"
        self.repo = ProductRepository(data_file=data_file)

    def test_recent_products_are_skipped(self) -> None:
        pipeline, generator, _ = build_pipeline(self.repo, [make_item(1)])
        pipeline.run(item_count=1, regenerate_only=False)
        first_cooldowns = self.repo.load_cooldowns()
        self.assertEqual(len(first_cooldowns), 1)
        first_added_at = first_cooldowns[0].added_at
        stored_products = self.repo.load_products()
        self.assertEqual(stored_products[0].brand, "Brand 1")

        pipeline.run(item_count=1, regenerate_only=False)
        products = self.repo.load_products()
        self.assertEqual(len(products), 1)
        cooldowns = self.repo.load_cooldowns()
        self.assertEqual(len(cooldowns), 1)
        self.assertEqual(cooldowns[0].added_at, first_added_at)
        self.assertGreaterEqual(generator.calls, 2)

    def test_cooldown_expiry_allows_repost(self) -> None:
        items = [make_item(2)]
        pipeline, _, _ = build_pipeline(self.repo, items)
        expired_entry = CooldownEntry(
            retailer_slug="amazon",
            asin="ASIN2",
            category_slug="tech",
            added_at=(datetime.now(timezone.utc) - timedelta(days=16)).isoformat(),
        )
        self.repo.save_cooldowns([expired_entry])
        pipeline.run(item_count=1, regenerate_only=False)
        cooldowns = self.repo.load_cooldowns()
        self.assertEqual(len(cooldowns), 1)
        self.assertNotEqual(cooldowns[0].added_at, expired_entry.added_at)
        self.assertEqual(self.repo.load_products()[0].asin, "ASIN2")

    def test_minimum_daily_posts_adjusts_item_count(self) -> None:
        items = [make_item(idx) for idx in range(5)]
        pipeline, _, retailer = build_pipeline(
            self.repo, items, minimum_daily_posts=5
        )
        pipeline.run(item_count=2, regenerate_only=False)
        self.assertEqual(retailer.last_item_count, 5)
        self.assertGreaterEqual(len(self.repo.load_products()), 5)


if __name__ == "__main__":
    unittest.main()
