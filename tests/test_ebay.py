import json

import pytest

from giftgrab import ebay


class DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_search_parses_items(monkeypatch):
    payload = {
        "itemSummaries": [
            {
                "itemId": "123",
                "title": "Coffee Grinder",
                "itemWebUrl": "https://www.ebay.com/itm/123",
                "image": {"imageUrl": "https://example.com/image.jpg"},
                "price": {"value": "19.99", "currency": "USD"},
                "brand": {"value": "Acme"},
                "categoryPath": "Home > Kitchen > Coffee",
            }
        ]
    }

    def fake_urlopen(request, timeout=0):
        assert request.full_url.startswith(ebay.SEARCH_URL)
        assert "q=coffee" in request.full_url
        assert "limit=5" in request.full_url
        headers = {key.lower(): value for key, value in request.header_items()}
        assert headers["authorization"] == "Bearer token"
        assert headers["x-ebay-c-marketplace-id"] == "EBAY_GB"
        return DummyResponse(payload)

    monkeypatch.setattr(ebay, "urlopen", fake_urlopen)

    results = ebay.search("coffee", limit=5, token="token", marketplace_id="EBAY_GB")
    assert len(results) == 1
    item = results[0]
    assert item["id"] == "123"
    assert item["price"] == pytest.approx(19.99)
    assert item["price_text"] == "$19.99"
    assert item["category"] == "Coffee"
    assert item["brand"] == "Acme"


def test_get_token_without_credentials(monkeypatch):
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    assert ebay.get_token() is None
