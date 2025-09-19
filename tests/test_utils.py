from __future__ import annotations

import unittest

from giftgrab.utils import apply_partner_tag, parse_price_string, slugify


class UtilsTests(unittest.TestCase):
    def test_slugify_generates_clean_url_component(self) -> None:
        self.assertEqual(
            slugify("The Ultimate Gift! 2024 Edition"),
            "the-ultimate-gift-2024-edition",
        )

    def test_apply_partner_tag_adds_tag_when_missing(self) -> None:
        url = "https://www.amazon.com/example-product?ref=123"
        result = apply_partner_tag(url, "myaffiliate-20")
        self.assertIn("tag=kayce25-20", result)
        self.assertTrue(result.startswith("https://www.amazon.com/example-product"))

    def test_apply_partner_tag_handles_none_url(self) -> None:
        result = apply_partner_tag(None, "myaffiliate-20")
        self.assertEqual(result, "https://www.amazon.com/?tag=kayce25-20")

    def test_parse_price_string_extracts_value_and_currency(self) -> None:
        parsed = parse_price_string("$129.99")
        self.assertEqual(parsed, (129.99, "USD"))

    def test_parse_price_string_handles_locale_format(self) -> None:
        parsed = parse_price_string("€1.234,50")
        self.assertEqual(parsed, (1234.5, "EUR"))


if __name__ == "__main__":
    unittest.main()
