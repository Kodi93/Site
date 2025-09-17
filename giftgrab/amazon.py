"""Amazon Product Advertising API client using only the Python standard library."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

SERVICE = "ProductAdvertisingAPI"
TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
REGION_BY_HOST = {
    "webservices.amazon.com": "us-east-1",
    "webservices.amazon.co.uk": "eu-west-1",
    "webservices.amazon.de": "eu-west-1",
    "webservices.amazon.in": "eu-west-1",
    "webservices.amazon.co.jp": "us-west-2",
}


@dataclass
class AmazonCredentials:
    access_key: str
    secret_key: str
    partner_tag: str
    marketplace: str = "www.amazon.com"
    host: str = "webservices.amazon.com"

    @property
    def region(self) -> str:
        return REGION_BY_HOST.get(self.host, "us-east-1")


class AmazonProductClient:
    """Lightweight wrapper around the Amazon Product Advertising API."""

    def __init__(self, credentials: AmazonCredentials) -> None:
        self.credentials = credentials

    def _sign(self, payload: str) -> Dict[str, str]:
        now = datetime.utcnow()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        canonical_uri = "/paapi5/searchitems"
        canonical_querystring = ""
        canonical_headers = (
            "content-encoding:amz-1.0\n"
            "content-type:application/json; charset=UTF-8\n"
            f"host:{self.credentials.host}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:{TARGET}\n"
        )
        signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (
            "POST\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )
        logger.debug("Canonical request: %s", canonical_request)
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = (
            f"{date_stamp}/{self.credentials.region}/{SERVICE}/aws4_request"
        )
        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )
        signing_key = self._get_signature_key(
            self.credentials.secret_key, date_stamp, self.credentials.region, SERVICE
        )
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256)
        authorization_header = (
            f"{algorithm} Credential={self.credentials.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature.hexdigest()}"
        )
        headers = {
            "Content-Encoding": "amz-1.0",
            "Content-Type": "application/json; charset=UTF-8",
            "Host": self.credentials.host,
            "X-Amz-Date": amz_date,
            "X-Amz-Target": TARGET,
            "Authorization": authorization_header,
        }
        return headers

    @staticmethod
    def _sign_message(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_signature_key(
        self, key: str, date_stamp: str, region_name: str, service_name: str
    ) -> bytes:
        k_date = self._sign_message(("AWS4" + key).encode("utf-8"), date_stamp)
        k_region = self._sign_message(k_date, region_name)
        k_service = self._sign_message(k_region, service_name)
        k_signing = self._sign_message(k_service, "aws4_request")
        return k_signing

    def search_items(
        self, *, keywords: Iterable[str], item_count: int = 10
    ) -> List[Dict[str, object]]:
        query = " ".join(keywords)
        body = {
            "Keywords": query,
            "PartnerTag": self.credentials.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": self.credentials.marketplace,
            "Resources": [
                "Images.Primary.Large",
                "Images.Primary.Medium",
                "Images.Primary.Small",
                "ItemInfo.Title",
                "ItemInfo.Features",
                "ItemInfo.ByLineInfo",
                "ItemInfo.ContentInfo",
                "ItemInfo.ProductInfo",
                "ItemInfo.TechnicalInfo",
                "Offers.Listings.Price",
                "CustomerReviews.Count",
                "CustomerReviews.StarRating",
            ],
            "ItemCount": item_count,
            "ItemPage": 1,
        }
        payload = json.dumps(body, separators=(",", ":"))
        headers = self._sign(payload)
        request = Request(
            f"https://{self.credentials.host}{canonical_path()}",
            data=payload.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
                logger.debug("Amazon response: %s", raw[:2000])
                return self._parse_items(data)
        except HTTPError as exc:
            logger.error("Amazon API HTTP error %s: %s", exc.code, exc.read())
        except URLError as exc:
            logger.error("Amazon API request error: %s", exc)
        except Exception as exc:  # pragma: no cover - network failures
            logger.exception("Unexpected error calling Amazon API: %s", exc)
        return []

    def _parse_items(self, data: dict) -> List[Dict[str, object]]:
        search_results = data.get("SearchResult", {})
        items = search_results.get("Items", [])
        parsed: List[Dict[str, object]] = []
        for item in items:
            asin = item.get("ASIN")
            info = item.get("ItemInfo", {})
            title = (
                info.get("Title", {}).get("DisplayValue")
                if isinstance(info.get("Title"), dict)
                else None
            )
            detail_page = item.get("DetailPageURL")
            images = item.get("Images", {})
            image_url = None
            primary = images.get("Primary") if isinstance(images, dict) else None
            if isinstance(primary, dict):
                large = primary.get("Large")
                medium = primary.get("Medium")
                small = primary.get("Small")
                for size_info in (large, medium, small):
                    if isinstance(size_info, dict):
                        url = size_info.get("URL")
                        if url:
                            image_url = url
                            break
            offers = item.get("Offers", {})
            price = None
            listings = offers.get("Listings") if isinstance(offers, dict) else None
            if isinstance(listings, list) and listings:
                first_listing = listings[0]
                price_info = first_listing.get("Price")
                if isinstance(price_info, dict):
                    price = price_info.get("DisplayAmount")
            features = []
            feature_info = info.get("Features") if isinstance(info, dict) else None
            if isinstance(feature_info, dict):
                features = list(feature_info.get("DisplayValues") or [])
            brand = None
            byline = info.get("ByLineInfo") if isinstance(info, dict) else None
            if isinstance(byline, dict):
                brand_info = byline.get("Brand")
                if isinstance(brand_info, dict):
                    brand = (
                        brand_info.get("DisplayValue")
                        or brand_info.get("Label")
                        or brand_info.get("Value")
                    )
                if not brand:
                    manufacturer = byline.get("Manufacturer")
                    if isinstance(manufacturer, dict):
                        brand = (
                            manufacturer.get("DisplayValue")
                            or manufacturer.get("Label")
                            or manufacturer.get("Value")
                        )
            reviews = item.get("CustomerReviews")
            rating = None
            total_reviews = None
            if isinstance(reviews, dict):
                star_rating = reviews.get("StarRating")
                count = reviews.get("Count")

                def _extract_value(value):
                    if isinstance(value, dict):
                        if "DisplayValue" in value:
                            return value.get("DisplayValue")
                        if "Value" in value:
                            return value.get("Value")
                    return value

                star_rating = _extract_value(star_rating)
                count = _extract_value(count)
                if star_rating is not None:
                    try:
                        rating = float(str(star_rating).replace(",", ""))
                    except (TypeError, ValueError):
                        rating = None
                if count is not None:
                    try:
                        total_reviews = int(float(str(count).replace(",", "")))
                    except (TypeError, ValueError):
                        total_reviews = None
            parsed.append(
                {
                    "asin": asin,
                    "title": title,
                    "detail_page_url": detail_page,
                    "image_url": image_url,
                    "price": price,
                    "features": features,
                    "rating": rating,
                    "total_reviews": total_reviews,
                    "brand": brand,
                }
            )
        return parsed


def canonical_path() -> str:
    return "/paapi5/searchitems"
