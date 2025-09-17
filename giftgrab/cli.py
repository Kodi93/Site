"""Command line entry point for running the automation pipeline."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qsl

from .amazon import AmazonCredentials
from .config import DEFAULT_CATEGORIES, DATA_DIR, OUTPUT_DIR, SiteSettings, ensure_directories
from .generator import SiteGenerator
from .pipeline import GiftPipeline
from .repository import ProductRepository
from .retailers import AmazonRetailerAdapter, StaticRetailerAdapter
from .utils import load_json

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automate the curated Amazon gift site generation.",
    )
    parser.add_argument(
        "command",
        choices=["update", "generate"],
        help="Use 'update' to fetch new products and rebuild, or 'generate' to rebuild from stored data.",
    )
    parser.add_argument(
        "--item-count",
        type=int,
        default=6,
        help="Number of products to request per category when fetching from Amazon.",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=DATA_DIR / "products.json",
        help="Override the products JSON file location.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory where the static site files will be written.",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Set the log level (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser


def load_site_settings() -> SiteSettings:
    keywords_env = os.getenv("SITE_KEYWORDS")
    keywords: tuple[str, ...] = ()
    if keywords_env:
        keywords = tuple(
            keyword.strip()
            for keyword in keywords_env.split(",")
            if keyword.strip()
        )
    def optional_env(name: str) -> str | None:
        value = os.getenv(name)
        if value is None:
            return None
        value = value.strip()
        return value or None

    analytics_snippet_env = os.getenv("SITE_ANALYTICS_SNIPPET")
    analytics_snippet = None
    if analytics_snippet_env and analytics_snippet_env.strip():
        analytics_snippet = analytics_snippet_env

    hidden_inputs_env = os.getenv("SITE_NEWSLETTER_HIDDEN_INPUTS")
    hidden_inputs: tuple[tuple[str, str], ...] = ()
    if hidden_inputs_env:
        pairs = [
            (name, value)
            for name, value in parse_qsl(hidden_inputs_env, keep_blank_values=True)
            if name
        ]
        hidden_inputs = tuple(pairs)

    raw_method = optional_env("SITE_NEWSLETTER_FORM_METHOD")
    newsletter_method = (raw_method or "post").lower()
    if newsletter_method not in {"get", "post"}:
        newsletter_method = "post"

    email_field = optional_env("SITE_NEWSLETTER_EMAIL_FIELD") or "email"
    return SiteSettings(
        site_name=os.getenv("SITE_NAME", "Curated Gift Radar"),
        base_url=os.getenv("SITE_BASE_URL", "https://example.com"),
        description=os.getenv(
            "SITE_DESCRIPTION",
            "Automated daily feed of the coolest Amazon gifts, organized for effortless browsing.",
        ),
        adsense_client_id=os.getenv("ADSENSE_CLIENT_ID"),
        adsense_slot=os.getenv("ADSENSE_SLOT"),
        amazon_partner_tag=os.getenv("AMAZON_ASSOCIATE_TAG"),
        twitter_handle=os.getenv("SITE_TWITTER"),
        facebook_page=os.getenv("SITE_FACEBOOK"),
        keywords=keywords,
        newsletter_url=os.getenv("SITE_NEWSLETTER_URL"),
        contact_email=os.getenv("SITE_CONTACT_EMAIL"),
        language=optional_env("SITE_LANGUAGE") or "en",
        locale=optional_env("SITE_LOCALE") or "en_US",
        logo_url=optional_env("SITE_LOGO_URL"),
        favicon_url=optional_env("SITE_FAVICON_URL"),
        analytics_measurement_id=optional_env("SITE_ANALYTICS_ID"),
        analytics_snippet=analytics_snippet,
        newsletter_form_action=optional_env("SITE_NEWSLETTER_FORM_ACTION"),
        newsletter_form_method=newsletter_method,
        newsletter_form_email_field=email_field,
        newsletter_form_hidden_inputs=hidden_inputs,
        newsletter_cta_copy=optional_env("SITE_NEWSLETTER_CTA_COPY"),
    )


def load_credentials() -> Optional[AmazonCredentials]:
    access_key = os.getenv("AMAZON_PAAPI_ACCESS_KEY")
    secret_key = os.getenv("AMAZON_PAAPI_SECRET_KEY")
    partner_tag = os.getenv("AMAZON_ASSOCIATE_TAG")
    marketplace = os.getenv("AMAZON_MARKETPLACE", "www.amazon.com")
    host = os.getenv("AMAZON_API_HOST", "webservices.amazon.com")
    if not all([access_key, secret_key, partner_tag]):
        return None
    return AmazonCredentials(
        access_key=access_key,
        secret_key=secret_key,
        partner_tag=partner_tag,
        marketplace=marketplace,
        host=host,
    )


def load_static_retailers() -> List[StaticRetailerAdapter]:
    """Discover JSON-backed retailer feeds stored on disk."""

    adapters: List[StaticRetailerAdapter] = []
    directory_override = os.getenv("STATIC_RETAILER_DIR")
    base_path = Path(directory_override).expanduser() if directory_override else DATA_DIR / "retailers"
    if not base_path.exists():
        return adapters

    grouped: dict[str, dict[str, Path]] = {}
    for entry in sorted(base_path.iterdir()):
        if entry.is_file() and entry.suffix.lower() == ".json":
            slug = entry.stem.lower().replace("_", "-")
            grouped.setdefault(slug, {})["file"] = entry
        elif entry.is_dir():
            slug = entry.name.lower().replace("_", "-")
            grouped.setdefault(slug, {})["dir"] = entry

    for slug in sorted(grouped):
        info = grouped[slug]
        sources: List[Path] = []
        metadata: dict = {}
        directory = info.get("dir")
        if directory:
            for meta_name in ("meta.json", "metadata.json"):
                meta_path = directory / meta_name
                if meta_path.exists():
                    metadata = load_json(meta_path, default={}) or {}
                    break
        if directory:
            sources.append(directory)
        file_path = info.get("file")
        if file_path:
            sources.append(file_path)
            file_meta = load_json(file_path, default={}) or {}
            if isinstance(file_meta, dict):
                metadata = {**metadata, **file_meta}

        if not sources:
            continue

        display = " ".join(part.capitalize() for part in slug.split("-")) or slug
        adapters.append(
            StaticRetailerAdapter(
                slug=slug,
                name=str(metadata.get("name") or display),
                dataset=sources if len(sources) > 1 else sources[0],
                cta_label=str(metadata.get("cta_label") or "Shop now"),
                homepage=metadata.get("homepage"),
            )
        )
    return adapters


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    ensure_directories()

    settings = load_site_settings()
    repository = ProductRepository(data_file=args.data_file)
    generator = SiteGenerator(settings, output_dir=args.output_dir)

    if args.command == "update":
        credentials = load_credentials()
        static_retailers = load_static_retailers()
        if credentials is None and not static_retailers:
            parser.error(
                "No retailer sources configured. Provide Amazon credentials or add JSON feeds under data/retailers/."
            )
        retailer_adapters = []
        if credentials:
            retailer_adapters.append(AmazonRetailerAdapter(credentials))
        retailer_adapters.extend(static_retailers)
        pipeline = GiftPipeline(
            repository=repository,
            generator=generator,
            categories=DEFAULT_CATEGORIES,
            credentials=credentials,
            retailers=retailer_adapters,
        )
        pipeline.run(item_count=args.item_count, regenerate_only=False)
    else:
        retailer_adapters = load_static_retailers()
        pipeline = GiftPipeline(
            repository=repository,
            generator=generator,
            categories=DEFAULT_CATEGORIES,
            credentials=None,
            retailers=retailer_adapters,
        )
        pipeline.run(item_count=args.item_count, regenerate_only=True)

    LOGGER.info("Site build completed. Output directory: %s", args.output_dir)


if __name__ == "__main__":
    main()
