"""Optional WooCommerce REST helpers for pushing matched prices to the live shop."""

from __future__ import annotations

import base64
from urllib.parse import quote

from .httputil import HttpError, normalize_shop_url, request_json
from .matcher import Product, sku_keys
from .normalize import name_tokens, normalize_name


class WooError(RuntimeError):
    pass


def site_ready(settings: dict) -> bool:
    return bool((settings.get("wp_url") or "").strip() and (settings.get("woo_key") or "").strip() and (settings.get("woo_secret") or "").strip())


def site_connected(settings: dict) -> bool:
    return site_ready(settings) and str(settings.get("site_connected") or "") == "1"


def _shop_base(settings: dict) -> tuple[str, str, str]:
    base = normalize_shop_url(settings.get("wp_url") or "")
    key = (settings.get("woo_key") or "").strip()
    secret = (settings.get("woo_secret") or "").strip()
    if not base or not key or not secret:
        raise WooError("آدرس فروشگاه و کلید ووکامرس را در تنظیمات بگذارید")
    return base, key, secret


def _woo_urls(base: str, path: str, key: str, secret: str) -> list[str]:
    path = path.lstrip("/")
    auth = f"consumer_key={key}&consumer_secret={secret}"
    pretty = f"{base}/wp-json/wc/v3/{path}"
    pretty += "&" if "?" in pretty else "?"
    pretty += auth
    route = path.replace("?", "&", 1)
    fallback = f"{base}/?rest_route=/wc/v3/{route}&{auth}"
    index = f"{base}/index.php?rest_route=/wc/v3/{route}&{auth}"
    urls = [pretty, fallback, index]
    if "://" in base:
        scheme, rest = base.split("://", 1)
        host = rest.split("/")[0]
        if host.startswith("www."):
            alt = f"{scheme}://{host[4:]}"
        else:
            alt = f"{scheme}://www.{host}"
        if alt != base:
            urls.append(pretty.replace(base, alt, 1))
    return urls


def _explain(status: int, body: object) -> WooError:
    if status == 401:
        return WooError("کلید ووکامرس رد شد. در ووکامرس کلید جدید با دسترسی خواندن/نوشتن بسازید و دوباره کپی کنید.")
    if status == 404:
        return WooError("آدرس REST پیدا نشد. در وردپرس تنظیمات → پیوندهای یکتا را روی «نام نوشته» بگذارید و ذخیره کنید.")
    if status == 403:
        return WooError("هاست درخواست را بست. افزونه امنیتی یا کلودفلر REST را مسدود کرده است.")
    if isinstance(body, str) and "<" in body:
        return WooError("سایت صفحه HTML داد، نه ووکامرس. آدرس فروشگاه را بدون مسیر اضافه بگذارید.")
    return WooError(f"ووکامرس پاسخ {status} داد")


def _headers(key: str, secret: str, use_basic: bool) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if use_basic:
        token = base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def _call(url: str, method: str, key: str, secret: str, payload: dict | None, timeout: int, insecure: bool, use_basic: bool):
    return request_json(
        url,
        method=method,
        headers=_headers(key, secret, use_basic),
        payload=payload,
        timeout=timeout,
        insecure=insecure,
    )


def _request(settings: dict, method: str, path: str, payload: dict | None = None, timeout: int = 35) -> tuple[object, dict]:
    base, key, secret = _shop_base(settings)
    insecure = str(settings.get("ssl_insecure") or "") == "1"
    last_error: Exception | None = None
    tried: set[tuple[str, bool, bool]] = set()

    for url in _woo_urls(base, path, key, secret)[:3]:
        for use_basic in (False, True):
            mode = (url, use_basic, insecure)
            if mode in tried:
                continue
            tried.add(mode)
            try:
                status, body, headers = _call(url, method, key, secret, payload, timeout, insecure, use_basic)
            except HttpError as exc:
                if str(exc) == "ssl" and not insecure:
                    try:
                        status, body, headers = _call(url, method, key, secret, payload, timeout, True, use_basic)
                        settings["ssl_insecure"] = "1"
                        insecure = True
                    except HttpError:
                        last_error = WooError("گواهی https سایت یا ویندوز مشکل دارد.")
                        continue
                elif str(exc) == "سایت دیر جواب می‌دهد":
                    raise WooError("سایت دیر جواب می‌دهد. دوباره تست کنید؛ اگر باز نشد از همان اینترنت فروشگاه امتحان کنید.") from exc
                else:
                    raise WooError("به سایت وصل نشد. آدرس را مثل https://shop.com بگذارید و اینترنت را چک کنید.") from exc
            if 200 <= status < 300:
                return body, headers
            last_error = _explain(status, body)
            if status == 401 and not use_basic:
                continue
            if status == 401:
                raise last_error
            if status == 404:
                break
            raise last_error
    raise last_error or WooError("اتصال به فروشگاه برقرار نشد")


