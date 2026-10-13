from pathlib import Path

from ste.matcher import match_rows
from ste.site_seed import SITE_PRODUCTS
from ste.telegram import channel_slug, crawl_channel, parse_channel_html

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "telegram_channel.html"


def test_channel_slug():
    assert channel_slug("@aquajoy_prices") == "aquajoy_prices"
    assert channel_slug("https://t.me/s/aquajoy_prices") == "aquajoy_prices"


def test_parse_public_channel_and_match_site():
    html = FIXTURE.read_text(encoding="utf-8")
    messages = parse_channel_html(html, "aquajoy_prices")
    assert len(messages) == 3
    rows = [row for message in messages for row in message.rows]
    skus = {row.sku for row in rows}
    assert "01103008" in skus
    assert "01105512" in skus
    assert any("AJ-3500" in (row.name or "") or "3500" in (row.name or "") for row in rows)
    results = match_rows(rows, list(SITE_PRODUCTS))
    updates = [item for item in results if item.action == "update"]
    missing = [item for item in results if item.action == "create"]
    assert any(item.sheet.sku == "01103008" for item in updates)
    assert any(item.product and "الیت" in item.product.name for item in updates)
    assert any("3500" in item.sheet.name for item in missing)


def test_crawl_uses_fetcher_not_live_network():
    html = FIXTURE.read_text(encoding="utf-8")
    crawled = crawl_channel("https://t.me/aquajoy_prices", pages=1, fetch=lambda url: html)
    assert crawled["channel"] == "aquajoy_prices"
    assert len(crawled["rows"]) >= 4
