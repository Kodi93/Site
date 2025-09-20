from giftgrab.content_gen import _build_blurb
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
