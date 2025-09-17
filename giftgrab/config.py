"""Configuration helpers for the giftgrab site generator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "public"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class SiteSettings:
    """Global site level settings used during generation."""

    site_name: str = "Curated Gift Radar"
    base_url: str = "https://example.com"
    description: str = (
        "Daily hand-picked Amazon gift ideas organized into intuitive categories."
    )
    adsense_client_id: str | None = None
    adsense_slot: str | None = None
    adsense_rail_slot: str | None = None
    amazon_partner_tag: str | None = None
    twitter_handle: str | None = None
    facebook_page: str | None = None
    keywords: tuple[str, ...] = ()
    newsletter_url: str | None = None
    contact_email: str | None = None
    language: str = "en"
    locale: str = "en_US"
    logo_url: str | None = None
    favicon_url: str | None = None
    analytics_measurement_id: str | None = None
    analytics_snippet: str | None = None
    newsletter_form_action: str | None = None
    newsletter_form_method: str = "post"
    newsletter_form_email_field: str = "email"
    newsletter_form_hidden_inputs: tuple[tuple[str, str], ...] = ()
    newsletter_cta_copy: str | None = None


@dataclass(frozen=True)
class CategoryDefinition:
    """A configured category that new gifts are sorted into."""

    slug: str
    name: str
    keywords: List[str]
    blurb: str


DEFAULT_CATEGORIES: List[CategoryDefinition] = [
    CategoryDefinition(
        slug="gifts-for-him",
        name="Gifts for Him",
        keywords=["men", "dad gifts", "boyfriend", "brother", "husband"],
        blurb="Bold, useful, and entertaining picks that guys actually want.",
    ),
    CategoryDefinition(
        slug="gifts-for-her",
        name="Gifts for Her",
        keywords=["women", "mom gifts", "girlfriend", "sister", "wife"],
        blurb="Thoughtful surprises guaranteed to score serious brownie points.",
    ),
    CategoryDefinition(
        slug="tech-and-gadgets",
        name="Tech & Gadgets",
        keywords=["tech gadgets", "electronics", "smart home", "innovation"],
        blurb="Cutting-edge devices for the tech obsessed early adopter.",
    ),
    CategoryDefinition(
        slug="home-and-kitchen",
        name="Home & Kitchen",
        keywords=["home", "kitchen", "decor", "entertaining", "cooking"],
        blurb="Stylish essentials to upgrade every cozy corner and culinary adventure.",
    ),
    CategoryDefinition(
        slug="outdoors-and-adventure",
        name="Outdoors & Adventure",
        keywords=["outdoor", "camping", "hiking", "travel", "adventure"],
        blurb="Trail-tested gear for explorers who never stay inside for long.",
    ),
    CategoryDefinition(
        slug="fitness-and-wellness",
        name="Fitness & Wellness",
        keywords=["fitness", "wellness", "health", "yoga", "athlete"],
        blurb="Wellness boosters that make staying active actually fun.",
    ),
    CategoryDefinition(
        slug="office-and-productivity",
        name="Office & Productivity",
        keywords=["office", "work", "productivity", "desk", "remote work"],
        blurb="Clever upgrades that supercharge any workspace or side hustle.",
    ),
    CategoryDefinition(
        slug="entertainment-and-games",
        name="Entertainment & Games",
        keywords=["games", "board game", "entertainment", "movie", "music"],
        blurb="Party-starting picks for gamers, streamers, and pop-culture fans.",
    ),
    CategoryDefinition(
        slug="kids-and-family",
        name="Kids & Family",
        keywords=["kids", "toys", "family", "learning", "STEM"],
        blurb="Playful discoveries that wow kids and keep the whole crew smiling.",
    ),
    CategoryDefinition(
        slug="stocking-stuffers",
        name="Stocking Stuffers",
        keywords=["stocking stuffer", "mini", "under 25", "gift exchange"],
        blurb="Small-in-size but huge-in-delight surprises for any holiday list.",
    ),
]


def ensure_directories() -> None:
    """Create the default data and output directories if missing."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
