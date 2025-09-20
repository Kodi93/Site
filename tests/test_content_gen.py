from giftgrab.content_gen import _build_blurb, _build_items, _build_specs
from giftgrab.models import Product


def make_product(**overrides) -> Product:
    defaults = dict(
        id="example-1",
        title="NestCo Cozy Throw Blanket",
        url="https://example.com/products/cozy-throw",
        image=None,
        price=58.0,
        price_text="$58.00",
        currency="USD",
        brand="NestCo",
        category="Cozy Home",
        rating=4.7,
        rating_count=320,
        source="curated",
    )
    defaults.update(overrides)
    return Product(**defaults)


def test_build_blurb_balances_length_and_details():
    product = make_product()
    setattr(product, "keywords", ["plush cotton", "reversible", "quick ship"])

    blurb = _build_blurb(product, context="romance-forward surprises")

    assert 120 <= len(blurb) <= 160
    assert "romance-forward surprises" in blurb
    assert "4.7/5" in blurb
    assert "$58.00" in blurb


def test_build_blurb_handles_sparse_metadata():
    product = make_product(
        price=None,
        price_text=None,
        rating=None,
        rating_count=None,
        title="TrailSet Mini Repair Kit",
    )
    setattr(product, "keywords", [])

    blurb = _build_blurb(product, context="clever stocking stuffers")

    assert 120 <= len(blurb) <= 160
    assert "clever stocking stuffers" in blurb
    assert "Check the latest listing" in blurb
    assert "TrailSet Mini Repair Kit" in blurb


def test_build_specs_uses_source_fallback_for_retailer():
    product = make_product()

    specs = _build_specs(product)

    assert "Price:" in specs[0]
    assert "Retailer: Curated" in specs


def test_build_specs_prefers_explicit_retailer_name():
    product = make_product()
    setattr(product, "retailer_name", "Acme Gifts")

    specs = _build_specs(product)

    assert "Retailer: Acme Gifts" in specs
    assert "Retailer: Curated" not in specs


def test_build_items_falls_back_to_product_url_when_link_missing():
    product = make_product()
    setattr(product, "keywords", ["cozy", "cotton"])

    items = _build_items([product], context="cozy nights")

    assert len(items) == 1
    assert items[0].outbound_url == product.url


def test_build_items_prefers_explicit_product_link():
    product = make_product()
    setattr(product, "link", "https://example.com/redirect/cozy-throw")

    items = _build_items([product], context="cozy nights")

    assert items[0].outbound_url == "https://example.com/redirect/cozy-throw"
