"""Optional WooCommerce REST helpers for pushing matched prices to the live shop."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .matcher import Product


class WooError(RuntimeError):
    pass


def _request(settings: dict, method: str, path: str, payload: dict | None = None) -> object:
    base = (settings.get("wp_url") or "").rstrip("/")
    key = settings.get("woo_key") or ""
    secret = settings.get("woo_secret") or ""
    if not base or not key or not secret:
        raise WooError("آدرس فروشگاه و کلید ووکامرس را در تنظیمات بگذارید")
    url = f"{base}/wp-json/wc/v3/{path.lstrip('/')}"
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}consumer_key={key}&consumer_secret={secret}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:240]
        raise WooError(f"ووکامرس پاسخ {exc.code} داد: {detail}") from exc
    except URLError as exc:
        raise WooError(f"اتصال به فروشگاه برقرار نشد: {exc.reason}") from exc


def fetch_products(settings: dict, per_page: int = 100) -> list[Product]:
    page = 1
    items: list[Product] = []
    while True:
        batch = _request(settings, "GET", f"products?per_page={per_page}&page={page}&status=any")
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
    body = _request(settings, "PUT", f"products/{product_id}", payload)
    if not isinstance(body, dict):
        raise WooError("پاسخ ووکامرس نامعتبر بود")
    return body


def create_product(settings: dict, name: str, price: int, sku: str | None = None) -> dict:
    payload = {"name": name, "type": "simple", "regular_price": str(price), "status": "publish"}
    if sku:
        payload["sku"] = sku
    body = _request(settings, "POST", "products", payload)
    if not isinstance(body, dict) or not body.get("id"):
        raise WooError("ساخت کالا در ووکامرس انجام نشد")
    return body
