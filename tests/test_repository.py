from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from giftgrab.models import Product
from giftgrab.repository import ProductRepository


def make_product(asin: str) -> Product:
    return Product(
        asin=asin,
        title=f"Test Product {asin}",
        link="https://www.amazon.com/dp/example",
        image=None,
        price=None,
        rating=None,
        total_reviews=None,
        category_slug="tech-and-gadgets",
        keywords=["tech"],
    )


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        data_file = Path(self.temp_dir.name) / "products.json"
        self.repo = ProductRepository(data_file=data_file)

    def test_repository_round_trip(self) -> None:
        product = make_product("ASIN001")
        self.repo.upsert_products([product])
        stored = self.repo.load_products()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].asin, "ASIN001")

    def test_upsert_updates_existing_record(self) -> None:
        product = make_product("ASIN002")
        self.repo.upsert_products([product])
        product.title = "Updated Title"
        self.repo.upsert_products([product])
        stored = self.repo.load_products()
        self.assertEqual(stored[0].title, "Updated Title")

    def test_price_history_tracks_changes(self) -> None:
        product = make_product("ASIN003")
        product.price = "$19.99"
        self.repo.upsert_products([product])
        product.price = "$17.99"
        self.repo.upsert_products([product])
        stored = self.repo.load_products()[0]
        self.assertGreaterEqual(len(stored.price_history), 2)
        latest = stored.price_history[-1]
        self.assertAlmostEqual(latest.amount, 17.99, places=2)
        self.assertEqual(latest.display, "$17.99")

    def test_separate_records_for_each_retailer(self) -> None:
        amazon_product = make_product("ASIN004")
        amazon_product.price = "$49.00"
        other_product = make_product("ASIN004")
        other_product.retailer_slug = "walmart"
        other_product.retailer_name = "Walmart"
        other_product.link = "https://www.walmart.com/ip/example"
        other_product.price = "$45.00"
        self.repo.upsert_products([amazon_product, other_product])
        stored = sorted(
            self.repo.load_products(), key=lambda item: item.retailer_slug
        )
        self.assertEqual(len(stored), 2)
        self.assertEqual(stored[0].retailer_slug, "amazon")
        self.assertEqual(stored[1].retailer_slug, "walmart")
        self.assertEqual(stored[1].price_history[-1].display, "$45.00")


if __name__ == "__main__":
    unittest.main()
