"""JSON-backed persistence for generated editorial articles."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Sequence

from .articles import Article
from .models import RoundupArticle
from .utils import dump_json, load_json, timestamp

logger = logging.getLogger(__name__)


class ArticleRepository:
    """Persist long-form articles to a JSON document alongside products."""

    def __init__(self, data_file: Path) -> None:
        self.data_file = data_file
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        if self.data_file.exists():
            return
        logger.debug("Creating article repository at %s", self.data_file)
        dump_json(
            self.data_file,
            {
                "articles": [],
                "meta": {
                    "roundup_index": 0,
                    "guide_index": 0,
                    "guide_last_published": None,
                },
                "roundups": [],
            },
        )

    def _load_payload(self) -> dict:
        data = load_json(self.data_file, default={})
        if not isinstance(data, dict):
            data = {}
        data.setdefault("articles", [])
        data.setdefault(
            "meta",
            {
                "roundup_index": 0,
                "guide_index": 0,
                "guide_last_published": None,
            },
        )
        data.setdefault("roundups", [])
        return data

    def load_articles(self) -> List[Article]:
        payload = self._load_payload()
        articles: List[Article] = []
        for raw in payload.get("articles", []):
            if isinstance(raw, dict):
                try:
                    articles.append(Article.from_dict(raw))
                except Exception as error:  # pragma: no cover - logged for visibility
                    logger.warning("Skipping invalid article payload: %s", error)
        return articles

    def save_articles(self, articles: Sequence[Article]) -> None:
        payload = self._load_payload()
        payload["articles"] = [article.to_dict() for article in articles]
        payload["last_saved"] = timestamp()
        dump_json(self.data_file, payload)

    def upsert(self, article: Article) -> Article:
        articles = self.load_articles()
        updated: List[Article] = []
        replaced = False
        for existing in articles:
            if existing.id == article.id:
                updated.append(article)
                replaced = True
            else:
                updated.append(existing)
        if not replaced:
            updated.append(article)
        self.save_articles(updated)
        return article

    def delete(self, article_id: str) -> None:
        articles = [article for article in self.load_articles() if article.id != article_id]
        self.save_articles(articles)

    def find_by_slug(self, slug: str) -> Article | None:
        slug = (slug or "").strip().lower()
        for article in self.load_articles():
            if article.slug.lower() == slug:
                return article
        return None

    def list_published(self, *, min_body_length: int = 800) -> List[Article]:
        published = [
            article
            for article in self.load_articles()
            if article.status == "published" and article.body_length >= min_body_length
        ]
        published.sort(key=lambda article: article.updated_at, reverse=True)
        return published

    def update(self, article: Article) -> None:
        self.upsert(article)

    def publish(self, article_id: str, when: str | None = None) -> Article | None:
        when_value = when or timestamp()
        articles = self.load_articles()
        updated: List[Article] = []
        target: Article | None = None
        for article in articles:
            if article.id == article_id:
                article.status = "published"
                article.updated_at = when_value
                article.published_at = when_value
                target = article
            updated.append(article)
        if target is not None:
            self.save_articles(updated)
        return target

    # ------------------------------------------------------------------
    # Roundup helpers
    def load_roundups(self) -> List[RoundupArticle]:
        payload = self._load_payload()
        roundups: List[RoundupArticle] = []
        for raw in payload.get("roundups", []):
            if isinstance(raw, dict):
                try:
                    roundups.append(RoundupArticle.from_dict(raw))
                except Exception as error:  # pragma: no cover - log
                    logger.debug("Skipping invalid roundup payload: %s", error)
        return roundups

    def save_roundups(self, roundups: Sequence[RoundupArticle]) -> None:
        payload = self._load_payload()
        payload["roundups"] = [roundup.to_dict() for roundup in roundups]
        payload["last_saved"] = timestamp()
        dump_json(self.data_file, payload)

    def upsert_roundup(self, roundup: RoundupArticle) -> RoundupArticle:
        roundups = self.load_roundups()
        updated: List[RoundupArticle] = []
        replaced = False
        for existing in roundups:
            if existing.slug == roundup.slug:
                updated.append(roundup)
                replaced = True
            else:
                updated.append(existing)
        if not replaced:
            updated.append(roundup)
        self.save_roundups(updated)
        return roundup

    def find_roundup(self, slug: str) -> RoundupArticle | None:
        slug = (slug or "").strip().lower()
        for roundup in self.load_roundups():
            if roundup.slug == slug:
                return roundup
        return None

    def list_published_roundups(self) -> List[RoundupArticle]:
        published = [
            roundup
            for roundup in self.load_roundups()
            if roundup.status == "published"
        ]
        published.sort(key=lambda roundup: roundup.updated_at, reverse=True)
        return published

    # Rotation metadata -------------------------------------------------
    def get_roundup_index(self) -> int:
        payload = self._load_payload()
        meta = payload.get("meta") or {}
        value = meta.get("roundup_index", 0)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def set_roundup_index(self, value: int) -> None:
        payload = self._load_payload()
        payload.setdefault("meta", {})["roundup_index"] = int(value)
        dump_json(self.data_file, payload)

    def get_guide_index(self) -> int:
        payload = self._load_payload()
        meta = payload.get("meta") or {}
        value = meta.get("guide_index", 0)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def set_guide_index(self, value: int) -> None:
        payload = self._load_payload()
        payload.setdefault("meta", {})["guide_index"] = int(value)
        dump_json(self.data_file, payload)

    def get_guide_last_published(self) -> str | None:
        payload = self._load_payload()
        meta = payload.get("meta") or {}
        value = meta.get("guide_last_published")
        if value:
            return str(value)
        return None

    def set_guide_last_published(self, value: str | None) -> None:
        payload = self._load_payload()
        meta = payload.setdefault("meta", {})
        if value:
            meta["guide_last_published"] = value
        else:
            meta.pop("guide_last_published", None)
        dump_json(self.data_file, payload)


def published_for_sitemap(repository: ArticleRepository, *, min_body_length: int = 800) -> List[Article]:
    return repository.list_published(min_body_length=min_body_length)
