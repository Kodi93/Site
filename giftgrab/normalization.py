"""Helpers for normalizing product payloads during ingestion."""

from __future__ import annotations

import re
from typing import Iterable, Tuple
from urllib.parse import parse_qsl, urlparse, urlsplit, urlunsplit, urlencode

from .utils import slugify

_PLACEHOLDER_IMAGE_PREFIXES: Tuple[str, ...] = ("/assets/amazon-sitestripe/",)
_PLACEHOLDER_IMAGE_HOSTS = {
    "images.unsplash.com",
    "picsum.photos",
    "placekitten.com",
    "source.unsplash.com",
}

_EBAY_TRACKING_PARAMS = {
    "amdata",
    "campgate",
    "campid",
    "chn",
    "customid",
    "epid",
    "frcectry",
    "hash",
    "imprid",
    "itmmeta",
    "loc",
    "mkcid",
    "mkevt",
    "mknod",
    "mkrid",
    "mksiteid",
    "mpre",
    "nma",
    "norover",
    "norvid",
    "osub",
    "pmt",
    "plmt",
    "rt",
    "rvr_id",
    "segname",
    "siteid",
    "skw",
    "sojtags",
    "toolid",
    "ul_noapp",
    "ul_ref",
    "var",
    "_skw",
    "_trkparms",
    "_trksid",
}

_EBAY_V1_ID_PATTERN = re.compile(r"^v\d\|(\d{9,})\|\d+$")
_EBAY_NUMERIC_ID_PATTERN = re.compile(r"^(\d{9,})$")
_EBAY_HASH_PATTERN = re.compile(r"item([0-9a-fA-F]+)")
_EBAY_URL_ID_PATTERN = re.compile(r"/itm/(?:[^/]*-)?([0-9a-fA-F]{9,})", re.IGNORECASE)


def looks_like_placeholder_image(value: object) -> bool:
    """Return ``True`` when the provided image payload is a known placeholder."""

    if not value:
        return True
    text = str(value).strip()
    if not text:
        return True
    lowered = text.lower()
    if lowered.startswith("data:image/svg"):
        return True
    for prefix in _PLACEHOLDER_IMAGE_PREFIXES:
        if lowered.startswith(prefix):
            return True
    if lowered.endswith(".svg") and "amazon" in lowered:
        return True
    if "placeholder" in lowered:
        return True
    if lowered.startswith("http://") or lowered.startswith("https://"):
        try:
            host = urlparse(lowered).netloc
        except ValueError:
            return False
        if host in _PLACEHOLDER_IMAGE_HOSTS:
            return True
    return False


def _filter_tracking_params(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    filtered = []
    for key, value in pairs:
        if key.lower() in _EBAY_TRACKING_PARAMS:
            continue
        filtered.append((key, value))
    filtered.sort(key=lambda item: item[0])
    return filtered


def _extract_ebay_identifier(
    raw_id: object, *, parsed_url, query_pairs: list[tuple[str, str]]
) -> str | None:
    query_map = {key.lower(): value for key, value in query_pairs}
    custom_id = query_map.get("customid")
    identifier: str | None = None
    if isinstance(raw_id, str):
        trimmed = raw_id.strip()
        match = _EBAY_V1_ID_PATTERN.match(trimmed)
        if match:
            identifier = match.group(1)
        else:
            candidate = trimmed
            if candidate.lower().startswith("ebay-"):
                candidate = candidate.split("-", 1)[1]
            match = _EBAY_NUMERIC_ID_PATTERN.match(candidate)
            if match:
                identifier = match.group(1)
        if identifier and custom_id and identifier == custom_id:
            identifier = None
    if identifier:
        return identifier
    path = parsed_url.path or ""
    path_match = _EBAY_URL_ID_PATTERN.search(path)
    if path_match:
        identifier = path_match.group(1)
    if identifier:
        return identifier
    hash_value = query_map.get("hash")
    if hash_value:
        hash_match = _EBAY_HASH_PATTERN.search(hash_value)
        if hash_match:
            identifier = hash_match.group(1)
    if identifier:
        return identifier
    for key in ("item", "itemid", "itemnumber", "itm"):
        value = query_map.get(key)
        if value and value.isdigit():
            return value
    return None


def _canonicalize_ebay_url(raw_url: str) -> tuple[str, list[tuple[str, str]]]:
    parsed = urlsplit(raw_url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered = _filter_tracking_params(pairs)
    canonical_query = urlencode(filtered, doseq=True)
    canonical = urlunsplit(
        (
            parsed.scheme or "https",
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            canonical_query,
            "",
        )
    )
    return canonical, pairs


def canonicalize_product_identity(
    raw_id: object, url: object, source: object | None
) -> tuple[str, str]:
    """Return a stable ``(id, url)`` pair for the provided product payload."""

    source_value = str(source or "").lower()
    url_text = str(url or "").strip()
    if not url_text:
        return (str(raw_id), url_text)
    parsed = urlsplit(url_text)
    host = parsed.netloc.lower()
    if source_value == "ebay" or host.endswith("ebay.com") or ".ebay." in host:
        canonical_url, original_pairs = _canonicalize_ebay_url(url_text)
        identifier = _extract_ebay_identifier(
            raw_id, parsed_url=parsed, query_pairs=original_pairs
        )
        if identifier:
            return (f"ebay-{identifier}", canonical_url)
        slug_source = parsed.path or canonical_url
        slug = slugify(f"ebay-{slug_source}")
        return (slug or f"ebay-{slugify(url_text)}" or str(raw_id)), canonical_url
    return (str(raw_id), url_text)

