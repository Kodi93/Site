"""Amazon PA-API helper that remains optional until credentials are provided."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)
_DISABLED_LOGGED = False


@dataclass
class AmazonCredentials:
    access_key: str
    secret_key: str
    partner_tag: str
    marketplace: str
    host: str = "webservices.amazon.com"


def _ensure_credentials() -> Optional[AmazonCredentials]:
    access = os.getenv("AMAZON_PAAPI_ACCESS_KEY")
    secret = os.getenv("AMAZON_PAAPI_SECRET_KEY")
    partner = os.getenv("AMAZON_ASSOCIATE_TAG")
    marketplace = os.getenv("AMAZON_MARKETPLACE", "www.amazon.com")
    if not access or not secret or not partner:
        global _DISABLED_LOGGED
        if not _DISABLED_LOGGED:
            LOGGER.info("Amazon disabled")
            _DISABLED_LOGGED = True
        return None
    host = os.getenv("AMAZON_API_HOST", "webservices.amazon.com")
    return AmazonCredentials(
        access_key=access.strip(),
        secret_key=secret.strip(),
        partner_tag=partner.strip(),
        marketplace=marketplace.strip() or "www.amazon.com",
        host=host.strip() or "webservices.amazon.com",
    )


def _sign(
    *,
    credentials: AmazonCredentials,
    target: str,
    payload: str,
    service: str = "ProductAdvertisingAPI",
    region: str = "us-east-1",
) -> dict[str, str]:
    """Return the signed headers for an Amazon PA-API request.

    The caller is responsible for performing the network request. This helper is
    intentionally unused when credentials are absent so the pipeline can rely on
    eBay alone until Amazon keys are provided.
    """

    now = datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    canonical_uri = "/paapi5/searchitems"
    canonical_headers = (
        "content-encoding:amz-1.0\n"
        "content-type:application/json; charset=UTF-8\n"
        f"host:{credentials.host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:{target}\n"
    )
    signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        "POST\n"
        f"{canonical_uri}\n\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )
    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
    signing_key = _hmac(_hmac(_hmac(_hmac(("AWS4" + credentials.secret_key).encode("utf-8"), date_stamp), region), service), "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Content-Encoding": "amz-1.0",
        "Content-Type": "application/json; charset=UTF-8",
        "Host": credentials.host,
        "X-Amz-Date": amz_date,
        "X-Amz-Target": target,
        "Authorization": (
            "AWS4-HMAC-SHA256 "
            f"Credential={credentials.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
    }


def search(keywords: Iterable[str], limit: int = 10) -> List[dict]:
    """Search Amazon PA-API. Returns an empty list when credentials are missing."""

    credentials = _ensure_credentials()
    if credentials is None:
        return []
    return _search_with_credentials(credentials, keywords=keywords, limit=limit)


def _search_with_credentials(
    credentials: AmazonCredentials, *, keywords: Iterable[str], limit: int
) -> List[dict]:
    """Perform a search against the PA-API using explicit credentials."""

    query = " ".join(str(keyword) for keyword in keywords if keyword)
    body = json.dumps(
        {
            "PartnerTag": credentials.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": credentials.marketplace,
            "Keywords": query,
            "ItemCount": limit,
            "ItemPage": 1,
            "Resources": [
                "Images.Primary.Large",
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "BrowseNodeInfo.BrowseNodes",
            ],
        }
    )
    headers = _sign(
        credentials=credentials,
        target="com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems",
        payload=body,
    )
    request = Request(
        f"https://{credentials.host}/paapi5/searchitems",
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:  # pragma: no cover - network errors
        detail = exc.read().decode("utf-8", "ignore")
        LOGGER.error("Amazon API error %s: %s", exc.code, detail)
        return []
    except URLError as exc:  # pragma: no cover - network errors
        LOGGER.error("Amazon API network error: %s", exc)
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:  # pragma: no cover - invalid payloads
        LOGGER.error("Invalid Amazon API response: %s", payload[:200])
        return []
    items = data.get("SearchResult", {}).get("Items", [])
    results: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        asin = item.get("ASIN")
        title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue")
        detail_url = item.get("DetailPageURL")
        if not asin or not title or not detail_url:
            continue
        offers = item.get("Offers", {}).get("Listings", [])
        price = None
        currency = "USD"
        price_text = None
        if isinstance(offers, list) and offers:
            listing = offers[0]
            amount = listing.get("Price", {}).get("Amount")
            currency = listing.get("Price", {}).get("Currency") or currency
            try:
                price = float(amount)
            except (TypeError, ValueError):
                price = None
            if price is not None:
                price_text = f"${price:,.2f}" if currency == "USD" else f"{price:,.2f} {currency}"
        brand = item.get("ItemInfo", {}).get("ByLineInfo", {}).get("Brand", {}).get("DisplayValue")
        category = None
        browse_nodes = item.get("BrowseNodeInfo", {}).get("BrowseNodes", [])
        if isinstance(browse_nodes, list) and browse_nodes:
            category = browse_nodes[0].get("DisplayName")
        results.append(
            {
                "id": str(asin),
                "title": str(title),
                "url": str(detail_url),
                "image": item.get("Images", {}).get("Primary", {}).get("Large", {}).get("URL"),
                "price": price,
                "price_text": price_text,
                "currency": currency,
                "brand": brand,
                "category": category,
                "rating": None,
                "rating_count": None,
                "source": "amazon",
            }
        )
    return results


class AmazonProductClient:
    """Thin client wrapper used by retailer adapters."""

    def __init__(self, credentials: AmazonCredentials) -> None:
        self.credentials = credentials

    def search_items(self, *, keywords: Iterable[str], item_count: int) -> List[dict]:
        return _search_with_credentials(
            self.credentials, keywords=keywords, limit=item_count
        )
