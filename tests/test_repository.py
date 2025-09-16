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


if __name__ == "__main__":
    unittest.main()
