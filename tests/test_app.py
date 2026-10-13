from io import BytesIO
from pathlib import Path

from ste.app import APP
from ste.catalog import connect, seed_if_empty
from ste.importer import write_template
from ste.site_seed import SITE_PRODUCTS

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "telegram_channel.html"


def test_preview_and_apply(tmp_path, monkeypatch):
    db = tmp_path / "ste.db"
    monkeypatch.setattr("ste.catalog.default_db_path", lambda: db)
    with connect(db) as conn:
        seed_if_empty(conn, SITE_PRODUCTS)

    client = APP.test_client()
    response = client.post(
        "/api/preview",
        data={"source": "local", "file": (BytesIO(write_template()), "list.xlsx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["counts"]["update"] >= 1
    apply = client.post(
        "/api/apply",
        json={
            "filename": "list.xlsx",
            "source": "local",
            "accept_suggested": True,
            "create_missing": True,
            "results": body["results"],
        },
    )
    assert apply.status_code == 200
    assert apply.get_json()["counts"]["updated"] >= 1
    products = client.get("/api/products").get_json()
    three_stage = next(item for item in products if item["sku"] == "01103008")
    assert three_stage["price"] == 132000000


def test_telegram_crawl_endpoint(tmp_path, monkeypatch):
    db = tmp_path / "ste.db"
    monkeypatch.setattr("ste.catalog.default_db_path", lambda: db)
    html = FIXTURE.read_text(encoding="utf-8")
    monkeypatch.setattr("ste.telegram.fetch_preview", lambda url: html)
    monkeypatch.setattr("ste.app.crawl_channel", lambda channel, pages=3: __import__("ste.telegram", fromlist=["crawl_channel"]).crawl_channel(channel, pages=1, fetch=lambda url: html))
    with connect(db) as conn:
        seed_if_empty(conn, SITE_PRODUCTS)
    client = APP.test_client()
    response = client.post("/api/telegram/crawl", json={"channel": "@aquajoy_prices", "source": "local"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["channel"] == "aquajoy_prices"
    assert body["counts"]["update"] >= 1
    assert body["counts"]["create"] >= 1
