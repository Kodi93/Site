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

    site_name: str = "Grab Gifts"
    base_url: str = "https://grabgifts.net"
    description: str = (
        "Grab Gifts surfaces viral-ready Amazon finds with conversion copy and plug-and-play affiliate automation."
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
        name="For Him",
        keywords=["men", "dad gifts", "boyfriend", "brother", "husband"],
        blurb="Bold, useful, and entertaining picks that guys actually want.",
    ),
    CategoryDefinition(
        slug="gifts-for-her",
        name="For Her",
        keywords=["women", "mom gifts", "girlfriend", "sister", "wife"],
        blurb="Thoughtful surprises guaranteed to score serious brownie points.",
    ),
    CategoryDefinition(
        slug="tech-and-gadgets",
        name="For a Techy",
        keywords=["tech gadgets", "electronics", "smart home", "innovation", "techie", "geek"],
        blurb="Cutting-edge devices and geeky upgrades for the resident technologist.",
    ),
    CategoryDefinition(
        slug="entertainment-and-games",
        name="For Gamers",
        keywords=["gaming", "gamer", "streamer", "pc gaming", "console", "esports"],
        blurb="Level-boosting gear, setups, and collectibles built for serious players.",
    ),
    CategoryDefinition(
        slug="fandom-and-collectibles",
        name="For Fandom",
        keywords=["anime", "manga", "cosplay", "collectibles", "series", "fandom"],
        blurb="Limited runs, cosplay essentials, and shelf candy for devoted superfans.",
    ),
    CategoryDefinition(
        slug="home-and-kitchen",
        name="Homebody Upgrades",
        keywords=["home", "kitchen", "decor", "entertaining", "cooking", "cozy"],
        blurb="Stylish essentials to upgrade every cozy corner and culinary adventure.",
    ),
    CategoryDefinition(
        slug="outdoors-and-adventure",
        name="For Adventurers",
        keywords=["outdoor", "camping", "hiking", "travel", "adventure", "explorer"],
        blurb="Trail-tested gear for explorers who never stay inside for long.",
    ),
    CategoryDefinition(
        slug="fitness-and-wellness",
        name="Wellness Warriors",
        keywords=["fitness", "wellness", "health", "yoga", "athlete", "recovery"],
        blurb="Wellness boosters that make staying active actually fun.",
    ),
    CategoryDefinition(
        slug="office-and-productivity",
        name="Productivity Power-Ups",
        keywords=["office", "work", "productivity", "desk", "remote work", "entrepreneur"],
        blurb="Clever upgrades that supercharge any workspace or side hustle.",
    ),
    CategoryDefinition(
        slug="kids-and-family",
        name="Family Time",
        keywords=["kids", "toys", "family", "learning", "STEM", "parenting"],
        blurb="Playful discoveries that wow kids and keep the whole crew smiling.",
    ),
]


def ensure_directories() -> None:
    """Create the default data and output directories if missing."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
