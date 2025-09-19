"""Article data structures and helpers for long-form editorial content."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Sequence

from .utils import slugify, timestamp


ARTICLE_KINDS = {"roundup", "seasonal", "weekly", "guide"}
ARTICLE_STATUSES = {"draft", "published"}


def _coerce_kind(value: str) -> str:
    value = (value or "").strip().lower()
    if value not in ARTICLE_KINDS:
        raise ValueError(f"Unsupported article kind: {value!r}")
    return value


def _coerce_status(value: str) -> str:
    value = (value or "").strip().lower()
    if value not in ARTICLE_STATUSES:
        raise ValueError(f"Unsupported article status: {value!r}")
    return value


def _coerce_list(values: Iterable[str] | None) -> List[str]:
    result: List[str] = []
    if not values:
        return result
    for value in values:
        if not value:
            continue
        trimmed = str(value).strip()
        if trimmed and trimmed not in result:
            result.append(trimmed)
    return result


@dataclass
class ArticleItem:
    """A single product section referenced within an article."""

    anchor: str
    title: str
    product_slug: str
    image: str
    blurb: str
    specs: List[str]
    tags: List[str] = field(default_factory=list)
    outbound_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "anchor": self.anchor,
            "title": self.title,
            "product_slug": self.product_slug,
            "image": self.image,
            "blurb": self.blurb,
            "specs": list(self.specs),
            "tags": list(self.tags),
            "outbound_url": self.outbound_url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArticleItem":
        return cls(
            anchor=data.get("anchor") or slugify(data.get("title", "section")),
            title=data.get("title", ""),
            product_slug=data.get("product_slug", ""),
            image=data.get("image", ""),
            blurb=data.get("blurb", ""),
            specs=list(data.get("specs") or []),
            tags=_coerce_list(data.get("tags")),
            outbound_url=data.get("outbound_url"),
        )


@dataclass
class Article:
    """Long-form editorial content associated with the site."""

    id: str
    slug: str
    path: str
    kind: str
    title: str
    description: str
    hero_image: str
    intro: List[str]
    who_for: str
    consider: str
    items: List[ArticleItem]
    hub_slugs: List[str] = field(default_factory=list)
    related_product_slugs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    status: str = "draft"
    created_at: str = field(default_factory=timestamp)
    updated_at: str = field(default_factory=timestamp)
    published_at: str | None = None

    def __post_init__(self) -> None:
        self.kind = _coerce_kind(self.kind)
        self.status = _coerce_status(self.status)
        self.tags = _coerce_list(self.tags)
        self.hub_slugs = _coerce_list(self.hub_slugs)
        self.related_product_slugs = _coerce_list(self.related_product_slugs)
        intro = [paragraph.strip() for paragraph in self.intro if paragraph.strip()]
        if not intro:
            raise ValueError("Article intro must contain at least one paragraph.")
        self.intro = intro
        self.items = [item for item in self.items if item.title and item.product_slug]
        if not self.items:
            raise ValueError("Article requires at least one item section.")

    @property
    def body_mdx(self) -> str:
        """Return a markdown-like body representation used for quality gates."""

        sections: List[str] = []
        sections.append("\n\n".join(self.intro))
        hub_text = ""
        if self.hub_slugs:
            hub_lines = ["Explore these related hubs:"]
            for slug in self.hub_slugs:
                hub_lines.append(f"- /categories/{slug}/")
            hub_text = "\n".join(hub_lines)
            sections.append(hub_text)
        for item in self.items:
            specs = "\n".join(f"- {spec}" for spec in item.specs if spec)
            sections.append(
                f"### {item.title}\n\n{item.blurb}\n\n{specs}\n\nLink: /products/{item.product_slug}/"
            )
        sections.append(f"### Who it's for\n\n{self.who_for}")
        sections.append(f"### Consider\n\n{self.consider}")
        if self.related_product_slugs:
            related_lines = ["Related picks:"]
            for slug in self.related_product_slugs:
                related_lines.append(f"- /products/{slug}/")
            sections.append("\n".join(related_lines))
        return "\n\n".join(sections).strip()

    @property
    def body_length(self) -> int:
        return len(self.body_mdx)

    @property
    def word_count(self) -> int:
        return len([word for word in self.body_mdx.split() if word])

    @property
    def table_of_contents(self) -> List[tuple[str, str]]:
        entries: List[tuple[str, str]] = []
        for item in self.items:
            entries.append((item.anchor, item.title))
        entries.append((slugify("who-its-for"), "Who it's for"))
        entries.append((slugify("consider"), "Consider"))
        if self.related_product_slugs:
            entries.append((slugify("related-picks"), "Related"))
        return entries

    def mark_published(self, when: datetime | None = None) -> None:
        when = when or datetime.now(timezone.utc)
        self.status = "published"
        iso = when.isoformat()
        self.published_at = iso
        self.updated_at = iso

    def touch(self, when: datetime | None = None) -> None:
        when = when or datetime.now(timezone.utc)
        self.updated_at = when.isoformat()

    def ensure_quality(
        self,
        *,
        min_body_length: int = 800,
        min_items: int = 8,
        max_duplicate_ratio: float = 0.2,
    ) -> None:
        if len(self.title.strip()) == 0 or len(self.title.strip()) > 60:
            raise ValueError("Article title must be non-empty and at most 60 characters.")
        if len(self.description.strip()) < 140 or len(self.description.strip()) > 160:
            raise ValueError("Meta description must be between 140 and 160 characters.")
        intro_words = sum(len(paragraph.split()) for paragraph in self.intro)
        if intro_words < 120 or intro_words > 200:
            raise ValueError("Intro copy must be between 120 and 200 words.")
        if len(self.items) < min_items:
            raise ValueError("Not enough items to satisfy quality bar.")
        if self.body_length < min_body_length:
            raise ValueError("Body content is too short for publication.")
        blurbs = [item.blurb.strip().lower() for item in self.items if item.blurb.strip()]
        duplicates = 0
        seen: set[str] = set()
        for blurb in blurbs:
            if blurb in seen:
                duplicates += 1
            else:
                seen.add(blurb)
        if blurbs and duplicates / len(blurbs) > max_duplicate_ratio:
            raise ValueError("Too many duplicate blurbs in article items.")
        if not self.hero_image.strip():
            raise ValueError("Hero image is required for article publication.")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "path": self.path,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "hero_image": self.hero_image,
            "intro": list(self.intro),
            "who_for": self.who_for,
            "consider": self.consider,
            "items": [item.to_dict() for item in self.items],
            "hub_slugs": list(self.hub_slugs),
            "related_product_slugs": list(self.related_product_slugs),
            "tags": list(self.tags),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "published_at": self.published_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        items = [
            ArticleItem.from_dict(raw)
            for raw in data.get("items", [])
            if isinstance(raw, dict)
        ]
        return cls(
            id=data.get("id", ""),
            slug=data.get("slug", ""),
            path=data.get("path", ""),
            kind=data.get("kind", "roundup"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            hero_image=data.get("hero_image", ""),
            intro=list(data.get("intro") or []),
            who_for=data.get("who_for", ""),
            consider=data.get("consider", ""),
            items=items,
            hub_slugs=_coerce_list(data.get("hub_slugs")),
            related_product_slugs=_coerce_list(data.get("related_product_slugs")),
            tags=_coerce_list(data.get("tags")),
            status=data.get("status", "draft"),
            created_at=data.get("created_at", timestamp()),
            updated_at=data.get("updated_at", timestamp()),
            published_at=data.get("published_at"),
        )

    def copy_with(self, **overrides) -> "Article":
        payload = self.to_dict()
        payload.update(overrides)
        return Article.from_dict(payload)


def ensure_articles_quality(articles: Sequence[Article]) -> None:
    for article in articles:
        article.ensure_quality()
