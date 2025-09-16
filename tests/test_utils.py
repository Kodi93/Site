from __future__ import annotations

import unittest

from giftgrab.pipeline import ensure_partner_tag
from giftgrab.utils import slugify


class UtilsTests(unittest.TestCase):
    def test_slugify_generates_clean_url_component(self) -> None:
        self.assertEqual(
            slugify("The Ultimate Gift! 2024 Edition"),
            "the-ultimate-gift-2024-edition",
        )

    def test_ensure_partner_tag_adds_tag_when_missing(self) -> None:
        url = "https://www.amazon.com/example-product?ref=123"
        result = ensure_partner_tag(url, "myaffiliate-20")
        self.assertIn("tag=myaffiliate-20", result)
        self.assertTrue(result.startswith("https://www.amazon.com/example-product"))

    def test_ensure_partner_tag_handles_none_url(self) -> None:
        result = ensure_partner_tag(None, "myaffiliate-20")
        self.assertEqual(result, "https://www.amazon.com/")


if __name__ == "__main__":
    unittest.main()
