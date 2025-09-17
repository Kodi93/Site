import json

from giftgrab.cli import load_static_retailers


def test_directory_feed_with_index(monkeypatch, tmp_path):
    retailers_dir = tmp_path / "retailers"
    index_path = retailers_dir / "amazon-sitestripe.json"
    items_dir = retailers_dir / "amazon-sitestripe" / "items"
    items_dir.mkdir(parents=True)

    item_payload = {
        "id": "asin123",
        "title": "Sample Gift",
        "url": "https://example.com/products/asin123",
        "price": "$19.99",
        "features": ["festive"],
        "rating": 4.6,
        "total_reviews": 87,
        "category_slug": "gifts-for-him",
        "category": "For Him",
    }
    (items_dir / "asin123.json").write_text(json.dumps(item_payload), encoding="utf-8")

    meta_path = retailers_dir / "amazon-sitestripe" / "meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "name": "Directory Meta Name",
                "cta_label": "Shop everything",
            }
        ),
        encoding="utf-8",
    )

    index_path.write_text(
        json.dumps(
            {
                "name": "Amazon SiteStripe Picks",
                "cta_label": "Shop on Amazon",
                "homepage": "https://www.amazon.com/",
                "items_dir": "./amazon-sitestripe/items",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("STATIC_RETAILER_DIR", str(retailers_dir))
    adapters = load_static_retailers()
    monkeypatch.delenv("STATIC_RETAILER_DIR", raising=False)

    assert len(adapters) == 1
    adapter = adapters[0]
    assert adapter.slug == "amazon-sitestripe"

    items = adapter.search_items(keywords=[], item_count=5)
    assert len(items) == 1
    assert items[0]["id"] == "asin123"
    assert items[0]["category_slug"] == "gifts-for-him"

    assert adapter.name == "Amazon SiteStripe Picks"
    assert adapter.cta_label == "Shop on Amazon"
    assert adapter.homepage == "https://www.amazon.com/"
