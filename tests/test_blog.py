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
 codex/revise-product-titles-and-descriptions-n6synj
            build_category_phrase("For a Techy"),
            "the perfect gift for tech enthusiasts",

            build_category_phrase("For a Techy"),< codex/revise-product-titles-and-descriptions-nopw04
            "the perfect gift for tech enthusiasts",

            "the perfect gift for a techy",
 main
 main
        )

    def test_build_category_phrase_handles_homebody_upgrades(self) -> None:
        self.assertEqual(
            build_category_phrase("Homebody Upgrades"),
<<< codex/revise-product-titles-and-descriptions-n6synj

 codex/revise-product-titles-and-descriptions-nopw04
 main
            "a homebody upgrade they'll appreciate",
        )

    def test_build_category_phrase_converts_concept_audiences(self) -> None:
        self.assertEqual(
            build_category_phrase("For Fandom"),
            "the perfect gift for devoted superfans",
<< codex/revise-product-titles-and-descriptions-n6synj
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

=
            "a homebody upgrade worth gifting",
main
>>main
        )

    def test_generate_blog_post_builds_rich_html(self) -> None:
        product = sample_product()
        blog = generate_blog_post(product, "Home & Kitchen", ["Levitating design", "USB-powered base"])
        self.assertIn("Gravity-Defying Coffee Mug", blog.summary)
        self.assertIn("Levitating design", blog.summary)
        self.assertIn("Key takeaways", blog.html)
        self.assertIn("Good for:", blog.html)
        self.assertIn("Consider:", blog.html)
        self.assertIn("cta-button", blog.html)
<<<< codex/revise-product-titles-and-descriptions-n6synj
        self.assertIn("Review the listing on Amazon", blog.html)====
        self.assertTrue(
            "View full details" in blog.html or "Check current pricing" in blog.html
        )
> main

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
<< codex/revise-product-titles-and-descriptions-n6synj
        self.assertIn("Homebody Upgrades planners can rely on", summary)
        self.assertIn("Levitating design and USB-powered base", summary)
====
        self.assertIn("levitating design", summary)
        self.assertIn("USB-powered base", summary)
>>> main
        self.assertNotIn("coffee", summary)

    def test_generate_summary_falls_back_to_keywords(self) -> None:
        product = sample_product()
        summary = generate_summary(product, "Homebody Upgrades", [])
<<< codex/revise-product-titles-and-descriptions-n6synj
        self.assertIn("coffee and novelty", summary)
        self.assertIn("Check pricing", summary)
        self.assertIn("confirm availability", summary)

    def test_generate_summary_handles_missing_highlights(self) -> None:
        product = sample_product()
        product.keywords = []
        summary = generate_summary(product, "Homebody Upgrades", [])
        self.assertIn("practical performance", summary)
        self.assertIn("Confirm assets", summary)
====
        self.assertIn("coffee", summary)
        self.assertIn("novelty", summary)
>>> main


if __name__ == "__main__":
    unittest.main()
