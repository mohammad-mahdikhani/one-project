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
