from ste.woo import WooError
from ste import woo as woo_mod


def test_connection_reads_products(monkeypatch):
    monkeypatch.setattr(
        "ste.woo.request_json",
        lambda *args, **kwargs: (200, [{"name": "فیلتر کربن"}], {"x-wp-total": "12"}),
    )
    info = woo_mod.test_connection({"wp_url": "aquasafe.ir", "woo_key": "ck_1", "woo_secret": "cs_1"})
    assert info["ok"] is True
    assert info["url"] == "https://aquasafe.ir"
    assert info["product_count"] == 12
    assert info["sample"] == "فیلتر کربن"


def test_connection_401(monkeypatch):
    monkeypatch.setattr(
        "ste.woo.request_json",
        lambda *args, **kwargs: (401, {"code": "woocommerce_rest_cannot_view"}, {}),
    )
    try:
        woo_mod.test_connection({"wp_url": "https://shop.com", "woo_key": "ck_bad", "woo_secret": "cs_bad"})
    except WooError as exc:
        assert "کلید" in str(exc)
    else:
        raise AssertionError("expected WooError")


def test_fetch_uses_total_pages_when_shop_caps_per_page(monkeypatch):
    calls = []

    def fake_request(url, method="GET", headers=None, payload=None, timeout=25, insecure=False):
        calls.append(url)
        if "&page=1&" in url or url.endswith("page=1"):
            return (200, [{"id": 1, "name": "فیلتر یک", "sku": "01306575", "regular_price": "1"}], {"x-wp-total": "2", "x-wp-totalpages": "2"})
        if "&page=2&" in url or url.endswith("page=2"):
            return (200, [{"id": 2, "name": "فیلتر دو", "sku": "01306576", "regular_price": "2"}], {"x-wp-total": "2", "x-wp-totalpages": "2"})
        return (200, [], {"x-wp-total": "2", "x-wp-totalpages": "2"})

    monkeypatch.setattr("ste.woo.request_json", fake_request)
    items = woo_mod.fetch_products({"wp_url": "https://shop.com", "woo_key": "ck_1", "woo_secret": "cs_1"}, per_page=100)
    assert [item.sku for item in items] == ["01306575", "01306576"]
    assert any("page=2" in url for url in calls)


def test_find_products_tries_sku_without_leading_zeros(monkeypatch):
    seen = []

    def fake_request(url, method="GET", headers=None, payload=None, timeout=25, insecure=False):
        seen.append(url)
        if "sku=01306575" in url or "sku=1306575" in url:
            return (200, [{"id": 9, "name": "فیلتر الیافی", "sku": "01306575", "regular_price": "18"}], {})
        return (200, [], {})

    monkeypatch.setattr("ste.woo.request_json", fake_request)
    items = woo_mod.find_products(
        {"wp_url": "https://shop.com", "woo_key": "ck_1", "woo_secret": "cs_1"},
        sku="01306575",
    )
    assert items and items[0].id == 9
    assert seen


def test_connection_timeout(monkeypatch):
    from ste.httputil import HttpError

    def boom(*args, **kwargs):
        raise HttpError("سایت دیر جواب می‌دهد")

    monkeypatch.setattr("ste.woo.request_json", boom)
    try:
        woo_mod.test_connection({"wp_url": "https://shop.com", "woo_key": "ck_1", "woo_secret": "cs_1"})
    except WooError as exc:
        assert "دیر" in str(exc)
    else:
        raise AssertionError("expected WooError")
