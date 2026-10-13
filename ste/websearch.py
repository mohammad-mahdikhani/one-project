"""Search Google/Bing/DuckDuckGo for a product on the shop domain."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from .httputil import HttpError, normalize_shop_url, request_url


@dataclass
class SearchHit:
    title: str
    url: str
    engine: str = ""


TAG_RE = re.compile(r"<[^>]+>")
HREF_RE = re.compile(r'''href=["']([^"']+)["']''', re.I)
TITLE_RE = re.compile(r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", re.I | re.S)


def shop_host(shop_url: str) -> str:
    parsed = urlparse(normalize_shop_url(shop_url) or shop_url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _clean_title(html: str) -> str:
    text = TAG_RE.sub(" ", html or "")
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _unwrap(url: str) -> str:
    value = unescape(url or "")
    if value.startswith("/url?"):
        qs = parse_qs(urlparse(value).query)
        value = (qs.get("q") or qs.get("url") or [value])[0]
    if "uddg=" in value:
        qs = parse_qs(urlparse(value).query)
        value = (qs.get("uddg") or [value])[0]
    if value.startswith("//"):
        value = "https:" + value
    return unquote(value)


def parse_hits(html: str, host: str) -> list[SearchHit]:
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for href, title_html in TITLE_RE.findall(html or ""):
        url = _unwrap(href)
        parsed = urlparse(url)
        hit_host = (parsed.hostname or "").lower()
        if hit_host.startswith("www."):
            hit_host = hit_host[4:]
        if not hit_host or host not in hit_host:
            continue
        if url in seen:
            continue
        title = _clean_title(title_html)
        if not title or len(title) < 3:
            continue
        seen.add(url)
        hits.append(SearchHit(title=title, url=url))
    return hits


def _get(url: str, fetch) -> str:
    result = fetch(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0",
            "Accept-Language": "fa,en;q=0.8",
            "Accept": "text/html",
        },
        timeout=12,
    )
    body = result.body if hasattr(result, "body") else result
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


def search_shop(name: str, shop_url: str, sku: str | None = None, fetch=request_url) -> list[SearchHit]:
    host = shop_host(shop_url)
    if not host or not (name or sku):
        return []
    queries = []
    if name:
        queries.append(f'"{name}" site:{host}')
        queries.append(f"{name} site:{host}")
    if sku:
        queries.append(f"{sku} site:{host}")
    engines = (
        ("google", "https://www.google.com/search?hl=fa&num=10&q={q}"),
        ("bing", "https://www.bing.com/search?q={q}"),
        ("ddg", "https://html.duckduckgo.com/html/?q={q}"),
    )
    for query in queries:
        encoded = quote_plus(query)
        for engine, template in engines:
            try:
                html = _get(template.format(q=encoded), fetch)
            except (HttpError, OSError, TimeoutError):
                continue
            hits = parse_hits(html, host)
            if hits:
                for hit in hits:
                    hit.engine = engine
                return hits
    return []
