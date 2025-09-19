"""Command line entry point for running the automation pipeline."""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qsl

from .amazon import AmazonCredentials
from .ebay import EbayCredentials
from .article_repository import ArticleRepository
from .config import (
    DEFAULT_CATEGORIES,
    DATA_DIR,
    OUTPUT_DIR,
    SiteSettings,
    default_settings,
    ensure_directories,
)
from .generator import SiteGenerator
from .pipeline import GiftPipeline
from .repository import ProductRepository
from .retailers import AmazonRetailerAdapter, EbayRetailerAdapter, StaticRetailerAdapter
from .roundups import run_daily_roundups
from .utils import load_json

LOGGER = logging.getLogger(__name__)

COMMAND_CHOICES: tuple[str, ...] = ("update", "generate", "roundups")


def get_configured_default_command() -> str:
    """Return the default command configured via environment variables."""

    default_command_env = os.getenv("GIFTGRAB_DEFAULT_COMMAND")
    default_command = (
        default_command_env.strip().lower() if default_command_env else "generate"
    )
    if default_command not in COMMAND_CHOICES:
        default_command = "generate"
    return default_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automate the Grab Gifts static site generation pipeline.",
    )

    default_command = get_configured_default_command()

    parser.set_defaults(command=None, _default_command=default_command)

    def env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    parser.add_argument(
        "command",
        choices=COMMAND_CHOICES,
        nargs="?",
        help=(
            "Use 'update' to fetch new products and rebuild, 'generate' to rebuild from stored data, "
            "or 'roundups' to synthesize roundup playbooks and refresh the site. "
            f"When omitted, defaults to '{default_command}' once stored data exists; "
            "if no products have been stored yet, the update command runs automatically."
        ),
    )
    parser.add_argument(
        "--item-count",
        type=int,
        default=6,
        help="Number of products to request per category when fetching from configured retailers.",
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
        "--roundup-limit",
        type=int,
        default=env_int("ROUNDUPS_PER_DAY", 15),
        help=(
            "Number of roundup lists to generate per day when running the 'roundups' command."
        ),
    )
    parser.add_argument(
        "--roundup-days",
        type=int,
        default=env_int("ROUNDUPS_DAYS", 1),
        help="Number of days of roundup content to synthesize when running 'roundups'.",
    )
    parser.add_argument(
        "--roundup-seed",
        type=str,
        default=os.getenv("ROUNDUPS_SEED"),
        help="Optional seed for deterministic roundup output.",
    )
    parser.add_argument(
        "--roundup-start-date",
        type=str,
        default=os.getenv("ROUNDUPS_START_DATE"),
        help="ISO date (YYYY-MM-DD) to start scheduling roundups from.",
    )
    parser.add_argument(
        "--guide-backfill-days",
        type=int,
        default=0,
        help=(
            "Number of days of partner guides to backfill (max 365)."
        ),
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

    defaults = default_settings()
    adsense_client_id = optional_env("ADSENSE_CLIENT_ID")
    adsense_slot = optional_env("ADSENSE_SLOT")
    adsense_rail_slot = optional_env("ADSENSE_RAIL_SLOT")

    return SiteSettings(
        site_name=os.getenv("SITE_NAME", "Grab Gifts"),
        base_url=os.getenv("SITE_BASE_URL", "https://grabgifts.net"),
        description=os.getenv(
            "SITE_DESCRIPTION",
            "Grab Gifts surfaces viral-ready Amazon finds with conversion copy and plug-and-play affiliate automation.",
        ),
        adsense_client_id=(
            adsense_client_id if adsense_client_id is not None else defaults.adsense_client_id
        ),
        adsense_slot=adsense_slot if adsense_slot is not None else defaults.adsense_slot,
        adsense_rail_slot=(
            adsense_rail_slot if adsense_rail_slot is not None else defaults.adsense_rail_slot
        ),
        amazon_partner_tag="kayce25-20",
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
        press_mentions=defaults.press_mentions,
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


def load_ebay_credentials() -> Optional[EbayCredentials]:
    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")
    developer_id = os.getenv("EBAY_DEV_ID") or os.getenv("EBAY_DEVELOPER_ID")
    campaign_id = os.getenv("EBAY_CAMPAIGN_ID")
    if not all(value and value.strip() for value in (client_id, client_secret, developer_id)):
        return None
    campaign = campaign_id.strip() if campaign_id and campaign_id.strip() else None
    return EbayCredentials(
        client_id=client_id.strip(),
        client_secret=client_secret.strip(),
        developer_id=developer_id.strip(),
        affiliate_campaign_id=campaign,
    )


def load_static_retailers() -> List[StaticRetailerAdapter]:
    """Discover JSON-backed retailer feeds stored on disk."""

    adapters: List[StaticRetailerAdapter] = []
    directory_override = os.getenv("STATIC_RETAILER_DIR")
    base_path = Path(directory_override).expanduser() if directory_override else DATA_DIR / "retailers"
    if not base_path.exists():
        return adapters
    grouped: dict[str, dict[str, list[Path]]] = {}
    for entry in sorted(base_path.iterdir()):
        if entry.is_file():
            if entry.suffix.lower() != ".json":
                continue
            slug = entry.stem
            slug = slug.lower().replace("_", "-")
            grouped.setdefault(slug, {}).setdefault("files", []).append(entry)
        elif entry.is_dir():
            slug = entry.name.lower().replace("_", "-")
            grouped.setdefault(slug, {}).setdefault("dirs", []).append(entry)

    def extract_display_fields(payload: object) -> dict[str, str]:
        if not isinstance(payload, dict):
            return {}
        fields: dict[str, str] = {}
        for key in ("name", "cta_label", "homepage"):
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                fields[key] = text
        return fields

    for slug in sorted(grouped):
        info = grouped[slug]
        sources: list[Path] = []
        metadata: dict[str, str] = {}

        for directory in info.get("dirs", []):
            if not directory.exists():
                continue
            for meta_name in ("meta.json", "metadata.json"):
                meta_path = directory / meta_name
                if meta_path.exists():
                    metadata.update(extract_display_fields(load_json(meta_path, default={}) or {}))
                    break
            sources.append(directory)

        for file_path in info.get("files", []):
            if not file_path.exists():
                continue
            metadata.update(extract_display_fields(load_json(file_path, default={}) or {}))
            sources.append(file_path)

        if not sources:
            continue

        unique_sources = list(dict.fromkeys(Path(path) for path in sources))
        display = " ".join(part.capitalize() for part in slug.split("-")) or slug

        dataset: Path | Sequence[Path]
        if len(unique_sources) == 1:
            dataset = unique_sources[0]
        else:
            dataset = tuple(unique_sources)

        adapters.append(
            StaticRetailerAdapter(
                slug=slug,
                name=str(metadata.get("name") or display),
                dataset=dataset,
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
    article_repository = ArticleRepository(DATA_DIR / "articles.json")

    has_products = bool(repository.load_products())
    default_command = getattr(args, "_default_command", get_configured_default_command())

    if args.command is None:
        if not has_products:
            LOGGER.info("No stored products found; defaulting to 'update' command.")
            command = "update"
        else:
            command = default_command
    else:
        command = args.command

    if command == "generate" and not has_products:
        parser.error("No stored products available. Run 'update' first to fetch data.")

    if args.guide_backfill_days < 0:
        parser.error("--guide-backfill-days must be non-negative")

    if command == "update":
        amazon_credentials = load_credentials()
        ebay_credentials = load_ebay_credentials()
        static_retailers = load_static_retailers()
        if (
            amazon_credentials is None
            and ebay_credentials is None
            and not static_retailers
        ):
            parser.error(
                "No retailer sources configured. Provide Amazon or eBay credentials, or add JSON feeds under data/retailers/."
            )
        retailer_adapters = []
        if amazon_credentials:
            retailer_adapters.append(AmazonRetailerAdapter(amazon_credentials))
        if ebay_credentials:
            retailer_adapters.append(EbayRetailerAdapter(ebay_credentials))
        retailer_adapters.extend(static_retailers)
        pipeline = GiftPipeline(
            repository=repository,
            generator=generator,
            categories=DEFAULT_CATEGORIES,
            credentials=amazon_credentials,
            retailers=retailer_adapters,
            article_repository=article_repository,
        )
        run_kwargs = {"item_count": args.item_count, "regenerate_only": False}
        if args.guide_backfill_days:
            run_kwargs["guide_backfill_days"] = args.guide_backfill_days
        pipeline.run(**run_kwargs)
    elif command == "roundups":
        roundup_limit = args.roundup_limit
        if roundup_limit <= 0:
            parser.error("--roundup-limit must be positive")
        roundup_days = args.roundup_days
        if roundup_days <= 0:
            parser.error("--roundup-days must be positive")
        roundup_start_date = None
        if args.roundup_start_date:
            try:
                roundup_start_date = date.fromisoformat(args.roundup_start_date)
            except ValueError:
                parser.error(
                    "--roundup-start-date must be in ISO format (YYYY-MM-DD)"
                )
        run_daily_roundups(
            repository=repository,
            article_repository=article_repository,
            limit=roundup_limit,
            seed=args.roundup_seed,
            days=roundup_days,
            start_date=roundup_start_date,
        )
        retailer_adapters = load_static_retailers()
        pipeline = GiftPipeline(
            repository=repository,
            generator=generator,
            categories=DEFAULT_CATEGORIES,
            credentials=None,
            retailers=retailer_adapters,
            article_repository=article_repository,
        )
        run_kwargs = {"item_count": args.item_count, "regenerate_only": True}
        if args.guide_backfill_days:
            run_kwargs["guide_backfill_days"] = args.guide_backfill_days
        pipeline.run(**run_kwargs)
    else:
        retailer_adapters = load_static_retailers()
        pipeline = GiftPipeline(
            repository=repository,
            generator=generator,
            categories=DEFAULT_CATEGORIES,
            credentials=None,
            retailers=retailer_adapters,
            article_repository=article_repository,
        )
        run_kwargs = {"item_count": args.item_count, "regenerate_only": True}
        if args.guide_backfill_days:
            run_kwargs["guide_backfill_days"] = args.guide_backfill_days
        pipeline.run(**run_kwargs)

    LOGGER.info("Site build completed. Output directory: %s", args.output_dir)


if __name__ == "__main__":
    main()
