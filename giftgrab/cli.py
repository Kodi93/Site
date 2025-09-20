"""Command line entrypoints for the GiftGrab automation pipeline."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from . import ebay
from .generator import SiteGenerator
from .pipeline import GiftPipeline
from .reporting import generate_stats_report
from .repository import ProductRepository
from .roundups import generate_guides

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GiftGrab automation commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    update_parser = subparsers.add_parser("update", help="Fetch products and update the catalog")
    update_parser.set_defaults(func=handle_update)

    roundups_parser = subparsers.add_parser(
        "roundups", help="Generate roundup guides and render the static site"
    )
    roundups_parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Number of guides to publish",
    )
    roundups_parser.add_argument(
        "--skip-update",
        action="store_true",
        help="Skip refreshing products before generating guides",
    )
    roundups_parser.add_argument(
        "--output",
        type=Path,
        default=Path("public"),
        help="Output directory for the static site",
    )
    roundups_parser.set_defaults(func=handle_roundups)

    check_parser = subparsers.add_parser("check", help="Validate generated content before deploy")
    check_parser.add_argument(
        "--output",
        type=Path,
        default=Path("public"),
        help="Output directory that should contain the generated site",
    )
    check_parser.set_defaults(func=handle_check)

    stats_parser = subparsers.add_parser(
        "stats", help="Summarize catalog health and guide freshness"
    )
    stats_parser.add_argument(
        "--top-categories",
        type=int,
        default=5,
        help="Number of top categories to display",
    )
    stats_parser.add_argument(
        "--recent-days",
        type=int,
        default=7,
        help="Number of days to treat guides as recently updated",
    )
    stats_parser.set_defaults(func=handle_stats)

    ebay_parser = subparsers.add_parser(
        "ebay", help="Run an ad-hoc eBay Browse API search for debugging"
    )
    ebay_parser.add_argument(
        "query",
        nargs="?",
        default="gift ideas",
        help="Search keywords to pass to the Browse API",
    )
    ebay_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of items to return",
    )
    ebay_parser.add_argument(
        "--json",
        action="store_true",
        help="Output the raw normalized payload as JSON",
    )
    ebay_parser.add_argument(
        "--marketplace",
        help="Override the X-EBAY-C-MARKETPLACE-ID header (defaults to EBAY_US)",
    )
    ebay_parser.set_defaults(func=handle_ebay)

    return parser


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def handle_update(args: argparse.Namespace) -> None:
    repository = ProductRepository()
    pipeline = GiftPipeline(repository=repository)
    pipeline.run()
    LOGGER.info("Update complete. %s products stored.", len(repository.load_products()))


def handle_roundups(args: argparse.Namespace) -> None:
    if args.limit < 15:
        raise SystemExit("--limit must be at least 15")
    repository = ProductRepository()
    if not getattr(args, "skip_update", False):
        pipeline = GiftPipeline(repository=repository)
        LOGGER.info("Refreshing catalog before generating guides")
        pipeline.run()
    guides = generate_guides(repository, limit=args.limit)
    generator = SiteGenerator(output_dir=args.output)
    products = repository.load_products()
    generator.build(products=products, guides=guides)
    LOGGER.info("Generated %s guides", len(guides))


def handle_check(args: argparse.Namespace) -> None:
    repository = ProductRepository()
    products = repository.load_products()
    guides = repository.load_guides()
    errors: list[str] = []
    if len(products) < 50:
        errors.append(f"Inventory too small: {len(products)} products")
    if len(guides) < 15:
        errors.append(f"Not enough guides generated: {len(guides)}")
    slugs = set()
    for guide in guides:
        if guide.slug in slugs:
            errors.append(f"Duplicate guide slug detected: {guide.slug}")
        slugs.add(guide.slug)
    for required in ("sitemap.xml", "robots.txt", "rss.xml"):
        if not (args.output / required).exists():
            errors.append(f"Missing {required} in {args.output}")
    if errors:
        for error in errors:
            LOGGER.error(error)
        raise SystemExit(1)
    LOGGER.info("Check passed: %s products, %s guides", len(products), len(guides))


def handle_stats(args: argparse.Namespace) -> None:
    if args.recent_days < 1:
        raise SystemExit("--recent-days must be at least 1")
    if args.top_categories < 0:
        raise SystemExit("--top-categories cannot be negative")

    repository = ProductRepository()
    products = repository.load_products()
    guides = repository.load_guides()
    report = generate_stats_report(
        products=products,
        guides=guides,
        top_categories=args.top_categories,
        recent_days=args.recent_days,
    )
    print(report)


def _truncate(value: object, width: int) -> str:
    text = str(value or "")
    if len(text) <= width:
        return text.ljust(width)
    if width <= 1:
        return text[:width]
    return (text[: width - 1].rstrip() + "…").ljust(width)


def handle_ebay(args: argparse.Namespace) -> None:
    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    token = ebay.get_token()
    if not token:
        raise SystemExit(
            "Unable to obtain eBay OAuth token. "
            "Check EBAY_CLIENT_ID and EBAY_CLIENT_SECRET."
        )
    items = ebay.search(
        args.query,
        limit=args.limit,
        token=token,
        marketplace_id=getattr(args, "marketplace", None),
    )
    if args.json:
        print(json.dumps(items, indent=2, sort_keys=True))
        return
    if not items:
        print("No products returned for query '" + args.query + "'.")
        return
    header = (
        f"{_truncate('ID', 18)} {_truncate('Title', 52)} "
        f"{_truncate('Price', 12)} {_truncate('Brand', 18)} URL"
    )
    print(header)
    print("-" * len(header))
    for item in items:
        price = item.get("price_text")
        if not price and isinstance(item.get("price"), (int, float)):
            price = f"${float(item['price']):,.2f}"
        brand = item.get("brand") or ""
        print(
            f"{_truncate(item.get('id'), 18)} "
            f"{_truncate(item.get('title'), 52)} "
            f"{_truncate(price, 12)} {_truncate(brand, 18)} {item.get('url', '')}"
        )


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging()
    args.func(args)


if __name__ == "__main__":
    main()