def test_connection(settings: dict) -> dict:
    settings = dict(settings)
    settings["wp_url"] = normalize_shop_url(settings.get("wp_url") or "")
    body, headers = _request(settings, "GET", "products?per_page=1", timeout=40)
    count = headers.get("x-wp-total")
    sample = ""
    if isinstance(body, list) and body:
        sample = str(body[0].get("name") or "")
        if not count:
            count = "1"
    elif isinstance(body, dict) and body.get("code"):
        raise WooError(str(body.get("message") or body.get("code")))
    return {
        "ok": True,
        "url": settings["wp_url"],
        "product_count": int(count or 0),
        "sample": sample,
        "ssl_insecure": str(settings.get("ssl_insecure") or "") == "1",
    }


def _header_int(headers: dict, key: str) -> int:
    try:
        return int(headers.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def product_from_woo(row: dict) -> Product:
    sku = str(row.get("sku") or "")
    barcode = ""
    for meta in row.get("meta_data") or []:
        if str(meta.get("key") or "").lower() in {"barcode", "_barcode"}:
            barcode = str(meta.get("value") or "")
    price = row.get("regular_price") or row.get("price") or None
    return Product(
        id=int(row.get("id") or 0),
        name=str(row.get("name") or ""),
        sku=sku,
        barcode=barcode,
        price=int(float(price)) if price not in (None, "") else None,
        sale_price=int(float(row["sale_price"])) if row.get("sale_price") else None,
        stock=row.get("stock_quantity"),
        permalink=str(row.get("permalink") or ""),
        slug=str(row.get("slug") or ""),
    )


def fetch_products(settings: dict, per_page: int = 100) -> list[Product]:
    page = 1
    items: list[Product] = []
    seen: set[int] = set()
    while page <= 80:
        try:
            batch, headers = _request(settings, "GET", f"products?per_page={per_page}&page={page}&status=publish")
        except WooError:
            if items:
                break
            raise
        if not isinstance(batch, list) or not batch:
            break
        for row in batch:
            product = product_from_woo(row)
            if product.id and product.id not in seen:
                seen.add(product.id)
                items.append(product)
        total = _header_int(headers, "x-wp-total")
        total_pages = _header_int(headers, "x-wp-totalpages")
        if total and len(items) >= total:
            break
        if total_pages and page >= total_pages:
            break
        if not total_pages and not total and len(batch) < per_page:
            if len(batch) not in {10, 20, 50}:
                break
        page += 1
    return items


def find_products(settings: dict, sku: str | None = None, search: str | None = None, limit: int = 10) -> list[Product]:
    seen: dict[int, Product] = {}
    paths: list[str] = []
    if sku:
        keys: list[str] = []
        for key in [str(sku).strip(), *sorted(sku_keys(sku), key=len, reverse=True)]:
            if key and key not in keys:
                keys.append(key)
        for key in keys[:4]:
            paths.append(f"products?sku={quote(key, safe='')}&per_page=5")
    if search:
        query = " ".join(name_tokens(search)[:6]) or normalize_name(search)[:48]
        if query:
            paths.append(f"products?search={quote(query, safe='')}&per_page={limit}")
    for path in paths:
        try:
            batch, _headers = _request(settings, "GET", path, timeout=25)
        except WooError:
            continue
        if not isinstance(batch, list):
            continue
        for row in batch:
            product = product_from_woo(row)
            if product.id:
                seen[product.id] = product
        if sku and seen:
            break
    return list(seen.values())


def lookup_sheet(settings: dict, sheet) -> list[Product]:
    return find_products(settings, sku=getattr(sheet, "sku", None), search=getattr(sheet, "name", None))


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
