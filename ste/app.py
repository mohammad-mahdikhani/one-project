"""STE — upload a supplier price list and update matching shop products."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

from .catalog import apply_match, connect, get_settings, list_products, log_import, save_settings, seed_if_empty
from .importer import read_upload, write_template
from .matcher import match_rows
from .normalize import format_money
from .site_seed import SITE_PRODUCTS
from .telegram import TelegramError, crawl_channel
from .woo import WooError, create_product, fetch_products, push_price

ROOT = Path(__file__).resolve().parent
APP = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
APP.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024


def serialize_product(product) -> dict:
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "price": product.price,
        "price_label": format_money(product.price),
        "stock": product.stock,
    }


def serialize_result(result) -> dict:
    target = result.product or result.suggested
    return {
        "row": result.sheet.row,
        "sheet_sku": result.sheet.sku or "",
        "sheet_name": result.sheet.name,
        "sheet_price": result.sheet.price,
        "sheet_price_label": format_money(result.sheet.price),
        "site_id": target.id if target else None,
        "site_sku": target.sku if target else "",
        "site_name": target.name if target else "",
        "site_price": target.price if target else None,
        "site_price_label": format_money(target.price) if target else "—",
        "score": result.score,
        "reason": result.reason,
        "action": result.action,
        "source": result.sheet.source,
        "source_url": result.sheet.source_url,
        "source_date": result.sheet.source_date,
        "delta": (result.sheet.price - target.price) if target and result.sheet.price is not None and target.price is not None else None,
    }


def load_source(settings: dict, source: str):
    if source == "woo":
        return fetch_products(settings)
    with connect() as conn:
        seed_if_empty(conn, SITE_PRODUCTS)
        return list_products(conn)


@APP.get("/")
def home():
    return render_template("app.html")


@APP.get("/list")
def public_list():
    with connect() as conn:
        seed_if_empty(conn, SITE_PRODUCTS)
        products = list_products(conn)
    return render_template("list.html", products=products, money=format_money)


@APP.get("/api/products")
def api_products():
    with connect() as conn:
        seed_if_empty(conn, SITE_PRODUCTS)
        products = list_products(conn)
    return jsonify([serialize_product(item) for item in products])


@APP.get("/api/settings")
def api_settings():
    with connect() as conn:
        return jsonify(get_settings(conn))


@APP.post("/api/settings")
def api_save_settings():
    with connect() as conn:
        return jsonify(save_settings(conn, request.get_json(silent=True) or {}))


@APP.get("/api/template")
def api_template():
    data = write_template()
    return send_file(
        path_or_file=__import__("io").BytesIO(data),
        as_attachment=True,
        download_name="ste-price-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def preview_payload(rows, site_source: str) -> tuple[dict, list]:
    with connect() as conn:
        settings = get_settings(conn)
    products = load_source(settings, site_source)
    results = match_rows(rows, products)
    counts = {
        "rows": len(results),
        "update": sum(1 for item in results if item.action == "update"),
        "suggest": sum(1 for item in results if item.action == "suggest"),
        "create": sum(1 for item in results if item.action == "create"),
        "skip": sum(1 for item in results if item.action == "skip"),
    }
    return counts, results


@APP.post("/api/preview")
def api_preview():
    upload = request.files.get("file")
    if not upload:
        return jsonify(error="فایل اکسل یا PDF را انتخاب کنید"), 400
    source = request.form.get("source") or "local"
    try:
        rows = read_upload(upload.filename or "list.xlsx", upload.read())
        counts, results = preview_payload(rows, source)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except WooError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(counts=counts, results=[serialize_result(item) for item in results])


@APP.post("/api/telegram/crawl")
def api_telegram_crawl():
    payload = request.get_json(silent=True) or {}
    channel = str(payload.get("channel") or "").strip()
    site_source = payload.get("source") or "local"
    try:
        pages = int(payload.get("pages") or 3)
        crawled = crawl_channel(channel, pages=pages)
        counts, results = preview_payload(crawled["rows"], site_source)
    except (TelegramError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    except WooError as exc:
        return jsonify(error=str(exc)), 502
    with connect() as conn:
        save_settings(conn, {"telegram_channel": crawled["channel"], "telegram_pages": str(pages)})
    return jsonify(
        channel=crawled["channel"],
        url=crawled["url"],
        messages=[
            {
                "post": item.post,
                "url": item.url,
                "date": item.date,
                "text": item.text[:280],
                "rows": len(item.rows),
                "has_document": item.has_document,
            }
            for item in crawled["messages"][:40]
        ],
        counts=counts,
        results=[serialize_result(item) for item in results],
    )


@APP.post("/api/apply")
def api_apply():
    payload = request.get_json(silent=True) or {}
    filename = str(payload.get("filename") or "list.xlsx")
    source = payload.get("source") or "local"
    accept_suggested = bool(payload.get("accept_suggested"))
    create_missing = bool(payload.get("create_missing"))
    rows_data = payload.get("results") or []
    if not rows_data:
        return jsonify(error="نتیجه پیش‌نمایش خالی است"), 400

    from .matcher import MatchResult, Product, SheetRow

    rebuilt = []
    for row in rows_data:
        sheet = SheetRow(
            row=int(row.get("row") or 0),
            name=row.get("sheet_name") or "",
            sku=row.get("sheet_sku") or None,
            price=row.get("sheet_price"),
        )
        product = None
        suggested = None
        if row.get("action") == "update" and row.get("site_id"):
            product = Product(
                id=int(row["site_id"]),
                name=row.get("site_name") or sheet.name,
                sku=row.get("site_sku") or "",
                price=row.get("site_price"),
            )
        if row.get("action") == "suggest" and row.get("site_id"):
            suggested = Product(
                id=int(row["site_id"]),
                name=row.get("site_name") or "",
                sku=row.get("site_sku") or "",
                price=row.get("site_price"),
            )
        rebuilt.append(
            MatchResult(
                sheet=sheet,
                product=product,
                score=int(row.get("score") or 0),
                reason=row.get("reason") or "",
                action=row.get("action") or "create",
                suggested=suggested,
            )
        )

    counts = {"updated": 0, "created": 0, "suggested": 0, "skipped": 0}
    errors = []
    if source == "woo":
        with connect() as conn:
            settings = get_settings(conn)
        for result in rebuilt:
            try:
                if result.action == "update" and result.product and result.sheet.price is not None:
                    push_price(settings, result.product.id, result.sheet.price, result.sheet.sku)
                    counts["updated"] += 1
                elif result.action == "suggest" and accept_suggested and result.suggested and result.sheet.price is not None:
                    push_price(settings, result.suggested.id, result.sheet.price, result.sheet.sku)
                    counts["updated"] += 1
                elif result.action == "create" and create_missing and result.sheet.price is not None:
                    create_product(settings, result.sheet.name, result.sheet.price, result.sheet.sku)
                    counts["created"] += 1
                else:
                    if result.action == "suggest":
                        counts["suggested"] += 1
                    else:
                        counts["skipped"] += 1
            except WooError as exc:
                errors.append({"row": result.sheet.row, "error": str(exc)})
    else:
        with connect() as conn:
            for result in rebuilt:
                status = apply_match(conn, result, accept_suggested, create_missing)
                if status == "updated":
                    counts["updated"] += 1
                elif status == "created":
                    counts["created"] += 1
                else:
                    if result.action == "suggest":
                        counts["suggested"] += 1
                    else:
                        counts["skipped"] += 1
            log_import(conn, filename, counts)

    return jsonify(counts=counts, errors=errors)


@APP.get("/header.jpg")
def legacy_header():
    return send_from_directory(ROOT.parent, "header.jpg")


def create_app() -> Flask:
    return APP


if __name__ == "__main__":
    APP.run(host="127.0.0.1", port=5055, debug=False)
