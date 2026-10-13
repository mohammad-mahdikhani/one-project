from ste.app import APP
from ste.catalog import connect
from ste.woo import WooError


def test_site_status_starts_disconnected(tmp_path, monkeypatch):
    monkeypatch.setattr("ste.catalog.default_db_path", lambda: tmp_path / "ste.db")
    with connect(tmp_path / "ste.db"):
        pass
    status = APP.test_client().get("/api/site/status").get_json()
    assert status["connected"] is False
    assert status["source"] == "local"


def test_site_test_saves_and_reports(tmp_path, monkeypatch):
    monkeypatch.setattr("ste.catalog.default_db_path", lambda: tmp_path / "ste.db")
    monkeypatch.setattr(
        "ste.app.test_connection",
        lambda settings: {"ok": True, "url": settings["wp_url"].rstrip("/"), "product_count": 12, "sample": "فیلتر"},
    )
    with connect(tmp_path / "ste.db"):
        pass
    response = APP.test_client().post(
        "/api/site/test",
        json={"wp_url": "https://shop.example", "woo_key": "ck_1", "woo_secret": "cs_1"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["connected"] is True
    assert body["product_count"] == 12
    status = APP.test_client().get("/api/site/status").get_json()
    assert status["connected"] is True
    assert status["source"] == "woo"
    assert status["has_keys"] is True


def test_site_test_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("ste.catalog.default_db_path", lambda: tmp_path / "ste.db")
    monkeypatch.setattr("ste.app.test_connection", lambda settings: (_ for _ in ()).throw(WooError("کلید غلط است")))
    with connect(tmp_path / "ste.db"):
        pass
    response = APP.test_client().post(
        "/api/site/test",
        json={"wp_url": "https://shop.example", "woo_key": "bad", "woo_secret": "bad"},
    )
    assert response.status_code == 502
    assert "کلید" in response.get_json()["error"]
