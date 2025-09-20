from giftgrab.models import Product


def test_product_from_dict_strips_placeholder_images():
    placeholder = Product.from_dict(
        {
            "id": "demo-placeholder",
            "title": "Placeholder Item",
            "url": "https://example.com/placeholder",
            "image": "/assets/amazon-sitestripe/placeholder.svg",
        }
    )
    assert placeholder.image is None

    real = Product.from_dict(
        {
            "id": "demo-real",
            "title": "Real Item",
            "url": "https://example.com/real",
            "image": "https://cdn.example.com/assets/real.jpg",
        }
    )
    assert real.image == "https://cdn.example.com/assets/real.jpg"
