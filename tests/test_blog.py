from __future__ import annotations

import unittest

from giftgrab.blog import generate_blog_post
from giftgrab.models import Product


def sample_product() -> Product:
    return Product(
        asin="B000TEST",
        title="Gravity-Defying Coffee Mug",
        link="https://www.amazon.com/example?tag=mytag-20",
        image="https://images.example.com/mug.jpg",
        price="$24.99",
        rating=4.7,
        total_reviews=1280,
        category_slug="home-and-kitchen",
        keywords=["coffee", "mug", "novelty"],
    )


class BlogTests(unittest.TestCase):
    def test_generate_blog_post_builds_rich_html(self) -> None:
        product = sample_product()
        blog = generate_blog_post(product, "Home & Kitchen", ["Levitating design", "USB-powered base"])
        self.assertIn("Gravity-Defying Coffee Mug", blog.summary)
        self.assertIn("Levitating design", blog.html)
        self.assertIn("cta-button", blog.html)
        self.assertTrue("Check it out" in blog.html or "See the latest price" in blog.html)

    def test_generate_blog_post_includes_review_callout(self) -> None:
        product = sample_product()
        blog = generate_blog_post(product, "Home & Kitchen", [])
        self.assertIn("Rated 4.7 stars by 1,280 shoppers.", blog.html)


if __name__ == "__main__":
    unittest.main()
