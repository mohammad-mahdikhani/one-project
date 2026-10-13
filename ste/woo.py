"""Optional WooCommerce REST helpers for pushing matched prices to the live shop."""

from __future__ import annotations

import base64
import json
import socket
from ssl import SSLError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .matcher import Product


class WooError(RuntimeError):
    pass


def site_ready(settings: dict) -> bool:
    return bool((settings.get("wp_url") or "").strip() and (settings.get("woo_key") or "").strip() and (settings.get("woo_secret") or "").strip())


def site_connected(settings: dict) -> bool:
    return site_ready(settings) and str(settings.get("site_connected") or "") == "1"


def _shop_base(settings: dict) -> tuple[str, str, str]:
    base = (settings.get("wp_url") or "").strip().rstrip("/")
    key = (settings.get("woo_key") or "").strip()
    secret = (settings.get("woo_secret") or "").strip()
    if not base or not key or not secret:
        raise WooError("آدرس فروشگاه و کلید ووکامرس را در تنظیمات بگذارید")
    if not base.startswith("http://") and not base.startswith("https://"):
        raise WooError("آدرس سایت باید با https:// شروع شود")
    return base, key, secret


def _woo_urls(base: str, path: str, key: str, secret: str) -> list[str]:
    path = path.lstrip("/")
    auth = f"consumer_key={key}&consumer_secret={secret}"
    pretty = f"{base}/wp-json/wc/v3/{path}"
    pretty += "&" if "?" in pretty else "?"
    pretty += auth
    route = path.replace("?", "&", 1)
    fallback = f"{base}/?rest_route=/wc/v3/{route}&{auth}"
    return [pretty, fallback]


def _request(settings: dict, method: str, path: str, payload: dict | None = None, timeout: int = 30) -> tuple[object, dict]:
    base, key, secret = _shop_base(settings)
    token = base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode("ascii")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 STE-PriceSync/1.0",
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
    }
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None
    for url in _woo_urls(base, path, key, secret):
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                out_headers = {item.lower(): value for item, value in response.headers.items()}
                return (json.loads(raw) if raw else {}), out_headers
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:240]
            if exc.code == 401:
                last_error = WooError(
                    "کلید ووکامرس رد شد. در ووکامرس کلید جدید با دسترسی خواندن/نوشتن بسازید و دوباره کپی کنید."
                )
                continue
            if exc.code == 404:
                last_error = WooError(
                    "آدرس REST پیدا نشد. در وردپرس تنظیمات → پیوندهای یکتا را روی «نام نوشته» بگذارید و ذخیره کنید."
                )
                continue
            if exc.code == 403:
                last_error = WooError("هاست درخواست را بست. افزونه امنیتی یا کلودفلر REST را مسدود کرده است.")
                continue
            if "<" in detail:
                last_error = WooError("سایت صفحه HTML داد، نه ووکامرس. آدرس فروشگاه را بدون مسیر اضافه بگذارید.")
                continue
            last_error = WooError(f"ووکامرس پاسخ {exc.code} داد")
        except (TimeoutError, socket.timeout) as exc:
            last_error = WooError("سایت دیر جواب می‌دهد. دوباره تست کنید؛ اگر باز نشد از همان شبکه سایت امتحان کنید.")
        except SSLError as exc:
            last_error = WooError("گواهی https سایت مشکل دارد.")
        except URLError as exc:
            last_error = WooError("به سایت وصل نشد. اینترنت و آدرس https://aquasafe.ir را چک کنید.")
    raise last_error or WooError("اتصال به فروشگاه برقرار نشد")


def test_connection(settings: dict) -> dict:
    body, headers = _request(settings, "GET", "products?per_page=1&status=any", timeout=25)
    count = headers.get("x-wp-total")
    sample = ""
    if isinstance(body, list) and body:
        sample = str(body[0].get("name") or "")
        if not count:
            count = "1"
    return {
        "ok": True,
        "url": (settings.get("wp_url") or "").rstrip("/"),
        "product_count": int(count or 0),
        "sample": sample,
    }


def fetch_products(settings: dict, per_page: int = 100) -> list[Product]:
    page = 1
    items: list[Product] = []
    while True:
        batch, _headers = _request(settings, "GET", f"products?per_page={per_page}&page={page}&status=any")
        if not isinstance(batch, list) or not batch:
            break
        for row in batch:
            sku = str(row.get("sku") or "")
            barcode = ""
            for meta in row.get("meta_data") or []:
                if str(meta.get("key") or "").lower() in {"barcode", "_barcode"}:
                    barcode = str(meta.get("value") or "")
            price = row.get("regular_price") or row.get("price") or None
            items.append(
                Product(
                    id=int(row.get("id") or 0),
                    name=str(row.get("name") or ""),
                    sku=sku,
                    barcode=barcode,
                    price=int(float(price)) if price not in (None, "") else None,
                    sale_price=int(float(row["sale_price"])) if row.get("sale_price") else None,
                    stock=row.get("stock_quantity"),
                )
            )
        if len(batch) < per_page:
            break
        page += 1
    return items


def push_price(settings: dict, product_id: int, price: int, sku: str | None = None) -> dict:
    payload = {"regular_price": str(price)}
    if sku:
        payload["sku"] = sku
    body, _headers = _request(settings, "PUT", f"products/{product_id}", payload)
    if not isinstance(body, dict):
        raise WooError("پاسخ ووکامرس نامعتبر بود")
    return body


def create_product(settings: dict, name: str, price: int, sku: str | None = None) -> dict:
    payload = {"name": name, "type": "simple", "regular_price": str(price), "status": "publish"}
    if sku:
        payload["sku"] = sku
    body, _headers = _request(settings, "POST", "products", payload)
    if not isinstance(body, dict) or not body.get("id"):
        raise WooError("ساخت کالا در ووکامرس انجام نشد")
    return body
