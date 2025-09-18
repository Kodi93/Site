from giftgrab.quality import SeoPayload, passes_seo
from giftgrab.text import (
    IntroParams,
    MetaParams,
    TitleParams,
    make_intro,
    make_meta,
    make_title,
)


def test_make_meta_hits_target_lengths_and_phrases():
    meta = make_meta(
        MetaParams(
            name="Echo Dot Kids Edition",
            price=39.99,
            currency="USD",
            specs=["Alexa built-in", "kid friendly design", "parental controls"],
            use="Kids rooms",
        )
    )
    assert 140 <= len(meta) <= 155
    assert "Check 40 USD before you buy" in meta
    assert "free shipping" not in meta.lower()


def test_make_title_dedupes_brand_and_cleans_text():
    title = make_title(
        TitleParams(
            name="Galaxy Buds Pro",
            brand="Samsung",
            model="Noise Cancelling",
            category="Audio",
        )
    )
    assert "Samsung" in title
    assert "Noise Cancelling" in title
    assert len(title) <= 60


def test_make_intro_matches_expected_tone():
    intro = make_intro(
        IntroParams(title="Compact Projector", use="Backyard movie nights", price=299.99)
    )
    assert intro.endswith("Highlights and trade-offs below.")
    assert "backyard movie nights" in intro.lower()


def test_passes_seo_enforces_title_description_and_body_requirements():
    body = " ".join(["detail"] * 140)
    valid_meta = make_meta(
        MetaParams(name="Gifting Pick", price=120.0, specs=["Compact", "Portable"], use="Travel")
    )
    good_payload = SeoPayload(title=make_title(TitleParams(name="Gifting Pick", category="Travel")), description=valid_meta, body=body)
    assert passes_seo(good_payload)

    failing_title = SeoPayload(title="Buy now gadget", description=valid_meta, body=body)
    assert not passes_seo(failing_title)

    failing_description = SeoPayload(
        title=good_payload.title,
        description="Too short",
        body=body,
    )
    assert not passes_seo(failing_description)

    failing_body = SeoPayload(
        title=good_payload.title,
        description=good_payload.description,
        body="Not enough",
    )
    assert not passes_seo(failing_body)
