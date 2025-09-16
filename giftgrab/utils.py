"""General utility helpers."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Return an SEO-friendly slug for the provided value."""

    value = value.lower().strip()
    value = SLUG_PATTERN.sub("-", value)
    value = value.strip("-")
    return value or "item"


def load_json(path: Path, default: Dict[str, Any] | list | None = None) -> Any:
    """Load a JSON file returning a default value if it does not exist."""

    if not path.exists():
        return default if default is not None else {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, data: Any) -> None:
    """Persist JSON data to disk, ensuring the parent folder exists."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def timestamp() -> str:
    """Return an ISO-8601 timestamp in UTC."""

    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
