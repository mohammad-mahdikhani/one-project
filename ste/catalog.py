"""Local product catalog used by the STE preview app."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .matcher import Product

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_db_path() -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    return DATA / "ste.db"


@contextmanager
def connect(path: Path | None = None):
    db = path or default_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          sku TEXT,
          barcode TEXT,
          name TEXT NOT NULL,
          price INTEGER,
          sale_price INTEGER,
          stock INTEGER,
          woo_id INTEGER,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS import_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          filename TEXT,
          updated INTEGER NOT NULL,
          created INTEGER NOT NULL,
          suggested INTEGER NOT NULL,
          skipped INTEGER NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )


def list_products(conn: sqlite3.Connection) -> list[Product]:
    rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    return [product_from_row(row) for row in rows]


def product_from_row(row) -> Product:
    return Product(
        id=row["id"],
        name=row["name"],
        sku=row["sku"] or "",
        barcode=row["barcode"] or "",
        price=row["price"],
        sale_price=row["sale_price"],
        stock=row["stock"],
    )


def upsert_product(conn: sqlite3.Connection, product: Product) -> Product:
    now = _now()
    if product.id:
        conn.execute(
            """UPDATE products SET sku=?, barcode=?, name=?, price=?, sale_price=?, stock=?, updated_at=?
               WHERE id=?""",
            (product.sku, product.barcode, product.name, product.price, product.sale_price, product.stock, now, product.id),
        )
        return product
    cur = conn.execute(
        """INSERT INTO products (sku, barcode, name, price, sale_price, stock, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (product.sku, product.barcode, product.name, product.price, product.sale_price, product.stock, now, now),
    )
    product.id = cur.lastrowid
    return product


def apply_match(conn: sqlite3.Connection, result, accept_suggested: bool, create_missing: bool) -> str:
    sheet = result.sheet
    target = result.product
    if result.action == "suggest" and accept_suggested:
        target = result.suggested
    if target:
        target.price = sheet.price if sheet.price is not None else target.price
        if sheet.sku and not target.sku:
            target.sku = sheet.sku
        if sheet.stock is not None:
            target.stock = sheet.stock
        upsert_product(conn, target)
        return "updated"
    if result.action == "create" and create_missing and sheet.price is not None:
        upsert_product(
            conn,
            Product(id=0, name=sheet.name, sku=sheet.sku or "", price=sheet.price, stock=sheet.stock),
        )
        return "created"
    return "skipped"


def log_import(conn: sqlite3.Connection, filename: str, counts: dict) -> None:
    conn.execute(
        """INSERT INTO import_logs (filename, updated, created, suggested, skipped, created_at)
           VALUES (?,?,?,?,?,?)""",
        (
            filename,
            counts.get("updated", 0),
            counts.get("created", 0),
            counts.get("suggested", 0),
            counts.get("skipped", 0),
            _now(),
        ),
    )


def seed_if_empty(conn: sqlite3.Connection, products: list[Product]) -> None:
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count:
        return
    for product in products:
        upsert_product(
            conn,
            Product(
                id=0,
                name=product.name,
                sku=product.sku,
                barcode=product.barcode,
                price=product.price,
                sale_price=product.sale_price,
                stock=product.stock,
            ),
        )


def get_settings(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def save_settings(conn: sqlite3.Connection, payload: dict) -> dict:
    allowed = {
        "wp_url",
        "woo_key",
        "woo_secret",
        "create_missing",
        "accept_suggested",
        "telegram_channel",
        "telegram_pages",
    }
    for key, value in payload.items():
        if key not in allowed:
            continue
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value or "")),
        )
    return get_settings(conn)
