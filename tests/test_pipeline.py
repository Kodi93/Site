import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from giftgrab.article_repository import ArticleRepository
from giftgrab.config import CategoryDefinition
from giftgrab.models import CooldownEntry
from giftgrab.pipeline import GiftPipeline
from giftgrab.repository import ProductRepository


class DummyGenerator:
    def __init__(self) -> None:
        self.calls = 0
        self.last_products = None
        self.last_generated = None
        self.last_roundups = None
        self.last_best = None

    def build(
        self,
        categories,
        products,
        *,
        articles=None,
        generated_products=None,
        roundups=None,
        best_generated=None,
    ) -> None:  # pragma: no cover - stub
        self.calls += 1
        self.last_products = list(products)
        self.last_generated = list(generated_products or [])
        self.last_roundups = list(roundups or [])
        self.last_best = best_generated


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


def build_pipeline(
    repo: ProductRepository,
    items,
    minimum_daily_posts: int = 1,
    bootstrap_target: int = 5,
):
    generator = DummyGenerator()
    retailer = FakeRetailerAdapter(items)
    pipeline = GiftPipeline(
        repository=repo,
        generator=generator,
        categories=[TEST_CATEGORY],
        retailers=[retailer],
        credentials=None,
        minimum_daily_posts=minimum_daily_posts,
        bootstrap_target=bootstrap_target,
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
            self.repo, items, minimum_daily_posts=5, bootstrap_target=5
        )
        pipeline.run(item_count=2, regenerate_only=False)
        self.assertEqual(retailer.last_item_count, 5)
        self.assertGreaterEqual(len(self.repo.load_products()), 5)

    def test_bootstrap_target_drives_initial_pull(self) -> None:
        items = [make_item(idx) for idx in range(12)]
        pipeline, _, retailer = build_pipeline(
            self.repo,
            items,
            minimum_daily_posts=5,
            bootstrap_target=12,
        )
        pipeline.run(item_count=3, regenerate_only=False)
        self.assertEqual(retailer.last_item_count, 12)
        self.assertEqual(len(self.repo.load_products()), 12)

    def test_daily_quota_limits_new_products(self) -> None:
        items = [make_item(idx) for idx in range(10)]
        pipeline, _, retailer = build_pipeline(
            self.repo,
            items,
            minimum_daily_posts=5,
            bootstrap_target=5,
        )
        pipeline.run(item_count=10, regenerate_only=False)
        self.assertEqual(len(self.repo.load_products()), 5)

        retailer.items = [make_item(idx + 20) for idx in range(10)]
        pipeline.run(item_count=10, regenerate_only=False)
        self.assertEqual(len(self.repo.load_products()), 10)

    def test_quality_scoring_prioritizes_high_ratings(self) -> None:
        items = []
        for idx in range(10):
            item = make_item(idx)
            item["rating"] = 4.0 + idx * 0.1
            item["total_reviews"] = (idx + 1) * 20
            items.append(item)
        pipeline, _, _ = build_pipeline(
            self.repo,
            items,
            minimum_daily_posts=5,
            bootstrap_target=5,
        )
        pipeline.run(item_count=10, regenerate_only=False)
        stored = self.repo.load_products()
        self.assertEqual(len(stored), 5)
        asins = {product.asin for product in stored}
        self.assertEqual(asins, {f"ASIN{idx}" for idx in range(5, 10)})

    def test_missing_ratings_do_not_block_marketplace_diversity(self) -> None:
        amazon_items = [
            {
                "id": "AMAZON-1",
                "title": "Amazon Low Rated 1",
                "url": "https://example.com/amazon/1",
                "image": "https://example.com/images/amazon1.jpg",
                "price": "$14.99",
                "features": ["feature one", "feature two"],
                "rating": 0.05,
                "total_reviews": 0,
                "brand": "Amazon Basics",
            },
            {
                "id": "AMAZON-2",
                "title": "Amazon Low Rated 2",
                "url": "https://example.com/amazon/2",
                "image": "https://example.com/images/amazon2.jpg",
                "price": "$15.99",
                "features": ["feature three", "feature four"],
                "rating": 0.05,
                "total_reviews": 0,
                "brand": "Amazon Essentials",
            },
        ]
        ebay_items = [
            {
                "id": "EBAY-1",
                "title": "eBay Listing",
                "url": "https://example.com/ebay/1",
                "image": "https://example.com/images/ebay1.jpg",
                "price": "$18.99",
                "features": ["unique find", "limited stock"],
                "rating": None,
                "total_reviews": None,
                "brand": "Independent",
            }
        ]
        amazon_retailer = FakeRetailerAdapter(amazon_items)
        ebay_retailer = FakeRetailerAdapter(ebay_items)
        ebay_retailer.slug = "ebay"
        ebay_retailer.name = "eBay"
        ebay_retailer.homepage = "https://www.ebay.com/"
        pipeline = GiftPipeline(
            repository=self.repo,
            generator=DummyGenerator(),
            categories=[TEST_CATEGORY],
            retailers=[amazon_retailer, ebay_retailer],
            credentials=None,
            minimum_daily_posts=2,
            bootstrap_target=2,
        )
        pipeline.run(item_count=3, regenerate_only=False)
        products = self.repo.load_products()
        ebay_selected = [
            product for product in products if product.retailer_slug == "ebay"
        ]
        self.assertGreaterEqual(len(ebay_selected), 1)

    def test_reserves_slot_for_each_retailer_before_ranking(self) -> None:
        amazon_items = [
            {
                "id": "AMAZON-HIGH-1",
                "title": "Amazon Highly Rated",
                "url": "https://example.com/amazon/high",
                "image": "https://example.com/images/amazon-high.jpg",
                "price": "$24.99",
                "features": ["popular", "trusted"],
                "rating": 4.9,
                "total_reviews": 2200,
                "brand": "Amazon Premium",
            },
            {
                "id": "AMAZON-HIGH-2",
                "title": "Amazon Runner Up",
                "url": "https://example.com/amazon/runner",
                "image": "https://example.com/images/amazon-runner.jpg",
                "price": "$22.99",
                "features": ["popular", "reliable"],
                "rating": 4.8,
                "total_reviews": 1800,
                "brand": "Amazon Picks",
            },
        ]
        ebay_items = [
            {
                "id": "EBAY-LOW",
                "title": "eBay Underdog",
                "url": "https://example.com/ebay/underdog",
                "image": "https://example.com/images/ebay-low.jpg",
                "price": "$19.99",
                "features": ["vintage", "unique"],
                "rating": 1.0,
                "total_reviews": 2,
                "brand": "Independent",
            }
        ]

        amazon_retailer = FakeRetailerAdapter(amazon_items)
        ebay_retailer = FakeRetailerAdapter(ebay_items)
        ebay_retailer.slug = "ebay"
        ebay_retailer.name = "eBay"
        ebay_retailer.homepage = "https://www.ebay.com/"

        pipeline = GiftPipeline(
            repository=self.repo,
            generator=DummyGenerator(),
            categories=[TEST_CATEGORY],
            retailers=[amazon_retailer, ebay_retailer],
            credentials=None,
            minimum_daily_posts=3,
            bootstrap_target=3,
        )

        pipeline.run(item_count=5, regenerate_only=False)
        products = self.repo.load_products()

        self.assertEqual(len(products), 3)
        retailers = {product.retailer_slug for product in products}
        self.assertIn("amazon", retailers)
        self.assertIn("ebay", retailers)


def test_pipeline_generate_only_handles_article_repository(tmp_path: Path) -> None:
    data_file = tmp_path / "products.json"
    repo = ProductRepository(data_file=data_file)
    generator = DummyGenerator()
    article_repo = ArticleRepository(tmp_path / "articles.json")
    pipeline = GiftPipeline(
        repository=repo,
        generator=generator,
        categories=[TEST_CATEGORY],
        retailers=[],
        credentials=None,
        article_repository=article_repo,
    )

    result = pipeline.run(item_count=0, regenerate_only=True)

    assert result.products == []
    assert generator.calls == 1


if __name__ == "__main__":
    unittest.main()
