import json

import pytest

import giftgrab.ebay as ebay_module
from giftgrab.ebay import EbayCredentials, EbayProductClient
from giftgrab.retailers import EbayRetailerAdapter


class DummyResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - no cleanup needed
        return False


def test_ebay_adapter_normalizes_results(monkeypatch):
    credentials = EbayCredentials(
        client_id="id",
        client_secret="secret",
        developer_id="dev",
        affiliate_campaign_id="123456",
    )
    client = EbayProductClient(credentials)
    adapter = EbayRetailerAdapter(credentials)
    adapter.client = client

    token_payload = {"access_token": "token", "expires_in": 7200}
    search_payload = {
        "itemSummaries": [
            {
                "itemId": "v1|123|0",
                "title": "Glow-in-the-dark throw blanket",
                "itemWebUrl": "https://www.ebay.com/itm/123",
                "image": {"imageUrl": "https://i.ebayimg.com/images/g/abc.jpg"},
                "price": {"value": "19.99", "currency": "USD"},
                "shortDescription": "Cozy fleece\nMachine washable",
                "reviewRating": {"averageRating": "4.6", "ratingCount": 27},
                "brand": "CozyCo",
                "categoryPath": "Home & Garden > Bedding",
                "localizedAspects": [
                    {"name": "Color", "value": "Blue"},
                    {"name": "Size", "value": "60x80"},
                ],
            }
        ]
    }

    calls: list[dict] = []
    urls: list[str] = []
    responses = [token_payload, search_payload]

    def fake_urlopen(request, timeout=0):
        if not responses:
            raise AssertionError("Unexpected extra HTTP call")
        headers = {key.lower(): value for key, value in request.header_items()}
        calls.append(headers)
        urls.append(request.full_url)
        payload = responses.pop(0)
        return DummyResponse(payload)

    monkeypatch.setattr(ebay_module, "urlopen", fake_urlopen)

    items = adapter.search_items(keywords=("cozy", "blanket"), item_count=3)

    assert urls[0] == ebay_module._TOKEN_URL
    assert ebay_module._SEARCH_URL in urls[1]
    assert calls[0]["x-ebay-c-dev-id"] == "dev"
    assert calls[1]["authorization"] == "Bearer token"
    assert calls[1]["x-ebay-c-dev-id"] == "dev"

    assert len(items) == 1
    item = items[0]
    assert item["id"] == "v1|123|0"
    assert item["title"].startswith("Glow-in-the-dark")
    assert item["url"] == "https://www.ebay.com/itm/123"
    assert item["image"] == "https://i.ebayimg.com/images/g/abc.jpg"
    assert item["price"] == "$19.99"
    assert "Color: Blue" in item["features"]
    assert "Cozy fleece" in item["features"]
    assert pytest.approx(item["rating"], rel=1e-6) == 4.6
    assert item["total_reviews"] == 27
    assert item["brand"] == "CozyCo"
    assert set(item["keywords"]) >= {"Home & Garden", "Bedding", "CozyCo"}
    assert item["category_slug"] == "bedding"


def test_ebay_decorate_url_preserves_affiliate_params():
    credentials = EbayCredentials(
        client_id="id",
        client_secret="secret",
        developer_id="dev",
        affiliate_campaign_id="654321",
    )
    adapter = EbayRetailerAdapter(credentials)

    decorated = adapter.decorate_url("https://www.ebay.com/itm/123?foo=bar")
    assert "foo=bar" in decorated
    assert "campid=654321" in decorated

    homepage_decorated = adapter.decorate_url(None)
    assert homepage_decorated.startswith("https://www.ebay.com/")
    assert "campid=654321" in homepage_decorated

    no_campaign = EbayRetailerAdapter(
        EbayCredentials("id", "secret", "dev", affiliate_campaign_id=None)
    )
    assert (
        no_campaign.decorate_url("https://www.ebay.com/itm/456?foo=bar")
        == "https://www.ebay.com/itm/456?foo=bar"
    )
