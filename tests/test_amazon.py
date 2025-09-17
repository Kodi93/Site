import unittest

from giftgrab.amazon import AmazonCredentials, AmazonProductClient


class AmazonProductClientImageTests(unittest.TestCase):
    def setUp(self) -> None:
        credentials = AmazonCredentials(
            access_key="test-access",
            secret_key="test-secret",
            partner_tag="test-tag",
        )
        self.client = AmazonProductClient(credentials)

    def test_parse_items_uses_small_image_when_only_size_available(self) -> None:
        data = {
            "SearchResult": {
                "Items": [
                    {
                        "ASIN": "SMALLASIN",
                        "DetailPageURL": "https://example.com/product",
                        "Images": {
                            "Primary": {
                                "Small": {
                                    "URL": "https://example.com/small.jpg",
                                }
                            }
                        },
                        "ItemInfo": {
                            "Title": {"DisplayValue": "Sample"},
                        },
                    }
                ]
            }
        }

        parsed = self.client._parse_items(data)

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["image_url"], "https://example.com/small.jpg")


if __name__ == "__main__":
    unittest.main()
