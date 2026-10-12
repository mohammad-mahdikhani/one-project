"""Crawl a public Telegram channel preview and turn posts into price rows."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .importer import read_message_text, read_upload
from .matcher import SheetRow

CHANNEL_RE = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?@?([A-Za-z0-9_]{4,64})")
POST_RE = re.compile(
    r'data-post="(?P<post>[^"]+)"(?P<body>.*?)(?=data-post="|$)',
    re.S,
)
TEXT_RE = re.compile(
    r'class="tgme_widget_message_text[^"]*"(?:[^>]*)>(?P<text>.*?)</div>',
    re.S,
)
TIME_RE = re.compile(r'<time[^>]*datetime="(?P<date>[^"]+)"')
DOC_RE = re.compile(r'class="tgme_widget_message_document[^"]*"', re.I)
BEFORE_RE = re.compile(r'href="(https://t\.me/s/[^"]+\?before=\d+)"')
TAG_RE = re.compile(r"<[^>]+>")


class TelegramError(RuntimeError):
    pass


@dataclass
class ChannelMessage:
    post: str
    url: str
    date: str
    text: str
    has_document: bool = False
    rows: list[SheetRow] = field(default_factory=list)


def channel_slug(value: str) -> str:
    text = (value or "").strip()
    if text.startswith("@"):
        text = text[1:]
    match = CHANNEL_RE.search(text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_]{4,64}", text):
        return text
    raise TelegramError("آدرس کانال را مثل @aquajoy یا t.me/aquajoy بگذارید")


def preview_url(slug: str, before: str | None = None) -> str:
    url = f"https://t.me/s/{slug}"
    if before:
        url += f"?before={before}"
    return url


def html_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html or "", flags=re.I)
    text = re.sub(r"</p>|<p[^>]*>", "\n", text, flags=re.I)
    text = TAG_RE.sub(" ", text)
    return unescape(text)


def parse_channel_html(html: str, slug: str) -> list[ChannelMessage]:
    messages: list[ChannelMessage] = []
    for match in POST_RE.finditer(html or ""):
        post = match.group("post")
        body = match.group("body")
        text_match = TEXT_RE.search(body)
        text = html_text(text_match.group("text")) if text_match else ""
        time_match = TIME_RE.search(body)
        date = time_match.group("date") if time_match else ""
        message = ChannelMessage(
            post=post,
            url=f"https://t.me/{post}",
            date=date,
            text=text,
            has_document=bool(DOC_RE.search(body)),
            rows=read_message_text(
                text,
                source={"source": "telegram", "url": f"https://t.me/{post}", "date": date},
            ),
        )
        if message.text or message.rows or message.has_document:
            messages.append(message)
    return messages


def fetch_preview(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 STE-PriceBot (+https://t.me/s) Telegram price sync",
            "Accept-Language": "fa,en;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=25) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise TelegramError(f"تلگرام پاسخ {exc.code} داد") from exc
    except URLError as exc:
        raise TelegramError(f"به پیش‌نمایش کانال وصل نشد: {exc.reason}") from exc


def crawl_channel(channel: str, pages: int = 3, fetch=fetch_preview) -> dict:
    slug = channel_slug(channel)
    if slug.lower() == "demo":
        fixture = Path(__file__).resolve().parent.parent / "tests/fixtures/telegram_channel.html"
        html = fixture.read_text(encoding="utf-8")
        fetch = lambda _url, _html=html: _html
        pages = 1
    url = preview_url(slug)
    messages: list[ChannelMessage] = []
    seen: set[str] = set()
    for _ in range(max(1, min(pages, 6))):
        html = fetch(url)
        batch = parse_channel_html(html, slug)
        fresh = [item for item in batch if item.post not in seen]
        if not fresh:
            break
        for item in fresh:
            seen.add(item.post)
        messages.extend(fresh)
        before = BEFORE_RE.search(html)
        if not before:
            break
        url = urljoin("https://t.me/", before.group(1))
    messages.sort(key=lambda item: item.date, reverse=True)
    rows: list[SheetRow] = []
    for index, message in enumerate(messages):
        for row in message.rows:
            row.row = len(rows) + 1
            row.raw["message_index"] = index
            rows.append(row)
    return {
        "channel": slug,
        "url": preview_url(slug),
        "messages": messages,
        "rows": rows,
    }


def attach_upload(rows: list[SheetRow], filename: str, data: bytes) -> list[SheetRow]:
    extra = read_upload(filename, data)
    for row in extra:
        row.source = row.source or "file"
        rows.append(row)
    return rows
