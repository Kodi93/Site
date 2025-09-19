"""Command line entrypoints for the GiftGrab automation pipeline."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .generator import SiteGenerator
from .pipeline import GiftPipeline
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


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging()
    args.func(args)


if __name__ == "__main__":
    main()
