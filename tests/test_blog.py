from __future__ import annotations

import unittest

from giftgrab.blog import (
    build_category_phrase,
    generate_blog_post,
    generate_summary,
)
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
    def test_build_category_phrase_for_audience_categories(self) -> None:
        self.assertEqual(build_category_phrase("For Him"), "the perfect gift for him")
        self.assertEqual(
            build_category_phrase("For a Techy"),
            "the perfect gift for tech enthusiasts",
        )

    def test_build_category_phrase_handles_homebody_upgrades(self) -> None:
        self.assertEqual(
            build_category_phrase("Homebody Upgrades"),
            "a homebody upgrade they'll appreciate",
        )

    def test_build_category_phrase_converts_concept_audiences(self) -> None:
        self.assertEqual(
            build_category_phrase("For Fandom"),
            "the perfect gift for devoted superfans",
        )

    def test_build_category_phrase_handles_family_time(self) -> None:
        self.assertEqual(
            build_category_phrase("Family Time"),
            "a thoughtful pick for family time together",
        )

    def test_build_category_phrase_default_fallback(self) -> None:
        self.assertEqual(
            build_category_phrase("Holiday Heroes"),
            "a holiday heroes pick worth gifting",
        )

    def test_generate_blog_post_builds_rich_html(self) -> None:
        product = sample_product()
        blog = generate_blog_post(product, "Home & Kitchen", ["Levitating design", "USB-powered base"])
        self.assertIn("Gravity-Defying Coffee Mug", blog.summary)
        self.assertIn("Levitating design", blog.summary)
        self.assertIn("Key takeaways", blog.html)
        self.assertIn("Good for:", blog.html)
        self.assertIn("Consider:", blog.html)
        self.assertIn("campaign-playbook", blog.html)
        self.assertIn("Launch checklist", blog.html)
        self.assertIn("cta-button", blog.html)
        self.assertIn("Review the listing on Amazon", blog.html)

    def test_generate_blog_post_includes_review_callout(self) -> None:
        product = sample_product()
        blog = generate_blog_post(product, "Home & Kitchen", [])
        self.assertIn("Rated 4.7 stars by 1,280 shoppers.", blog.html)

    def test_generate_summary_prefers_features_when_available(self) -> None:
        product = sample_product()
        summary = generate_summary(
            product,
            "Homebody Upgrades",
            ["Levitating design", "USB-powered base", "USB-powered base"],
        )
        self.assertIn("For homebody upgrades.", summary)
        self.assertIn("Levitating design, USB-powered base", summary)
        self.assertIn("See highlights inside.", summary)

    def test_generate_summary_falls_back_to_keywords(self) -> None:
        product = sample_product()
        summary = generate_summary(product, "Homebody Upgrades", [])
        self.assertIn("coffee, novelty", summary)
        self.assertIn("We outline trade-offs.", summary)

    def test_generate_summary_handles_missing_highlights(self) -> None:
        product = sample_product()
        product.keywords = []
        summary = generate_summary(product, "Homebody Upgrades", [])
        self.assertIn("key features", summary)
        self.assertIn("We outline trade-offs.", summary)


if __name__ == "__main__":
    unittest.main()
