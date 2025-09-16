"""Command line entry point for running the automation pipeline."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

from .amazon import AmazonCredentials
from .config import DEFAULT_CATEGORIES, DATA_DIR, OUTPUT_DIR, SiteSettings, ensure_directories
from .generator import SiteGenerator
from .pipeline import GiftPipeline
from .repository import ProductRepository

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
        if credentials is None:
            parser.error(
                "Missing Amazon API credentials. Please set AMAZON_PAAPI_ACCESS_KEY, AMAZON_PAAPI_SECRET_KEY, and AMAZON_ASSOCIATE_TAG."
            )
        pipeline = GiftPipeline(
            repository=repository,
            generator=generator,
            categories=DEFAULT_CATEGORIES,
            credentials=credentials,
        )
        pipeline.run(item_count=args.item_count, regenerate_only=False)
    else:
        pipeline = GiftPipeline(
            repository=repository,
            generator=generator,
            categories=DEFAULT_CATEGORIES,
            credentials=None,
        )
        pipeline.run(item_count=args.item_count, regenerate_only=True)

    LOGGER.info("Site build completed. Output directory: %s", args.output_dir)


if __name__ == "__main__":
    main()
