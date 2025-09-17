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


def test_directory_feed_without_index(monkeypatch, tmp_path):
    retailers_dir = tmp_path / "retailers"
    items_dir = retailers_dir / "amazon-sitestripe" / "items"
    items_dir.mkdir(parents=True)

    item_payload = {
        "id": "asin999",
        "title": "Another Gift",
        "url": "https://example.com/products/asin999",
        "price": "$42.00",
        "features": ["delightful"],
        "rating": 4.9,
        "total_reviews": 230,
    }
    (items_dir / "asin999.json").write_text(json.dumps(item_payload), encoding="utf-8")

    meta_path = retailers_dir / "amazon-sitestripe" / "meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "name": "Directory Meta Only",
                "cta_label": "Shop this drop",
                "homepage": "https://example.com/amazon",
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
    assert items[0]["id"] == "asin999"
    assert items[0]["title"] == "Another Gift"

    assert adapter.name == "Directory Meta Only"
    assert adapter.cta_label == "Shop this drop"
    assert adapter.homepage == "https://example.com/amazon"


def test_rich_directory_items_survive_pointer_overrides(monkeypatch, tmp_path):
    retailers_dir = tmp_path / "retailers"
    pointer_path = retailers_dir / "curated.json"
    items_dir = retailers_dir / "curated" / "items"
    items_dir.mkdir(parents=True)

    detailed_payload = {
        "id": "asin555",
        "title": "Aurora Skyline Projector",
        "url": "https://example.com/products/asin555",
        "price": "$88.00",
        "image": "https://cdn.example.com/aurora.jpg",
        "features": ["immersive lighting", "smart home"],
        "rating": 4.9,
        "total_reviews": 420,
        "keywords": ["lighting", "party"],
        "category_slug": "home-and-kitchen",
        "category": "Homebody Upgrades",
    }
    (items_dir / "asin555.json").write_text(
        json.dumps(detailed_payload), encoding="utf-8"
    )

    pointer_payload = {
        "name": "Curated Feed",
        "homepage": "https://example.com",
        "items": [
            {
                "id": "asin555",
                "title": "Generic Pointer",
                "url": "https://example.com/pointer/asin555",
            }
        ],
    }
    pointer_path.write_text(json.dumps(pointer_payload), encoding="utf-8")

    monkeypatch.setenv("STATIC_RETAILER_DIR", str(retailers_dir))
    adapters = load_static_retailers()
    monkeypatch.delenv("STATIC_RETAILER_DIR", raising=False)

    assert len(adapters) == 1
    adapter = adapters[0]
    assert adapter.slug == "curated"

    items = adapter.search_items(keywords=[], item_count=5)
    assert len(items) == 1
    item = items[0]
    assert item["title"] == "Aurora Skyline Projector"
    assert item["image"] == "https://cdn.example.com/aurora.jpg"
    assert item["price"] == "$88.00"
    assert item["rating"] == 4.9
    assert item["url"] == "https://example.com/products/asin555"
    assert item["category_slug"] == "home-and-kitchen"
    assert sorted(item["features"]) == ["immersive lighting", "smart home"]
    assert sorted(item["keywords"]) == ["lighting", "party"]


def test_placeholder_title_replaced_by_shorter_curated_value(monkeypatch, tmp_path):
    retailers_dir = tmp_path / "retailers"
    retailers_dir.mkdir()
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir()

    pointer_path = retailers_dir / "curated.json"
    curated_file = resources_dir / "curated-item.json"

    curated_payload = {
        "id": "asin777",
        "title": "Cozy Mug",
        "url": "https://example.com/products/asin777",
        "image": "https://cdn.example.com/mug.jpg",
    }
    curated_file.write_text(json.dumps(curated_payload), encoding="utf-8")

    pointer_payload = {
        "items": [
            {
                "id": "asin777",
                "url": "https://example.com/pointer/asin777",
            }
        ],
        "items_file": "../resources/curated-item.json",
    }
    pointer_path.write_text(json.dumps(pointer_payload), encoding="utf-8")

    monkeypatch.setenv("STATIC_RETAILER_DIR", str(retailers_dir))
    adapters = load_static_retailers()
    monkeypatch.delenv("STATIC_RETAILER_DIR", raising=False)

    assert len(adapters) == 1
    adapter = adapters[0]
    items = adapter.search_items(keywords=[], item_count=5)

    assert len(items) == 1
    item = items[0]
    assert item["title"] == "Cozy Mug"
    assert item["title"] != "Grab Gifts marketplace find"


def test_amazon_placeholder_images_are_resolved(monkeypatch, tmp_path):
    retailers_dir = tmp_path / "retailers"
    items_dir = retailers_dir / "amazon-sitestripe" / "items"
    items_dir.mkdir(parents=True)

    item_payload = {
        "id": "amzn-abc123",
        "title": "Placeholder Gadget",
        "url": "https://amzn.to/abc123",
        "image": "/assets/amazon-sitestripe/amzn-abc123.svg",
    }
    (items_dir / "amzn-abc123.json").write_text(
        json.dumps(item_payload), encoding="utf-8"
    )

    resolved_url = "https://m.media-amazon.com/images/I/placeholder.jpg"

    def fake_resolver(url: str, *, timeout: int = 15) -> str | None:  # pragma: no cover - deterministic stub
        assert url == "https://amzn.to/abc123"
        return resolved_url

    monkeypatch.setattr(
        "giftgrab.retailers.resolve_amazon_image_url", fake_resolver
    )
    monkeypatch.setenv("STATIC_RETAILER_DIR", str(retailers_dir))

    adapters = load_static_retailers()

    monkeypatch.delenv("STATIC_RETAILER_DIR", raising=False)

    assert len(adapters) == 1
    items = adapters[0].search_items(keywords=[], item_count=5)
    assert len(items) == 1
    assert items[0]["image"] == resolved_url


def test_amazon_placeholder_entries_are_dropped_when_image_unresolved(
    monkeypatch, tmp_path
):
    retailers_dir = tmp_path / "retailers"
    items_dir = retailers_dir / "amazon-sitestripe" / "items"
    items_dir.mkdir(parents=True)

    item_payload = {
        "id": "amzn-dropme",
        "title": "Unresolvable Placeholder",
        "url": "https://amzn.to/dropme",
        "image": "/assets/amazon-sitestripe/amzn-dropme.svg",
    }
    (items_dir / "amzn-dropme.json").write_text(
        json.dumps(item_payload), encoding="utf-8"
    )

    def fake_resolver(url: str, *, timeout: int = 15) -> str | None:
        assert url == "https://amzn.to/dropme"
        return None

    monkeypatch.setattr(
        "giftgrab.retailers.resolve_amazon_image_url", fake_resolver
    )
    monkeypatch.setenv("STATIC_RETAILER_DIR", str(retailers_dir))

    adapters = load_static_retailers()

    monkeypatch.delenv("STATIC_RETAILER_DIR", raising=False)

    assert len(adapters) == 1
    items = adapters[0].search_items(keywords=[], item_count=5)
    assert items == []
