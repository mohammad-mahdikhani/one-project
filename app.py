"""دفترچی — صندوق فروش، انبار و حسابداری."""

from __future__ import annotations

import base64
import calendar
import functools
import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
import smtplib
import socket
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

import jdatetime
from flask import Flask, abort, jsonify, request, send_file, send_from_directory, session
from openpyxl import Workbook, load_workbook
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

# ساعت ایران، بدون بسته tzdata. ویندوز آفلاین هم همین را دارد.
TEHRAN = timezone(timedelta(hours=3, minutes=30))
DATA = Path(os.environ.get("DAFTARCHI_DATA", Path(__file__).resolve().parent / "data"))
UPLOAD = DATA / "uploads"
DB_PATH = DATA / "daftarchi.db"
INITIAL_PHONE = "09120000000"
INITIAL_PASSWORD = "daftarchi"
JMONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
PLANS = {
    "3m": ("سه ماهه", 3, "price_3m"),
    "6m": ("شش ماهه", 6, "price_6m"),
    "12m": ("یک ساله", 12, "price_12m"),
    "50y": ("پنجاه ساله", 600, "price_50y"),
}
HEADER_MAP = {
    "name": "name", "نام": "name", "عنوان": "name", "نام کالا": "name", "نام محصول": "name", "عنوان کالا": "name",
    "sku": "sku", "کد": "sku", "کد کالا": "sku", "کد محصول": "sku",
    "barcode": "barcode", "بارکد": "barcode",
    "price": "price", "قیمت": "price", "قیمت فروش": "price", "فی فروش": "price",
    "stock": "stock", "موجودی": "stock", "موجودی انبار": "stock",
    "cost": "cost", "قیمت خرید": "cost",
    "image": "image", "تصویر": "image", "آدرس تصویر": "image",
    "tax_code": "tax_code", "شناسه مودیان": "tax_code", "شناسه کالا": "tax_code", "sstid": "tax_code",
}
DEFAULT_SETTINGS = {
    "wp_url": "https://webakery.ir",
    "woo_key": "",
    "woo_secret": "",
    "pos_provider": "manual",
    "pos_host": "",
    "pos_port": "1362",
    "pos_terminal": "",
    "gateway": "zibal",
    "gateway_merchant": "6a331116da557b902563c32f",
    "gateway_callback": "https://webakery.ir",
    "gateway_sandbox": "0",
    "license_merchant": "6a331116da557b902563c32f",
    "sms_provider": "internal",
    "sms_api_key": "",
    "sms_sender": "",
    "sms_username": "",
    "sms_password": "",
    "manager_phone": "",
    "sms_on_close": "1",
    "sms_on_sale": "0",
    "sms_low_stock": "0",
    "low_stock": "5",
    "smtp_user": "",
    "smtp_password": "",
    "price_3m": "6000000",
    "price_6m": "12000000",
    "price_12m": "15000000",
    "price_50y": "15000000",
    "cap_50y": "50",
    "must_change_password": "1",
    "moadian_fiscal_id": "",
    "moadian_economic_code": "",
    "moadian_private_key": "",
    "moadian_vat": "10",
    "moadian_enabled": "0",
    "moadian_sandbox": "1",
    "shop_name": "دفترچی",
    "shop_logo": "",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
}
POS_PROVIDERS = {"manual", "saman", "behpardakht", "parsian", "irankish", "sepehr", "asanpardakht"}
GATEWAYS = {"zarinpal", "idpay", "zibal"}
WEBAKERY_URL = "https://webakery.ir"
SANDBOX_MERCHANT = "00000000-0000-0000-0000-000000000000"
ZIBAL_LICENSE_MERCHANT = "6a331116da557b902563c32f"
APP_VERSION = "1.1.6"
TRIAL_DAYS = 7
UPDATE_MANIFEST_URLS = (
    "https://webakery.ir/daftarchi/version.json",
    "https://webakery.ir/license-server/version.json",
    "https://webakery.ir/version.json",
)
UPDATE_MANIFEST_URL = UPDATE_MANIFEST_URLS[0]
HOST_MAIL_URLS = (
    "https://webakery.ir/daftarchi/mail.php",
    "https://webakery.ir/license-server/mail.php",
    "https://webakery.ir/mail.php",
)
HOST_MAIL_URL = HOST_MAIL_URLS[0]
HOST_PAY_URLS = (
    "https://webakery.ir/license-server/pay.php",
    "https://webakery.ir/daftarchi/pay.php",
    "https://webakery.ir/pay.php",
)
HOST_ACCOUNT_URLS = (
    "https://webakery.ir/license-server/accounts.php",
    "https://webakery.ir/daftarchi/accounts.php",
)
HOST_MAIL_KEY = "daftarchi-webakery-mail"
HOST_TELEGRAM_URLS = (
    "https://webakery.ir/daftarchi/telegram.php",
    "https://webakery.ir/license-server/telegram.php",
    "https://webakery.ir/telegram.php",
)
SMS_PROVIDERS = {"internal", "kavenegar", "melipayamak"}
BOOL_KEYS = {"gateway_sandbox", "sms_on_close", "sms_on_sale", "sms_low_stock", "moadian_enabled", "moadian_sandbox"}
SYSTEM_ACCOUNTS = [
    ("1000", "صندوق", "asset"),
    ("1010", "بانک", "asset"),
    ("1020", "درگاه پرداخت", "asset"),
    ("1200", "موجودی کالا", "asset"),
    ("1300", "حساب‌های دریافتنی", "asset"),
    ("2000", "حساب‌های پرداختنی", "liability"),
    ("3000", "سرمایه", "equity"),
    ("4000", "فروش", "income"),
    ("4100", "تخفیفات فروش", "expense"),
    ("4200", "فروش لایسنس", "income"),
    ("5000", "بهای تمام‌شده", "expense"),
    ("5100", "کسر و اضافه صندوق", "expense"),
]

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.json.ensure_ascii = False
app.url_map.strict_slashes = False
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("daftarchi")


class AppError(Exception):
    def __init__(self, message: str, status: int = 400, **extra):
        super().__init__(message)
        self.status = status
        self.extra = extra


def now_dt() -> datetime:
    return datetime.now(TEHRAN)


def iso(dt: datetime | None = None) -> str:
    return (dt or now_dt()).isoformat(timespec="seconds")


def to_jalali(value: str | None) -> str:
    if not value:
        return ""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TEHRAN)
    local = dt.astimezone(TEHRAN).replace(tzinfo=None)
    return jdatetime.datetime.fromgregorian(datetime=local).strftime("%Y/%m/%d %H:%M")


def add_months(dt: datetime, months: int) -> datetime:
    index = dt.month - 1 + months
    year = dt.year + index // 12
    month = index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hash_pw(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 60_000).hex()
    return f"{salt}${digest}"


def check_pw(password: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 60_000).hex()
    return secrets.compare_digest(check, digest)


def norm_phone(value: str) -> str:
    text = str(value or "").translate(DIGITS)
    text = re.sub(r"[\s\-()]", "", text)
    if text.startswith("+98"):
        text = "0" + text[3:]
    elif text.startswith("0098"):
        text = "0" + text[4:]
    elif text.startswith("98") and len(text) == 12:
        text = "0" + text[2:]
    return text


def parse_money(value, label: str = "مبلغ", allow_empty: bool = False) -> int:
    if isinstance(value, bool) or value is None:
        if allow_empty and value is None:
            return 0
        raise AppError(f"{label} عدد نیست")
    if isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, float):
        number = Decimal(str(value))
    else:
        text = str(value).translate(DIGITS).strip()
        text = text.replace("تومان", "").replace("ریال", "").replace(",", "")
        text = text.replace("٬", "").replace(" ", "").replace("\u200c", "")
        if text == "":
            if allow_empty:
                return 0
            raise AppError(f"{label} لازم است")
        try:
            number = Decimal(text)
        except InvalidOperation:
            raise AppError(f"{label} عدد نیست")
    if number < 0:
        raise AppError(f"{label} نمی‌تواند منفی باشد")
    if number > Decimal(10**13):
        raise AppError(f"{label} خیلی بزرگ است")
    return int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_qty(value, label: str = "تعداد") -> int:
    qty = parse_money(value, label)
    if qty <= 0:
        raise AppError(f"{label} باید بیشتر از صفر باشد")
    if qty > 1_000_000:
        raise AppError(f"{label} خیلی بزرگ است")
    return qty


def clean_text(value, label: str, max_len: int, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise AppError(f"{label} لازم است")
    if len(text) > max_len:
        raise AppError(f"{label} طولانی است")
    return text


def clean_code(value, label: str) -> str | None:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = clean_text(value, label, 64)
    return text or None


def name_key(value: str) -> str:
    text = str(value or "").translate(DIGITS)
    for src, dst in (("ي", "ی"), ("ك", "ک"), ("ة", "ه"), ("ۀ", "ه"), ("\u200c", " "), ("\u200d", ""), ("\u0640", "")):
        text = text.replace(src, dst)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text


FILTER_FAMILIES = {"air", "water", "bath"}
BATH_WORDS = ("حمام", "دوش", "سردوش", "شیرآلات", "روشویی", "توالت", "وان")
ROLE_WORDS = ("سردوش", "شیرآلات", "روشویی", "توالت", "ممبران", "هوزینگ", "پمپ", "دستگاه", "دوش", "وان")
MATERIAL_WORDS = (
    ("الیافی", "fiber"),
    ("کربنی", "carbon"),
    ("کربن", "carbon"),
    ("نمدی", "felt"),
    ("سرامیکی", "ceramic"),
    ("مینرال", "mineral"),
    ("نخ", "yarn"),
    ("هپا", "hepa"),
)
LATIN_MATERIALS = (
    (re.compile(r"\bpp\b"), "pp"),
    (re.compile(r"\bcto\b"), "cto"),
    (re.compile(r"\bgac\b"), "gac"),
    (re.compile(r"\buf\b"), "uf"),
    (re.compile(r"\bhepa\b"), "hepa"),
)
MEASURE_WORDS = {"pp", "cto", "gac", "uf", "hepa", "inch", "micron", "um"}
INCH_RE = re.compile(r"(\d+(?:[./]\d+)?)\s*(?:اینچ|inch\b)")
MICRON_RE = re.compile(r"(\d+(?:[./]\d+)?)\s*(?:میکرون|micron\b|µm|μm|\bum\b)")
CODE_RE = re.compile(r"[a-z]{2,}(?:[-/]\d{1,4})?|\d{5,12}")
WOO_BATCH = 20


def word_in(text: str, word: str) -> bool:
    return re.search(rf"(?<![\w]){re.escape(word)}(?![\w])", text) is not None


def measure_token(raw: str) -> str:
    text = str(raw or "").strip()
    if "/" in text:
        left, right = text.split("/", 1)
        try:
            value = float(left) / float(right)
        except (ValueError, ZeroDivisionError):
            return text
    else:
        try:
            value = float(text)
        except ValueError:
            return text
    if value.is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def product_family(text: str) -> str:
    if any(word_in(text, word) for word in BATH_WORDS):
        return "bath"
    has_water = ("آب" in text) or word_in(text, "اب")
    has_air = word_in(text, "هوا") or ("هپا" in text)
    if has_air and has_water:
        if "تصفیه هوا" in text and "تصفیه آب" not in text and "تصفیه اب" not in text:
            return "air"
        if ("تصفیه آب" in text or "تصفیه اب" in text) and "تصفیه هوا" not in text:
            return "water"
        return ""
    if "تصفیه هوا" in text or "فیلتر هوا" in text or (has_air and "فیلتر" in text):
        return "air"
    if (
        "تصفیه آب" in text or "تصفیه اب" in text or "فیلتر آب" in text or "فیلتر اب" in text
        or ("فیلتر" in text and has_water)
    ):
        return "water"
    return ""


@functools.lru_cache(maxsize=8192)
def product_marks(name: str) -> dict:
    text = name_key(name)
    inches = {"0.5"} if re.search(r"نیم\s*اینچ", text) else set()
    inches.update(measure_token(match.group(1)) for match in INCH_RE.finditer(text))
    microns = {measure_token(match.group(1)) for match in MICRON_RE.finditer(text)}
    stripped = re.sub(r"نیم\s*اینچ", " ", text)
    stripped = INCH_RE.sub(" ", stripped)
    stripped = MICRON_RE.sub(" ", stripped)
    codes = set()
    for match in CODE_RE.finditer(stripped):
        token = match.group(0)
        if token in MEASURE_WORDS:
            continue
        codes.add(token)
    materials = {token for word, token in MATERIAL_WORDS if word in text}
    for pattern, token in LATIN_MATERIALS:
        if pattern.search(text):
            materials.add(token)
    roles = {word for word in ROLE_WORDS if word_in(text, word)}
    return {
        "family": product_family(text),
        "inches": frozenset(inches),
        "microns": frozenset(microns),
        "codes": frozenset(codes),
        "materials": frozenset(materials),
        "roles": frozenset(roles),
        "key": text,
    }


def marks_match(left: dict, right: dict) -> bool:
    if left["family"] not in FILTER_FAMILIES or left["family"] != right["family"]:
        return False
    if not (left["inches"] or left["microns"] or left["codes"]):
        return False
    return (
        left["inches"] == right["inches"]
        and left["microns"] == right["microns"]
        and left["codes"] == right["codes"]
        and left["materials"] == right["materials"]
        and left["roles"] == right["roles"]
    )


def goods_match(left_name: str, right_name: str) -> bool:
    left = product_marks(left_name)
    right = product_marks(right_name)
    if left["key"] and left["key"] == right["key"]:
        return True
    return marks_match(left, right)


def sku_blocks(left, right) -> bool:
    left_sku = str(left or "").strip()
    right_sku = str(right or "").strip()
    return bool(left_sku and right_sku and left_sku != right_sku)


def header_field(value) -> str | None:
    text = str(value or "").replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    return HEADER_MAP.get(text) or HEADER_MAP.get(text.lower())


def clean_tax_code(value) -> str | None:
    text = re.sub(r"\D", "", str(value or "").translate(DIGITS))
    if not text:
        return None
    if not re.fullmatch(r"\d{13}", text):
        raise AppError("شناسه کالا/خدمت مودیان باید ۱۳ رقم باشد")
    return text


def clean_image(value) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"/uploads/[a-f0-9]{32}\.(jpg|jpeg|png|webp|gif)", text):
        return text
    if text.startswith("http://") or text.startswith("https://"):
        if len(text) > 400:
            raise AppError("آدرس تصویر طولانی است")
        return text
    raise AppError("تصویر باید فایل بارگذاری‌شده یا آدرس اینترنتی باشد")


def clean_base(url: str) -> str:
    text = str(url or "").strip().rstrip("/")
    if not text.startswith("http://") and not text.startswith("https://"):
        raise AppError("آدرس سایت باید با http:// یا https:// شروع شود")
    return text


def body_json() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AppError("اطلاعات نامعتبر است")
    return data


def calc_discount(subtotal: int, dtype: str, value) -> int:
    if dtype == "percent":
        raw = str(value if value not in (None, "") else 0).translate(DIGITS).strip()
        try:
            pct = Decimal(raw or "0")
        except InvalidOperation:
            raise AppError("درصد تخفیف عدد نیست")
        if pct < 0 or pct > 100:
            raise AppError("درصد تخفیف بین ۰ و ۱۰۰ است")
        if pct == pct.to_integral_value():
            return (subtotal * int(pct) + 50) // 100
        return int((Decimal(subtotal) * pct / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if dtype == "amount":
        amount = parse_money(value, "تخفیف", allow_empty=True)
        if amount > subtotal:
            raise AppError("تخفیف از جمع کل بیشتر است")
        return amount
    raise AppError("نوع تخفیف نامعتبر است")


def public_user(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "email": row["email"] or "",
        "role": row["role"],
        "email_verified": int(row["email_verified"] or 0),
    }


def get_settings(conn) -> dict:
    data = dict(DEFAULT_SETTINGS)
    for row in conn.execute("SELECT key, value FROM settings"):
        data[row["key"]] = row["value"]
    return data


def setting_int(settings: dict, key: str) -> int:
    try:
        return int(str(settings.get(key) or "0").translate(DIGITS))
    except ValueError:
        return 0


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return row


def require_user():
    user = current_user()
    if not user:
        raise AppError("وارد نشده‌اید", 401)
    return user


def require_admin():
    user = require_user()
    if user["role"] != "admin":
        raise AppError("فقط مدیر به این بخش دسترسی دارد", 403)
    return user


def acc(conn, code: str):
    row = conn.execute("SELECT * FROM accounts WHERE code=?", (code,)).fetchone()
    if not row:
        raise AppError(f"حساب {code} پیدا نشد")
    return row


def account_balance(conn, account_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(debit),0) AS d, COALESCE(SUM(credit),0) AS c FROM journal_lines WHERE account_id=?",
        (account_id,),
    ).fetchone()
    return int(row["d"]) - int(row["c"])


def side_of(signed: int) -> tuple[str, int]:
    if signed > 0:
        return "بدهکار", signed
    if signed < 0:
        return "بستانکار", -signed
    return "تسویه", 0


def post_entry(conn, memo: str, lines: list[tuple[int, int, int]], source: str, source_id: int | None, user_id: int | None) -> int | None:
    clean = []
    for account_id, debit, credit in lines:
        debit, credit = int(debit), int(credit)
        if debit < 0 or credit < 0 or (debit and credit) or (debit == 0 and credit == 0):
            raise AppError("ردیف سند نامعتبر است")
        clean.append((int(account_id), debit, credit))
    if not clean:
        return None
    if len(clean) < 2:
        raise AppError("سند حداقل دو ردیف می‌خواهد")
    debit_total = sum(item[1] for item in clean)
    credit_total = sum(item[2] for item in clean)
    if debit_total != credit_total:
        raise AppError("سند تراز نیست")
    cur = conn.execute(
        "INSERT INTO journal_entries (memo, source, source_id, user_id, created_at) VALUES (?,?,?,?,?)",
        (memo, source, source_id, user_id, iso()),
    )
    entry_id = cur.lastrowid
    for account_id, debit, credit in clean:
        conn.execute(
            "INSERT INTO journal_lines (entry_id, account_id, debit, credit) VALUES (?,?,?,?)",
            (entry_id, account_id, debit, credit),
        )
    return entry_id


def log_stock(conn, product_id: int, kind: str, qty_delta: int, old_value: int, new_value: int, note: str, user_id: int | None):
    conn.execute(
        """INSERT INTO inventory_logs (product_id, kind, qty_delta, old_value, new_value, note, created_at, user_id)
           VALUES (?,?,?,?,?,?,?,?)""",
        (product_id, kind, qty_delta, old_value, new_value, note, iso(), user_id),
    )


def moving_avg(old_qty: int, old_cost: int, in_qty: int, in_cost: int) -> int:
    total_qty = old_qty + in_qty
    if total_qty <= 0:
        return in_cost
    value = (Decimal(old_qty) * Decimal(old_cost) + Decimal(in_qty) * Decimal(in_cost)) / Decimal(total_qty)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def open_session(conn):
    return conn.execute("SELECT * FROM register_sessions WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()


def require_open(conn):
    row = open_session(conn)
    if not row:
        raise AppError("صندوق بسته است. از صفحه صندوق آن را باز کنید.")
    return row


def create_person_account(conn, name: str) -> int:
    cur = conn.execute(
        "INSERT INTO accounts (code, name, type, system, active, created_at) VALUES (NULL,?,?,0,1,?)",
        (name, "person", iso()),
    )
    account_id = cur.lastrowid
    conn.execute("UPDATE accounts SET code=? WHERE id=?", (f"P{account_id:04d}", account_id))
    return account_id


def person_part(value: str) -> bool:
    return bool(re.fullmatch(r"[\u0600-\u06FFa-zA-Z\u200c]{2,40}", value or ""))


def walk_in_name(payload: dict) -> str:
    first = clean_text(payload.get("customer_first"), "نام", 40)
    last = clean_text(payload.get("customer_last"), "نام خانوادگی", 40)
    if first or last:
        if person_part(first) and person_part(last):
            return f"{first} {last}"
        raise AppError("نام و نام خانوادگی خریدار را بنویسید")
    parts = [part for part in re.split(r"\s+", clean_text(payload.get("customer_name"), "نام خریدار", 80)) if part]
    if len(parts) < 2 or any(not person_part(part) for part in parts):
        raise AppError("نام و نام خانوادگی خریدار را بنویسید")
    return " ".join(parts)


def walk_in_customer(conn, payload: dict, credit: bool) -> dict:
    name = walk_in_name(payload)
    phone = norm_phone(payload.get("customer_phone") or "")
    if not re.fullmatch(r"09\d{9}", phone):
        raise AppError("شماره موبایل خریدار را وارد کنید")
    return ensure_customer(conn, name, phone, credit)


def ensure_customer(conn, name: str, phone: str, credit: bool) -> dict:
    name = clean_text(name, "نام خریدار", 80)
    phone_raw = str(phone or "").strip()
    if not phone_raw and not name:
        if credit:
            raise AppError("برای فروش نسیه شماره تماس خریدار لازم است")
        return {"id": None, "name": "", "phone": "", "account_id": None}
    phone_n = norm_phone(phone_raw) if phone_raw else ""
    if credit and not phone_n:
        raise AppError("برای فروش نسیه شماره تماس خریدار لازم است")
    if phone_n and not re.fullmatch(r"0\d{10}", phone_n):
        raise AppError("شماره تماس معتبر نیست")
    display = name or "مشتری"
    if not phone_n:
        return {"id": None, "name": display, "phone": "", "account_id": None}
    row = conn.execute("SELECT * FROM customers WHERE phone=?", (phone_n,)).fetchone()
    if row:
        if name and name != row["name"]:
            conn.execute("UPDATE customers SET name=? WHERE id=?", (name, row["id"]))
            display = name
        else:
            display = row["name"]
        account_id = row["account_id"]
        if credit and not account_id:
            account_id = create_person_account(conn, display)
            conn.execute("UPDATE customers SET account_id=? WHERE id=?", (account_id, row["id"]))
        return {"id": row["id"], "name": display, "phone": phone_n, "account_id": account_id}
    account_id = create_person_account(conn, display) if credit else None
    cur = conn.execute(
        "INSERT INTO customers (name, phone, account_id, created_at) VALUES (?,?,?,?)",
        (display, phone_n, account_id, iso()),
    )
    return {"id": cur.lastrowid, "name": display, "phone": phone_n, "account_id": account_id}


def match_product(conn, barcode: str | None, sku: str | None):
    by_barcode = conn.execute("SELECT * FROM products WHERE barcode=?", (barcode,)).fetchone() if barcode else None
    by_sku = conn.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone() if sku else None
    if by_barcode and by_sku and by_barcode["id"] != by_sku["id"]:
        raise AppError("بارکد و کد به دو کالای متفاوت مربوط است")
    return by_barcode or by_sku


def product_kind(row) -> str:
    if "product_type" not in row.keys():
        return "simple"
    return row["product_type"] or "simple"


def variation_dict(row) -> dict:
    try:
        attributes = json.loads(row["attributes"] or "[]")
    except json.JSONDecodeError:
        attributes = []
    if not isinstance(attributes, list):
        attributes = []
    stock = row["stock"]
    tracked = stock is not None
    return {
        "id": row["id"],
        "woo_id": row["woo_id"],
        "sku": row["sku"] or "",
        "barcode": row["barcode"] or "",
        "price": row["price"],
        "stock": stock,
        "tracked": tracked,
        "in_stock": (int(stock) > 0) if tracked else bool(row["in_stock"]),
        "label": row["label"],
        "attributes": attributes,
        "image": row["image"] or "",
    }


def load_variations(conn, product_ids: list[int]) -> dict[int, list[dict]]:
    if not product_ids:
        return {}
    marks = ",".join("?" for _ in product_ids)
    rows = conn.execute(
        f"""SELECT * FROM product_variations
            WHERE active=1 AND product_id IN ({marks}) ORDER BY id""",
        product_ids,
    ).fetchall()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["product_id"], []).append(variation_dict(row))
    return grouped


def product_dict(row, threshold: int, variations: list | None = None) -> dict:
    variations = variations or []
    kind = product_kind(row)
    if kind == "variable" and variations:
        low = any(item["tracked"] and int(item["stock"]) <= threshold for item in variations) or not any(item["in_stock"] for item in variations)
    else:
        low = row["stock"] <= threshold
    return {
        "id": row["id"],
        "name": row["name"],
        "family": product_marks(row["name"])["family"],
        "sku": row["sku"] or "",
        "barcode": row["barcode"] or "",
        "price": row["price"],
        "cost": row["cost"],
        "stock": row["stock"],
        "image": row["image"] or "",
        "woo_id": row["woo_id"],
        "active": row["active"],
        "tax_code": row["tax_code"] or "",
        "type": kind,
        "variations": variations,
        "low": low,
    }


def present_products(conn, rows, threshold: int) -> list[dict]:
    grouped = load_variations(conn, [row["id"] for row in rows])
    return [product_dict(row, threshold, grouped.get(row["id"], [])) for row in rows]


def present_product(conn, row, threshold: int) -> dict:
    return present_products(conn, [row], threshold)[0]


def load_cart(conn, items) -> tuple[list[dict], int]:
    if not isinstance(items, list) or not items:
        raise AppError("سبد خالی است")
    merged: dict[tuple[int, int], int] = {}
    for raw in items:
        if not isinstance(raw, dict):
            raise AppError("قلم کالا نامعتبر است")
        try:
            pid = int(raw.get("product_id") or 0)
            variation_id = int(raw.get("variation_id") or 0)
        except (TypeError, ValueError):
            raise AppError("کالا نامعتبر است")
        key = (pid, variation_id)
        merged[key] = merged.get(key, 0) + parse_qty(raw.get("qty"))
    result = []
    subtotal = 0
    for (pid, variation_id), qty in merged.items():
        row = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
        if not row:
            raise AppError("کالا پیدا نشد")
        if product_kind(row) == "variable":
            if not variation_id:
                raise AppError(f"برای «{row['name']}» نوع متغیر را انتخاب کنید")
            var = conn.execute(
                "SELECT * FROM product_variations WHERE id=? AND product_id=? AND active=1",
                (variation_id, pid),
            ).fetchone()
            if not var:
                raise AppError("این متغیر پیدا نشد")
            if var["stock"] is None:
                if not var["in_stock"]:
                    raise AppError(f"«{row['name']} — {var['label']}» ناموجود است")
            elif qty > int(var["stock"]):
                raise AppError(f"موجودی «{row['name']} — {var['label']}» کافی نیست")
            unit_price = int(var["price"])
            name = f"{row['name']} — {var['label']}"
        else:
            if variation_id:
                raise AppError("این کالا متغیر نیست")
            if qty > row["stock"]:
                raise AppError(f"موجودی «{row['name']}» کافی نیست")
            unit_price = int(row["price"])
            name = row["name"]
            var = None
        line_total = unit_price * qty
        subtotal += line_total
        result.append({
            "product_id": pid,
            "variation_id": variation_id or None,
            "name": name,
            "qty": qty,
            "unit_price": unit_price,
            "unit_cost": int(row["cost"]),
            "line_total": line_total,
        })
    if subtotal > 10**13:
        raise AppError("مبلغ فاکتور خیلی بزرگ است")
    return result, subtotal


def insert_sale(conn, user_id: int, customer: dict, items: list[dict], subtotal: int, discount: int, method: str, pos_ref: str, session_id: int | None) -> int:
    payable = subtotal - discount
    cur = conn.execute(
        """INSERT INTO sales (status, customer_id, customer_name, customer_phone, subtotal, discount, payable,
           payment_method, pos_ref, gateway, gateway_ref, pay_url, session_id, user_id, created_at)
           VALUES ('pending',?,?,?,?,?,?,?,?, '', NULL, NULL, ?, ?, ?)""",
        (
            customer["id"], customer["name"], customer["phone"], subtotal, discount, payable,
            method, pos_ref or None, session_id, user_id, iso(),
        ),
    )
    sale_id = cur.lastrowid
    for item in items:
        conn.execute(
            """INSERT INTO sale_items (sale_id, product_id, variation_id, name, qty, unit_price, unit_cost, line_total)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                sale_id, item["product_id"], item.get("variation_id"), item["name"], item["qty"],
                item["unit_price"], item["unit_cost"], item["line_total"],
            ),
        )
    return sale_id


def variable_parent_stock(conn, product_id: int) -> int:
    total = conn.execute(
        """SELECT COALESCE(SUM(stock), 0) AS total FROM product_variations
           WHERE product_id=? AND active=1 AND stock IS NOT NULL""",
        (product_id,),
    ).fetchone()["total"]
    price = conn.execute(
        "SELECT MIN(price) AS price FROM product_variations WHERE product_id=? AND active=1",
        (product_id,),
    ).fetchone()["price"]
    if price is None:
        conn.execute(
            "UPDATE products SET stock=?, product_type='variable', updated_at=? WHERE id=?",
            (int(total), iso(), product_id),
        )
    else:
        conn.execute(
            "UPDATE products SET stock=?, price=?, product_type='variable', updated_at=? WHERE id=?",
            (int(total), int(price), iso(), product_id),
        )
    return int(total)


def line_variation(conn, item):
    variation_id = int(item["variation_id"] or 0) if item["variation_id"] is not None else 0
    if not variation_id:
        return None
    var = conn.execute(
        "SELECT * FROM product_variations WHERE id=? AND product_id=? AND active=1",
        (variation_id, item["product_id"]),
    ).fetchone()
    if not var:
        raise AppError(f"متغیر «{item['name']}» دیگر در سیستم نیست")
    return var


def ensure_line_stock(conn, item):
    row = conn.execute("SELECT * FROM products WHERE id=?", (item["product_id"],)).fetchone()
    if not row:
        raise AppError(f"کالای «{item['name']}» دیگر در سیستم نیست")
    var = line_variation(conn, item)
    if var:
        if var["stock"] is None:
            if not var["in_stock"]:
                raise AppError(f"«{item['name']}» ناموجود است")
            return
        if int(var["stock"]) < int(item["qty"]):
            raise AppError(f"موجودی «{item['name']}» کافی نیست")
        return
    if product_kind(row) == "variable":
        raise AppError(f"برای «{row['name']}» نوع متغیر را انتخاب کنید")
    if row["stock"] < item["qty"]:
        raise AppError(f"موجودی «{item['name']}» کافی نیست")


def take_line_stock(conn, item, user_id: int, sale_id: int, threshold: int) -> list[str]:
    row = conn.execute("SELECT * FROM products WHERE id=?", (item["product_id"],)).fetchone()
    var = line_variation(conn, item)
    if var:
        if var["stock"] is None:
            return []
        new_stock = int(var["stock"]) - int(item["qty"])
        conn.execute(
            "UPDATE product_variations SET stock=?, in_stock=? WHERE id=?",
            (new_stock, 1 if new_stock else 0, var["id"]),
        )
        parent_before = int(row["stock"])
        parent_after = variable_parent_stock(conn, row["id"])
        alerts = [item["name"]] if parent_before > threshold >= parent_after or (int(var["stock"]) > threshold >= new_stock) else []
        log_stock(conn, row["id"], "sale", -int(item["qty"]), int(var["stock"]), new_stock, f"فاکتور {sale_id} · {var['label']}", user_id)
        return alerts
    new_stock = int(row["stock"]) - int(item["qty"])
    alerts = [row["name"]] if int(row["stock"]) > threshold >= new_stock else []
    conn.execute("UPDATE products SET stock=?, updated_at=? WHERE id=?", (new_stock, iso(), row["id"]))
    log_stock(conn, row["id"], "sale", -int(item["qty"]), int(row["stock"]), new_stock, f"فاکتور {sale_id}", user_id)
    return alerts


def finalize_sale(conn, sale_id: int, user_id: int) -> list[str]:
    sale = conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
    if not sale:
        raise AppError("فاکتور پیدا نشد", 404)
    if sale["status"] == "paid":
        return []
    if sale["status"] != "pending":
        raise AppError("این فاکتور قابل تأیید نیست")
    items = conn.execute("SELECT * FROM sale_items WHERE sale_id=?", (sale_id,)).fetchall()
    settings = get_settings(conn)
    threshold = setting_int(settings, "low_stock")
    alerts = []
    for item in items:
        ensure_line_stock(conn, item)
    for item in items:
        alerts.extend(take_line_stock(conn, item, user_id, sale_id, threshold))
    if sale["payment_method"] == "credit":
        if not sale["customer_id"]:
            raise AppError("خریدار نسیه مشخص نیست")
        customer = conn.execute("SELECT * FROM customers WHERE id=?", (sale["customer_id"],)).fetchone()
        debit_id = customer["account_id"] if customer else None
        if not debit_id:
            raise AppError("حساب بدهکار خریدار پیدا نشد")
    else:
        code = {"cash": "1000", "card": "1010", "gateway": "1020"}.get(sale["payment_method"])
        if not code:
            raise AppError("روش پرداخت نامعتبر است")
        debit_id = acc(conn, code)["id"]
    if sale["payment_method"] == "gateway":
        sess = open_session(conn)
        conn.execute(
            "UPDATE sales SET created_at=?, session_id=COALESCE(?, session_id) WHERE id=?",
            (iso(), sess["id"] if sess else None, sale_id),
        )
    elif not sale["session_id"]:
        raise AppError("صندوق بسته است. از صفحه صندوق آن را باز کنید.")
    cogs = sum(int(item["unit_cost"]) * int(item["qty"]) for item in items)
    lines = []
    if sale["payable"]:
        lines.append((debit_id, int(sale["payable"]), 0))
    if sale["discount"]:
        lines.append((acc(conn, "4100")["id"], int(sale["discount"]), 0))
    if sale["payable"] or sale["discount"]:
        lines.append((acc(conn, "4000")["id"], 0, int(sale["subtotal"])))
    if cogs:
        lines.append((acc(conn, "5000")["id"], cogs, 0))
        lines.append((acc(conn, "1200")["id"], 0, cogs))
    post_entry(conn, f"فاکتور {sale_id}", lines, "sale", sale_id, user_id)
    conn.execute("UPDATE sales SET status='paid' WHERE id=?", (sale_id,))
    return alerts


def sale_payload(conn, sale_id: int) -> dict:
    sale = conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
    items = conn.execute("SELECT * FROM sale_items WHERE sale_id=? ORDER BY id", (sale_id,)).fetchall()
    data = dict(sale)
    data["at_jalali"] = to_jalali(data["created_at"])
    return {"sale": data, "items": [dict(item) for item in items]}


def session_figures(conn, sess) -> dict:
    sid = sess["id"]

    def sales_of(method: str) -> tuple[int, int]:
        row = conn.execute(
            """SELECT COALESCE(SUM(payable),0) AS s, COUNT(*) AS c FROM sales
               WHERE session_id=? AND status='paid' AND payment_method=?""",
            (sid, method),
        ).fetchone()
        return int(row["s"]), int(row["c"])

    cash_sales, cash_count = sales_of("cash")
    card_sales, card_count = sales_of("card")
    gateway_sales, gateway_count = sales_of("gateway")
    credit_sales, credit_count = sales_of("credit")

    def license_sum(method: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(SUM(payable),0) AS s FROM licenses WHERE session_id=? AND payment_method=? AND status='paid'",
            (sid, method),
        ).fetchone()
        return int(row["s"])

    def receipt_sum(method: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS s FROM receipts WHERE session_id=? AND payment_method=?",
            (sid, method),
        ).fetchone()
        return int(row["s"])

    purchases = conn.execute(
        """SELECT COALESCE(SUM(p.total),0) AS s FROM purchases p
           JOIN accounts a ON a.id = p.pay_account_id
           WHERE p.session_id=? AND a.code='1000'""",
        (sid,),
    ).fetchone()
    cash_purchases = int(purchases["s"])
    license_cash = license_sum("cash")
    cash_receipts = receipt_sum("cash")
    opening = int(sess["opening_cash"])
    expected = opening + cash_sales + cash_receipts - cash_purchases
    counted = sess["counted_cash"]
    return {
        "opening": opening,
        "cash_sales": cash_sales,
        "card_sales": card_sales,
        "gateway_sales": gateway_sales,
        "credit_sales": credit_sales,
        "license_cash": license_cash,
        "license_card": license_sum("card"),
        "cash_receipts": cash_receipts,
        "card_receipts": receipt_sum("card"),
        "cash_purchases": cash_purchases,
        "expected_cash": expected,
        "counted_cash": counted,
        "difference": None if counted is None else int(counted) - expected,
        "invoice_count": cash_count + card_count + gateway_count + credit_count,
    }


def public_session(conn, sess) -> dict | None:
    if not sess:
        return None
    data = {
        "id": sess["id"],
        "status": sess["status"],
        "opening_cash": sess["opening_cash"],
        "counted_cash": sess["counted_cash"],
        "opened_at": sess["opened_at"],
        "closed_at": sess["closed_at"],
        "opened_jalali": to_jalali(sess["opened_at"]),
        "closed_jalali": to_jalali(sess["closed_at"]) if sess["closed_at"] else "",
        "figures": session_figures(conn, sess),
    }
    return data


def adjust_cash_to(conn, target: int, memo: str, source: str, source_id: int, user_id: int):
    book = account_balance(conn, acc(conn, "1000")["id"])
    delta = target - book
    if delta > 0:
        post_entry(conn, memo, [(acc(conn, "1000")["id"], delta, 0), (acc(conn, "3000")["id"], 0, delta)], source, source_id, user_id)
    elif delta < 0:
        amount = -delta
        post_entry(conn, memo, [(acc(conn, "5100")["id"], amount, 0), (acc(conn, "1000")["id"], 0, amount)], source, source_id, user_id)


def manager_phone(settings: dict) -> str:
    phone = norm_phone(settings.get("manager_phone") or "")
    return phone if re.fullmatch(r"09\d{9}", phone) else ""


def parse_body(raw: bytes):
    if not raw:
        return None
    try:
        return json.loads(raw.decode())
    except Exception:
        return {"raw": raw.decode(errors="replace")[:500]}


def http_request(method: str, url: str, payload=None, headers=None, form=None, timeout: int = 12):
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        content_type = "application/x-www-form-urlencoded"
    elif payload is not None:
        data = json.dumps(payload).encode()
        content_type = "application/json"
    else:
        data = None
        content_type = None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Daftarchi/1.0")
    if content_type:
        req.add_header("Content-Type", content_type)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, parse_body(res.read())
    except urllib.error.HTTPError as exc:
        return exc.code, parse_body(exc.read())
    except urllib.error.URLError as exc:
        raise AppError(f"اتصال برقرار نشد: {exc.reason}", 502)
    except TimeoutError as exc:
        raise AppError("اتصال برقرار نشد: زمان درخواست تمام شد", 502) from exc


def woo_rfc3986(value: str) -> str:
    return urllib.parse.quote(str(value), safe="~")


def woo_oauth_signature(method: str, base_url: str, params: dict, secret: str) -> str:
    pairs = []
    for key in sorted(params):
        if key == "oauth_signature":
            continue
        encoded = woo_rfc3986(urllib.parse.unquote(str(key))) + "=" + woo_rfc3986(urllib.parse.unquote(str(params[key])))
        pairs.append(woo_rfc3986(encoded))
    query = "%26".join(pairs)
    string_to_sign = f"{method.upper()}&{woo_rfc3986(base_url)}&{query}"
    digest = hmac.new((secret + "&").encode(), string_to_sign.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def woo_oauth_url(method: str, url: str, key: str, secret: str, scheme: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    signed = urllib.parse.urlunsplit((scheme, parsed.netloc, parsed.path, "", ""))
    requested = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    params["oauth_consumer_key"] = key
    params["oauth_timestamp"] = str(int(datetime.now(timezone.utc).timestamp()))
    params["oauth_nonce"] = secrets.token_hex(16)
    params["oauth_signature_method"] = "HMAC-SHA256"
    params["oauth_signature"] = woo_oauth_signature(method, signed, params, secret)
    return requested + "?" + urllib.parse.urlencode(params)


def woo_target(settings: dict, method: str, path: str, extra: dict | None, auth: str, style: str, scheme: str) -> tuple[str, dict]:
    base = clean_base(settings.get("wp_url") or "")
    key = str(settings.get("woo_key") or "").strip()
    secret = str(settings.get("woo_secret") or "").strip()
    query = {str(name): str(value) for name, value in (extra or {}).items()}
    headers = {}
    if auth == "basic":
        token = base64.b64encode(f"{key}:{secret}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    elif auth == "query":
        query["consumer_key"] = key
        query["consumer_secret"] = secret
    route = "/wc/v3/" + path.strip("/")
    if style == "index":
        url = f"{base}/index.php?rest_route={urllib.parse.quote(route, safe='')}"
        if query:
            url += "&" + urllib.parse.urlencode(query)
    else:
        url = f"{base}/wp-json{route}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
    if auth == "oauth":
        url = woo_oauth_url(method, url, key, secret, scheme)
    return url, headers


def woo_body_text(body) -> tuple[str, str]:
    if not isinstance(body, dict):
        return "", ""
    message = str(body.get("message") or "").strip()
    if not message:
        message = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(body.get("raw") or ""))).strip()
    return str(body.get("code") or ""), message


def woo_failure(status: int, body) -> str:
    _code, message = woo_body_text(body)
    lowered = message.lower()
    if "signature" in lowered or "امضا" in message:
        return "ووکامرس امضا را نپذیرفت. آدرس فروشگاه باید همان آدرس وردپرس باشد، مثل https://aquasafe.ir"
    if any(word in message for word in ("اجازه", "مشاهده", "لیست منابع", "cannot list", "cannot view")) or "cannot_view" in _code:
        return "کلید را در ووکامرس با کاربر مدیر بسازید و دسترسی را «خواندن و نوشتن» بگذارید. کادر Consumer key باید پر باشد و با ck_ شروع شود."
    if message:
        return f"ووکامرس: {message[:220]}"
    if status == 401:
        return "ووکامرس کلید را نپذیرفت. Consumer key و Consumer secret را از ووکامرس، تنظیمات، پیشرفته، REST API دوباره بسازید. دسترسی خواندن و نوشتن باشد."
    if status == 404:
        return "آدرس ووکامرس پیدا نشد. آدرس همان صفحه فروشگاه باشد، مثل https://aquasafe.ir"
    return "اتصال به فروشگاه برقرار نشد. آدرس را با https:// بنویسید."


def woo_error_rank(status: int, body) -> int:
    code, message = woo_body_text(body)
    lowered = message.lower()
    if "signature" in lowered or "امضا" in message:
        return 50
    if code == "woocommerce_rest_authentication_error" or "نامعتبر" in message or "invalid" in lowered:
        return 40
    if status in {401, 403}:
        return 10
    return 0


def woo_request(settings: dict, method: str, path: str, extra: dict | None = None, payload=None):
    require_woo(settings)
    last_error = None
    best = (0, None, -1)
    attempts = (
        ("query", "pretty", "https"),
        ("oauth", "pretty", "https"),
        ("oauth", "pretty", "http"),
        ("basic", "pretty", "https"),
        ("query", "index", "https"),
        ("oauth", "index", "https"),
    )
    for auth, style, scheme in attempts:
        url, headers = woo_target(settings, method, path, extra, auth, style, scheme)
        try:
            status, body = http_request(method, url, payload=payload, headers=headers, timeout=8 if auth == "basic" else 20)
        except AppError as exc:
            last_error = exc
            continue
        if status < 400:
            return status, body
        rank = woo_error_rank(status, body)
        if rank >= best[2]:
            best = (status, body, rank)
        if status not in {401, 403, 404}:
            break
        _code, message = woo_body_text(body)
        # کلید در پایگاه ووکامرس نیست. روش‌های بعدی همان جواب را دیرتر تکرار می‌کنند.
        if auth == "oauth" and rank == 40 and "امضا" not in message and "signature" not in message.lower():
            break
    if best[2] < 0 and last_error:
        raise last_error
    raise AppError(woo_failure(best[0], best[1]), 502)


def wordpress_status(settings: dict) -> str:
    base = clean_base(settings.get("wp_url") or "")
    last_error = None
    for url in (base + "/wp-json/", base + "/wp-json", base + "/?rest_route=/"):
        try:
            status, body = http_request("GET", url, timeout=20)
        except AppError as exc:
            last_error = exc
            continue
        if status < 400 and isinstance(body, dict) and body.get("name"):
            return f"اتصال برقرار است: {body.get('name')}"
    try:
        status, body = http_request("GET", base + "/wp-login.php", timeout=20)
    except AppError as exc:
        if last_error:
            raise last_error
        raise
    raw = body.get("raw", "") if isinstance(body, dict) else ""
    lowered = raw.lower()
    if status < 400 and ("وردپرس" in raw or "wordpress" in lowered or "wp-login" in lowered):
        return "صفحه ورود وردپرس باز شد، ولی فهرست فروشگاه پاسخ نداد."
    if last_error:
        raise last_error
    raise AppError("وردپرس پاسخ نداد. آدرس سایت را با https:// بنویسید.", 502)


def require_woo(settings: dict):
    if not settings.get("wp_url") or not settings.get("woo_key") or not settings.get("woo_secret"):
        raise AppError("آدرس وردپرس و کلیدهای ووکامرس را در تنظیمات وارد کنید")
    clean_base(settings["wp_url"])


def deliver_sms(conn, settings: dict, recipient: str, text: str) -> tuple[str, str]:
    recipient = norm_phone(recipient)
    status, detail = "internal", "در صندوق پیامک سیستم ثبت شد"
    provider = settings.get("sms_provider") or "internal"
    try:
        if provider == "kavenegar" and settings.get("sms_api_key"):
            sender = settings.get("sms_sender") or ""
            if not sender:
                raise AppError("شماره خط کاوه‌نگار خالی است")
            url = f"https://api.kavenegar.com/v1/{settings['sms_api_key']}/sms/send.json"
            code, body = http_request("POST", url, form={"receptor": recipient, "sender": sender, "message": text})
            ret = body.get("return", {}) if isinstance(body, dict) else {}
            if code >= 400 or str(ret.get("status", 200)) not in {"200", "OK"}:
                raise AppError(str(body)[:220] if body else str(code))
            status, detail = "sent", "کاوه‌نگار"
        elif provider == "melipayamak" and settings.get("sms_username"):
            sender = settings.get("sms_sender") or ""
            if not sender:
                raise AppError("شماره خط ملی‌پیامک خالی است")
            code, body = http_request(
                "POST",
                "https://rest.payamak-panel.com/api/SendSMS/SendSMS",
                payload={
                    "username": settings["sms_username"],
                    "password": settings.get("sms_password") or "",
                    "to": recipient,
                    "from": sender,
                    "text": text,
                    "isFlash": False,
                },
            )
            ret = body.get("RetStatus") if isinstance(body, dict) else None
            if code >= 400 or ret not in (1, "1"):
                raise AppError(str(body)[:220] if body else str(code))
            status, detail = "sent", "ملی‌پیامک"
    except Exception as exc:
        status, detail = "failed", str(exc)[:300]
    conn.execute(
        "INSERT INTO notifications (channel, recipient, body, status, detail, created_at) VALUES ('sms',?,?,?,?,?)",
        (recipient, text, status, detail, iso()),
    )
    return status, detail


def deliver_email(conn, settings: dict, recipient: str, subject: str, text: str) -> tuple[str, str]:
    status, detail = "internal", "جیمیل تنظیم نشده"
    sender = str(settings.get("smtp_user") or "").strip()
    secret = str(settings.get("smtp_password") or "").replace(" ", "")
    if sender and secret:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient
            msg.set_content(text)
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                token = base64.b64encode(f"\0{sender}\0{secret}".encode()).decode()
                code, resp = smtp.docmd("AUTH", f"PLAIN {token}")
                if code != 235:
                    text = resp.decode(errors="replace") if isinstance(resp, bytes) else str(resp)
                    raise RuntimeError(f"{code} {text}")
                smtp.send_message(msg)
            status, detail = "sent", "جیمیل"
        except Exception as exc:
            status, detail = "failed", str(exc)[:300]
    conn.execute(
        "INSERT INTO notifications (channel, recipient, body, status, detail, created_at) VALUES ('email',?,?,?,?,?)",
        (recipient, f"{subject}\n{text}", status, detail, iso()),
    )
    return status, detail


def gmail_address(value) -> str:
    email = clean_text(value, "جیمیل", 120).lower()
    if not re.fullmatch(r"[a-z0-9._%+\-]+@(gmail|googlemail)\.com", email):
        raise AppError("آدرس باید جیمیل باشد، مثل name@gmail.com")
    return email


def smtp_ready(settings: dict) -> bool:
    return bool(str(settings.get("smtp_user") or "").strip() and str(settings.get("smtp_password") or "").strip())


def explain_gmail(detail: str) -> str:
    return explain_host_mail(detail)


def explain_host_mail(detail: str) -> str:
    text = str(detail or "")
    low = text.lower()
    if "404" in low:
        return (
            "پوشه daftarchi روی سایت باز نمی‌شود. فایل mail.php را کپی کنید داخل پوشه license-server "
            "که از قبل در public_html کنار wp-admin است. سپس https://webakery.ir/license-server/mail.php "
            "باید ok و daftarchi-mail نشان بدهد."
        )
    if "اتصال" in text or "timed out" in low or "timeout" in low or "unreachable" in low:
        return "اتصال به هاست وب‌بیکری برقرار نشد. تأیید حساب و بازیابی رمز بدون هاست ممکن نیست."
    if "mail" in low or "key" in low or "fields" in low or "تنظیم نشده" in text:
        return (
            "هاست کد را به جیمیل نفرستاد. فایل mail.php را در public_html/daftarchi کنار version.json بگذارید. "
            "نامه از هاست به جیمیل خریدار می‌رود، نه از رمز ورود جیمیل روی همین رایانه."
        )
    return f"ارسال کد از هاست به جیمیل ناموفق بود: {text[:180]}"


def host_mail_hit(method: str, payload=None, timeout: int = 4):
    last_status, last_body = 404, {"error": "HTTP 404"}
    for url in HOST_MAIL_URLS:
        try:
            status, body = http_request(method, url, payload=payload, timeout=timeout)
        except AppError as exc:
            last_status, last_body = 502, {"error": str(exc)}
            continue
        last_status, last_body = status, body
        if status < 400 and isinstance(body, dict) and body.get("service") == "daftarchi-mail":
            return url, status, body
    return HOST_MAIL_URLS[-1], last_status, last_body


def host_mail_ready() -> bool:
    _url, status, body = host_mail_hit("GET", timeout=4)
    return status < 400 and isinstance(body, dict) and bool(body.get("ok")) and body.get("service") == "daftarchi-mail"


def send_host_mail(recipient: str, subject: str, text: str) -> None:
    payload = {"key": HOST_MAIL_KEY, "to": recipient, "subject": subject, "text": text}
    url, status, body = host_mail_hit("POST", payload=payload, timeout=12)
    if status >= 400 or not isinstance(body, dict) or not body.get("ok"):
        detail = ""
        if isinstance(body, dict):
            detail = str(body.get("error") or "")
        raise AppError(explain_host_mail(detail or f"HTTP {status} {url}"), 502)


def store_code(conn, user_id: int, channel: str) -> str:
    since = iso(now_dt() - timedelta(minutes=10))
    recent = conn.execute(
        "SELECT COUNT(*) AS c FROM password_resets WHERE user_id=? AND created_at>?",
        (user_id, since),
    ).fetchone()["c"]
    if recent >= 5:
        raise AppError("چند بار درخواست داده‌اید. کمی بعد دوباره تلاش کنید")
    code = f"{secrets.randbelow(900000) + 100000}"
    conn.execute(
        "INSERT INTO password_resets (user_id, code_hash, channel, expires_at, used, created_at) VALUES (?,?,?,?,0,?)",
        (user_id, hashlib.sha256(code.encode()).hexdigest(), channel, iso(now_dt() + timedelta(minutes=10)), iso()),
    )
    return code


def send_gmail_code(conn, _settings: dict, recipient: str, user_id: int, purpose: str) -> None:
    channel = "verify" if purpose == "verify" else "email"
    code = store_code(conn, user_id, channel)
    if purpose == "verify":
        subject = "کد تأیید حساب دفترچی"
        text = (
            f"کد تأیید حساب دفترچی: {code}\n"
            "این کد تا ۱۰ دقیقه معتبر است.\n"
            "اگر شما این حساب را نساخته‌اید، این نامه را نادیده بگیرید."
        )
    else:
        subject = "بازیابی رمز دفترچی"
        text = f"کد بازیابی رمز دفترچی: {code}\nاین کد تا ۱۰ دقیقه معتبر است."
    send_host_mail(recipient, subject, text)
    conn.execute(
        "INSERT INTO notifications (channel, recipient, body, status, detail, created_at) VALUES ('email',?,?,?,?,?)",
        (recipient, f"{subject}\n{text}", "sent", "هاست وب‌بیکری", iso()),
    )


def version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for piece in re.split(r"[^\d]+", str(value or "").strip()):
        if not piece:
            continue
        parts.append(int(piece))
        if len(parts) == 4:
            break
    return tuple(parts) or (0,)


def notify_buyer(sale: dict) -> dict:
    phone = norm_phone(sale.get("customer_phone") or "")
    if not re.fullmatch(r"09\d{9}", phone):
        return {"status": "skipped", "detail": ""}
    name = sale.get("customer_name") or "مشتری"
    text = f"{name} عزیز\nخرید حضوری شما ثبت شد.\nمبلغ: {int(sale['payable']):,} تومان\nفاکتور: {sale['id']}"
    try:
        with connect() as conn:
            status, detail = deliver_sms(conn, get_settings(conn), phone, text)
    except Exception:
        log.exception("buyer sms")
        return {"status": "failed", "detail": "پیامک خریدار ثبت نشد"}
    if status == "sent":
        note = "پیامک ثبت خرید به شماره خریدار رفت"
    elif status == "internal":
        note = "پیامک در صندوق پیامک ثبت شد. برای رسیدن به گوشی خریدار، کاوه‌نگار یا ملی‌پیامک را در تنظیمات بگذارید."
    else:
        note = f"پیامک نرفت: {detail}"
    return {"status": status, "detail": note}


def notify_manager(settings_snapshot: dict, text: str):
    phone = manager_phone(settings_snapshot)
    if not phone:
        return
    with connect() as conn:
        deliver_sms(conn, get_settings(conn), phone, text)


def find_user(conn, ident: str):
    ident = str(ident or "").strip()
    if "@" in ident:
        return conn.execute("SELECT * FROM users WHERE lower(email)=?", (ident.lower(),)).fetchone()
    return conn.execute("SELECT * FROM users WHERE phone=?", (norm_phone(ident),)).fetchone()


def clear_initial_secret(conn, user):
    if user["role"] == "admin":
        conn.execute("UPDATE settings SET value='0' WHERE key='must_change_password'")


def range_bounds(kind: str) -> tuple[datetime, datetime]:
    now = now_dt()
    if kind == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)
    if kind == "week":
        delta = (now.weekday() - 5) % 7
        start = (now - timedelta(days=delta)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=7)
    if kind == "month":
        local = now.astimezone(TEHRAN).replace(tzinfo=None)
        jalali = jdatetime.datetime.fromgregorian(datetime=local)
        start_j = jdatetime.datetime(jalali.year, jalali.month, 1, 0, 0, 0)
        end_j = jdatetime.datetime(jalali.year + 1, 1, 1) if jalali.month == 12 else jdatetime.datetime(jalali.year, jalali.month + 1, 1)
        start = start_j.togregorian().replace(tzinfo=TEHRAN)
        end = end_j.togregorian().replace(tzinfo=TEHRAN)
        return start, end
    raise AppError("بازه نامعتبر است")


def summary_for(conn, kind: str) -> dict:
    start, end = range_bounds(kind)
    rows = conn.execute(
        """SELECT id, payable, discount, created_at FROM sales
           WHERE status='paid' AND created_at>=? AND created_at<?""",
        (iso(start), iso(end)),
    ).fetchall()
    parsed = []
    for row in rows:
        parsed.append((datetime.fromisoformat(row["created_at"]), int(row["payable"]), int(row["discount"])))
    points = []
    if kind == "day":
        buckets = [(hour, start + timedelta(hours=hour), start + timedelta(hours=hour + 1)) for hour in range(24)]
    elif kind == "week":
        names = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
        buckets = [(names[i], start + timedelta(days=i), start + timedelta(days=i + 1)) for i in range(7)]
    else:
        buckets = []
        cursor = start
        while cursor < end:
            nxt = cursor + timedelta(days=1)
            local = cursor.astimezone(TEHRAN).replace(tzinfo=None)
            buckets.append((jdatetime.datetime.fromgregorian(datetime=local).day, cursor, nxt))
            cursor = nxt
    for label, bucket_start, bucket_end in buckets:
        total = sum(pay for stamp, pay, _disc in parsed if bucket_start <= stamp < bucket_end)
        points.append({"label": label, "total": total})
    local = start.astimezone(TEHRAN).replace(tzinfo=None)
    jalali = jdatetime.datetime.fromgregorian(datetime=local)
    label = f"{jalali.day} {JMONTHS[jalali.month - 1]} {jalali.year}"
    if kind == "week":
        label = f"هفته از {label}"
    elif kind == "month":
        label = f"{JMONTHS[jalali.month - 1]} {jalali.year}"
    top_rows = conn.execute(
        """SELECT si.name AS name, SUM(si.qty) AS qty, SUM(si.line_total) AS total
           FROM sale_items si JOIN sales s ON s.id = si.sale_id
           WHERE s.status='paid' AND s.created_at>=? AND s.created_at<?
           GROUP BY si.product_id, IFNULL(si.variation_id, 0), si.name
           ORDER BY total DESC LIMIT 5""",
        (iso(start), iso(end)),
    ).fetchall()
    return {
        "range": kind,
        "label": label,
        "total": sum(pay for _s, pay, _d in parsed),
        "discount": sum(disc for _s, _p, disc in parsed),
        "count": len(parsed),
        "points": points,
        "top": [{"name": row["name"], "qty": row["qty"], "total": row["total"]} for row in top_rows],
    }


def payment_settings(settings: dict) -> dict:
    data = dict(settings)
    merchant = (data.get("gateway_merchant") or "").strip()
    if not merchant and data.get("gateway_sandbox") == "1":
        merchant = SANDBOX_MERCHANT
    callback = (data.get("gateway_callback") or "").strip()
    if not callback.startswith("http://") and not callback.startswith("https://"):
        callback = WEBAKERY_URL
    data["gateway_merchant"] = merchant
    data["gateway_callback"] = callback.rstrip("/")
    return data


def gateway_request(settings: dict, sale_id: int, payable: int, phone: str, description: str | None = None) -> tuple[str, str]:
    settings = payment_settings(settings)
    merchant = (settings.get("gateway_merchant") or "").strip()
    callback = (settings.get("gateway_callback") or "").strip()
    if not merchant:
        raise AppError("مرچنت کد درگاه وب‌بیکری را در تنظیمات وارد کنید")
    if not callback.startswith("http://") and not callback.startswith("https://"):
        raise AppError("آدرس بازگشت درگاه را در تنظیمات وارد کنید")
    if payable < 1000:
        raise AppError("حداقل مبلغ درگاه ۱۰۰۰ تومان است")
    gateway = settings.get("gateway") or "zarinpal"
    sandbox = settings.get("gateway_sandbox") == "1"
    amount = payable * 10
    description = description or f"فاکتور {sale_id} دفترچی"
    if gateway == "zarinpal":
        host = "https://sandbox.zarinpal.com" if sandbox else "https://api.zarinpal.com"
        code, body = http_request("POST", f"{host}/pg/v4/payment/request.json", {
            "merchant_id": merchant,
            "amount": amount,
            "callback_url": callback,
            "description": description,
            "metadata": {"mobile": phone} if phone else {},
        })
        data = body.get("data") if isinstance(body, dict) else None
        authority = data.get("authority") if isinstance(data, dict) else None
        if code >= 400 or not authority or data.get("code") not in (100, "100"):
            raise AppError("درگاه پرداخت درخواست را نپذیرفت", 502)
        start = "https://sandbox.zarinpal.com" if sandbox else "https://www.zarinpal.com"
        return authority, f"{start}/pg/StartPay/{authority}"
    if gateway == "idpay":
        code, body = http_request(
            "POST",
            "https://api.idpay.ir/v1.1/payment",
            {"order_id": str(sale_id), "amount": amount, "callback": callback, "desc": description, "phone": phone},
            headers={"X-API-KEY": merchant, "X-SANDBOX": "1" if sandbox else "0"},
        )
        if code >= 400 or not isinstance(body, dict) or not body.get("id") or not body.get("link"):
            raise AppError("آی‌دی‌پی درخواست را نپذیرفت", 502)
        return str(body["id"]), body["link"]
    if gateway == "zibal" and not sandbox:
        if not callback.startswith("https://"):
            callback = WEBAKERY_URL
        body = host_pay("request", {
            "amount": amount,
            "callbackUrl": callback,
            "description": description,
            "orderId": str(sale_id),
            "mobile": phone or "",
        })
        track = str(body.get("trackId") or "")
        if not track:
            raise AppError("هاست شماره پرداخت زیبال را نداد", 502)
        return track, str(body.get("payUrl") or f"https://gateway.zibal.ir/start/{track}")
    if gateway == "zibal":
        code, body = http_request("POST", "https://gateway.zibal.ir/v1/request", {
            "merchant": zibal_merchant_id(merchant, sandbox),
            "amount": amount,
            "callbackUrl": callback,
            "description": description,
            "orderId": str(sale_id),
            "mobile": phone or None,
        })
        if code >= 400 or not isinstance(body, dict) or body.get("result") not in (100, "100") or not body.get("trackId"):
            detail = str(body.get("message") or "").strip() if isinstance(body, dict) else ""
            raise AppError(f"زیبال درخواست را نپذیرفت{(': ' + detail) if detail else ''}", 502)
        return str(body["trackId"]), f"https://gateway.zibal.ir/start/{body['trackId']}"
    raise AppError("درگاه ناشناخته است")


def gateway_verify(settings: dict, sale) -> str:
    settings = payment_settings(settings)
    gateway = sale["gateway"] or settings.get("gateway") or "zarinpal"
    merchant = (settings.get("gateway_merchant") or "").strip()
    sandbox = settings.get("gateway_sandbox") == "1"
    amount = int(sale["payable"]) * 10
    ref = sale["gateway_ref"]
    if not ref:
        raise AppError("شناسه پرداخت این فاکتور خالی است")
    if gateway == "zarinpal":
        host = "https://sandbox.zarinpal.com" if sandbox else "https://api.zarinpal.com"
        code, body = http_request("POST", f"{host}/pg/v4/payment/verify.json", {
            "merchant_id": merchant, "amount": amount, "authority": ref,
        })
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict) or data.get("code") not in (100, 101, "100", "101"):
            raise AppError("پرداخت در درگاه تأیید نشد", 502)
        return str(data.get("ref_id") or ref)
    if gateway == "idpay":
        code, body = http_request(
            "POST",
            "https://api.idpay.ir/v1.1/payment/verify",
            {"id": ref, "order_id": str(sale["id"])},
            headers={"X-API-KEY": merchant, "X-SANDBOX": "1" if sandbox else "0"},
        )
        if code >= 400 or not isinstance(body, dict) or str(body.get("status")) not in {"100", "101", "200"}:
            raise AppError("پرداخت آی‌دی‌پی تأیید نشد", 502)
        return str(body.get("track_id") or ref)
    if gateway == "zibal" and not sandbox:
        return host_zibal_verify(ref)
    if gateway == "zibal":
        track = int(ref) if str(ref).isdigit() else ref
        code, body = http_request("POST", "https://gateway.zibal.ir/v1/verify", {
            "merchant": zibal_merchant_id(merchant, sandbox), "trackId": track,
        })
        if not isinstance(body, dict) or body.get("result") not in (100, 201, "100", "201"):
            raise AppError("پرداخت زیبال تأیید نشد", 502)
        return str(body.get("refNumber") or ref)
    if gateway == "woocommerce":
        _code, body = woo_request(settings, "GET", f"orders/{ref}")
        if not isinstance(body, dict):
            raise AppError("فروشگاه وضعیت سفارش را نداد", 502)
        if body.get("status") not in {"processing", "completed"}:
            raise AppError("پرداخت در فروشگاه هنوز تأیید نشده است", 502)
        return str(body.get("transaction_id") or ref)
    raise AppError("درگاه ناشناخته است")


def zibal_merchant_id(merchant: str, sandbox: bool) -> str:
    if merchant and merchant != SANDBOX_MERCHANT:
        return merchant
    if sandbox:
        return "zibal"
    return merchant


def license_gateway_settings(settings: dict) -> dict:
    data = dict(settings)
    merchant = (data.get("license_merchant") or "").strip() or ZIBAL_LICENSE_MERCHANT
    data["gateway"] = "zibal"
    data["gateway_merchant"] = merchant
    data["gateway_sandbox"] = "0"
    callback = (data.get("gateway_callback") or "").strip()
    if not callback.startswith("http://") and not callback.startswith("https://"):
        data["gateway_callback"] = WEBAKERY_URL
    return data


def explain_host_pay(detail: str) -> str:
    text = str(detail or "")
    low = text.lower()
    if "invalid ip" in low:
        ip = text.replace(":", " ").split()[-1].strip(".,")
        return (
            f"صفحه درگاه در مرورگر باز می‌شود و آی‌پی رایانه‌های فروشگاه به زیبال فرستاده نمی‌شود. "
            f"زیبال فقط آی‌پی هاست را دیده و نپذیرفته است: {ip}."
        )
    if "404" in low:
        return (
            "فایل pay.php روی هاست نیست. آن را کنار mail.php در public_html/license-server بگذارید، "
            "بعد https://webakery.ir/license-server/pay.php باید ok نشان بدهد."
        )
    if "اتصال" in text or "timed out" in low or "timeout" in low:
        return "اتصال به هاست وب‌بیکری برای ساخت پرداخت برقرار نشد."
    return f"پرداخت از هاست ساخته نشد: {text[:180]}"


def host_account(action: str, fields: dict) -> dict:
    payload = {"key": HOST_MAIL_KEY, "action": action, **fields}
    failures = []
    for url in HOST_ACCOUNT_URLS:
        try:
            status, body = http_request("POST", url, payload=payload, timeout=8)
        except AppError as exc:
            failures.append(str(exc))
            continue
        if not isinstance(body, dict) or "raw" in body:
            failures.append(f"HTTP {status}")
            continue
        if status < 400 and body.get("ok") and body.get("service") == "daftarchi-accounts":
            return body
        if body.get("service") == "daftarchi-accounts" or isinstance(body.get("ok"), bool):
            raise AppError(str(body.get("error") or f"HTTP {status}"), 502)
        failures.append(f"HTTP {status}")
    raise AppError(failures[-1] if failures else "HTTP 404", 502)


def license_host_item(conn, row) -> dict:
    shop = conn.execute("SELECT phone FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
    return {
        "shop_phone": shop["phone"] if shop else "",
        "local_id": int(row["id"]),
        "buyer_name": row["buyer_name"],
        "phone": row["phone"],
        "plan": row["plan"],
        "title": PLANS.get(row["plan"], (row["plan"], 0, ""))[0],
        "payable": int(row["payable"]),
        "status": row["status"] or "paid",
        "starts_at": row["starts_at"] or "",
        "ends_at": row["ends_at"] or "",
        "gateway_ref": row["gateway_ref"] or "",
        "payment_method": row["payment_method"] or "",
    }


def store_license_on_host(conn, row) -> bool:
    try:
        body = host_account("save", {"items": [license_host_item(conn, row)]})
    except AppError:
        conn.execute("UPDATE licenses SET host_saved=0 WHERE id=?", (row["id"],))
        return False
    saved_ids = {int(item) for item in (body.get("ids") or []) if str(item).isdigit()}
    if saved_ids and int(row["id"]) not in saved_ids:
        conn.execute("UPDATE licenses SET host_saved=0 WHERE id=?", (row["id"],))
        return False
    conn.execute("UPDATE licenses SET host_saved=1 WHERE id=?", (row["id"],))
    return True


def sync_licenses_to_host(conn) -> None:
    rows = conn.execute(
        "SELECT * FROM licenses WHERE COALESCE(host_saved,0)=0 ORDER BY id DESC LIMIT 20"
    ).fetchall()
    if not rows:
        return
    try:
        body = host_account("save", {"items": [license_host_item(conn, row) for row in rows]})
    except AppError:
        return
    saved_ids = {int(item) for item in (body.get("ids") or []) if str(item).isdigit()}
    for row in rows:
        if int(row["id"]) in saved_ids:
            conn.execute("UPDATE licenses SET host_saved=1 WHERE id=?", (row["id"],))


def host_pay(action: str, fields: dict) -> dict:
    payload = {"key": HOST_MAIL_KEY, "action": action, **fields}
    failures = []
    for url in HOST_PAY_URLS:
        try:
            status, body = http_request("POST", url, payload=payload, timeout=20)
        except AppError as exc:
            failures.append(str(exc))
            continue
        if not isinstance(body, dict):
            failures.append(f"HTTP {status}")
            continue
        if status < 400 and body.get("ok") and body.get("service") == "daftarchi-pay":
            return body
        # A live pay.php answered. A later 404 page must not replace this error.
        if body.get("service") == "daftarchi-pay" or isinstance(body.get("ok"), bool):
            detail = str(body.get("error") or body.get("message") or f"HTTP {status}")
            raise AppError(explain_host_pay(detail), 502)
        failures.append(str(body.get("error") or body.get("message") or f"HTTP {status}"))
    detail = next((item for item in failures if "invalid ip" in item.lower()), "")
    if not detail:
        detail = failures[-1] if failures else "HTTP 404"
    raise AppError(explain_host_pay(detail), 502)


def webakery_payment(settings: dict, order_id: int, title: str, payable: int, buyer: str, phone: str) -> tuple[str, str, str]:
    tuned = license_gateway_settings(settings)
    body = host_pay("request", {
        "amount": int(payable) * 10,
        "callbackUrl": tuned.get("gateway_callback") or WEBAKERY_URL,
        "description": f"لایسنس {title} دفترچی — webakery.ir",
        "orderId": str(order_id),
        "mobile": phone or "",
    })
    track = str(body.get("trackId") or "")
    if not track:
        raise AppError("هاست شماره پرداخت زیبال را نداد", 502)
    pay_url = str(body.get("payUrl") or f"https://gateway.zibal.ir/start/{track}")
    return "zibal", track, pay_url


def host_zibal_verify(track: str) -> str:
    if not str(track or "").strip():
        raise AppError("شناسه پرداخت این لایسنس خالی است")
    body = host_pay("verify", {"trackId": int(track) if str(track).isdigit() else track})
    if body.get("result") not in (100, 201, "100", "201"):
        raise AppError("پرداخت هنوز در زیبال تأیید نشده است", 409)
    return str(body.get("refNumber") or track)


def days_left(end: datetime) -> int:
    seconds = (end - now_dt()).total_seconds()
    if seconds <= 0:
        return 0
    return (int(seconds) + 86399) // 86400


def ensure_access(conn) -> dict:
    now = now_dt()
    paid = conn.execute(
        """SELECT * FROM licenses
           WHERE status='paid' AND plan!='7d' AND ends_at>?
           ORDER BY ends_at DESC LIMIT 1""",
        (iso(now),),
    ).fetchone()
    if paid:
        end = datetime.fromisoformat(paid["ends_at"])
        if end.tzinfo is None:
            end = end.replace(tzinfo=TEHRAN)
        title = PLANS.get(paid["plan"], (paid["plan"], 0, ""))[0]
        return {
            "mode": "paid",
            "active": True,
            "title": title,
            "days_left": days_left(end),
            "ends_at": paid["ends_at"],
            "ends_jalali": to_jalali(paid["ends_at"]),
        }
    settings = get_settings(conn)
    started = str(settings.get("trial_started_at") or "").strip()
    ends_at = str(settings.get("trial_ends_at") or "").strip()
    if not started or not ends_at:
        start = now.replace(microsecond=0)
        end = start + timedelta(days=TRIAL_DAYS)
        started = iso(start)
        ends_at = iso(end)
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('trial_started_at', ?)", (started,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('trial_ends_at', ?)", (ends_at,))
    end = datetime.fromisoformat(ends_at)
    if end.tzinfo is None:
        end = end.replace(tzinfo=TEHRAN)
    left = days_left(end)
    return {
        "mode": "trial" if left else "expired",
        "active": left > 0,
        "title": "۷ روز رایگان",
        "days_left": left,
        "ends_at": ends_at,
        "ends_jalali": to_jalali(ends_at),
    }


def require_access(conn) -> dict:
    access = ensure_access(conn)
    if not access["active"]:
        raise AppError("مهلت ۷ روز رایگان تمام شده. برای ادامه، از بخش لایسنس اپ یک طرح بخرید.", 402)
    return access


def woo_item(row) -> dict:
    item = {
        "name": row["name"],
        "type": "simple",
        "regular_price": str(row["price"]),
        "manage_stock": True,
        "stock_quantity": row["stock"],
        "status": "publish",
    }
    if row["sku"]:
        item["sku"] = row["sku"]
    if row["barcode"]:
        item["meta_data"] = [{"key": "barcode", "value": row["barcode"]}]
    image = row["image"] or ""
    if image.startswith("http://") or image.startswith("https://"):
        item["images"] = [{"src": image}]
    return item


def remote_barcode(remote: dict) -> str | None:
    for meta in remote.get("meta_data") or []:
        if str(meta.get("key") or "").lower() in {"barcode", "_barcode"}:
            value = str(meta.get("value") or "").strip()
            return value or None
    return None


def save_settings(conn, payload: dict):
    allowed = set(DEFAULT_SETTINGS) - {"must_change_password"}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key in BOOL_KEYS:
            stored = "1" if str(value) in {"1", "true", "True", "on"} else "0"
        elif key in {"price_3m", "price_6m", "price_12m", "price_50y"}:
            stored = str(parse_money(value, "قیمت لایسنس"))
        elif key in {"cap_50y", "low_stock"}:
            stored = str(parse_money(value, key, allow_empty=True))
        elif key == "pos_port":
            stored = str(parse_money(value or "0", "پورت", allow_empty=True))
            if int(stored) > 65535:
                raise AppError("پورت نامعتبر است")
        elif key == "pos_provider":
            stored = str(value or "manual")
            if stored not in POS_PROVIDERS:
                raise AppError("کارت‌خوان نامعتبر است")
        elif key == "gateway":
            stored = str(value or "zarinpal")
            if stored not in GATEWAYS:
                raise AppError("درگاه نامعتبر است")
        elif key == "sms_provider":
            stored = str(value or "internal")
            if stored not in SMS_PROVIDERS:
                raise AppError("سامانه پیامک نامعتبر است")
        elif key == "moadian_fiscal_id":
            stored = clean_text(value, "شناسه حافظه مالیاتی", 6).upper()
            if stored and not re.fullmatch(r"[A-Z0-9]{6}", stored):
                raise AppError("شناسه یکتای حافظه مالیاتی ۶ کاراکتر است")
        elif key == "moadian_economic_code":
            stored = re.sub(r"\D", "", str(value or "").translate(DIGITS))
            if stored and not re.fullmatch(r"\d{11,14}", stored):
                raise AppError("کد اقتصادی باید ۱۱ تا ۱۴ رقم باشد")
        elif key == "moadian_private_key":
            stored = str(value or "").strip()
            if not stored:
                continue
            if "PRIVATE KEY" not in stored or len(stored) > 8000:
                raise AppError("کلید خصوصی مودیان معتبر نیست")
            try:
                from cryptography.hazmat.primitives import serialization
                serialization.load_pem_private_key(stored.encode(), password=None)
            except ImportError:
                raise AppError("کتابخانه رمزنگاری روی این رایانه نیست. دفترچی را دوباره اجرا کنید.")
            except Exception:
                raise AppError("کلید خصوصی خوانده نشد. فایل pem کارپوشه را بچسبانید.")
        elif key == "shop_name":
            stored = clean_text(value, "نام فروشگاه", 80) or "دفترچی"
        elif key == "shop_logo":
            text = str(value or "").strip()
            stored = clean_image(text) if text else ""
        elif key == "telegram_bot_token":
            stored = str(value or "").strip()
            if not stored:
                continue
            if not re.fullmatch(r"\d{6,15}:[A-Za-z0-9_-]{20,}", stored):
                raise AppError("توکن ربات تلگرام معتبر نیست")
        elif key == "telegram_chat_id":
            stored = str(value or "").translate(DIGITS).replace(" ", "")
            if stored and not re.fullmatch(r"-?\d{1,20}", stored):
                raise AppError("شناسه چت تلگرام عدد است")
        elif key == "moadian_vat":
            stored = str(parse_money(value or "10", "نرخ مالیات", allow_empty=True))
            if int(stored) > 100:
                raise AppError("نرخ مالیات تا ۱۰۰ است")
        else:
            stored = clean_text(value, key, 400)
            if key in {"wp_url", "gateway_callback"} and stored:
                if not stored.startswith("http://") and not stored.startswith("https://"):
                    raise AppError("آدرس باید با http:// یا https:// شروع شود")
                stored = stored.rstrip("/")
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, stored),
        )


def init_db():
    DATA.mkdir(parents=True, exist_ok=True)
    UPLOAD.mkdir(parents=True, exist_ok=True)
    secret_path = DATA / "secret.key"
    if secret_path.exists():
        app.secret_key = secret_path.read_text().strip()
    else:
        app.secret_key = secrets.token_hex(32)
        secret_path.write_text(app.secret_key)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              phone TEXT UNIQUE NOT NULL,
              email TEXT UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('admin','cashier')),
              email_verified INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS accounts (
              id INTEGER PRIMARY KEY,
              code TEXT UNIQUE,
              name TEXT NOT NULL,
              type TEXT NOT NULL,
              system INTEGER NOT NULL DEFAULT 0,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS customers (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              phone TEXT UNIQUE NOT NULL,
              account_id INTEGER,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              sku TEXT UNIQUE,
              barcode TEXT UNIQUE,
              price INTEGER NOT NULL,
              cost INTEGER NOT NULL DEFAULT 0,
              stock INTEGER NOT NULL DEFAULT 0,
              image TEXT,
              woo_id INTEGER,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inventory_logs (
              id INTEGER PRIMARY KEY,
              product_id INTEGER NOT NULL,
              kind TEXT NOT NULL,
              qty_delta INTEGER NOT NULL DEFAULT 0,
              old_value INTEGER,
              new_value INTEGER,
              note TEXT,
              created_at TEXT NOT NULL,
              user_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS register_sessions (
              id INTEGER PRIMARY KEY,
              opened_at TEXT NOT NULL,
              closed_at TEXT,
              opening_cash INTEGER NOT NULL,
              counted_cash INTEGER,
              status TEXT NOT NULL,
              opened_by INTEGER,
              closed_by INTEGER
            );
            CREATE TABLE IF NOT EXISTS sales (
              id INTEGER PRIMARY KEY,
              status TEXT NOT NULL,
              customer_id INTEGER,
              customer_name TEXT,
              customer_phone TEXT,
              subtotal INTEGER NOT NULL,
              discount INTEGER NOT NULL,
              payable INTEGER NOT NULL,
              payment_method TEXT NOT NULL,
              pos_ref TEXT,
              gateway TEXT,
              gateway_ref TEXT,
              pay_url TEXT,
              session_id INTEGER,
              user_id INTEGER,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sale_items (
              id INTEGER PRIMARY KEY,
              sale_id INTEGER NOT NULL,
              product_id INTEGER NOT NULL,
              variation_id INTEGER,
              name TEXT NOT NULL,
              qty INTEGER NOT NULL,
              unit_price INTEGER NOT NULL,
              unit_cost INTEGER NOT NULL,
              line_total INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS product_variations (
              id INTEGER PRIMARY KEY,
              product_id INTEGER NOT NULL,
              woo_id INTEGER UNIQUE,
              sku TEXT,
              barcode TEXT,
              price INTEGER NOT NULL,
              stock INTEGER,
              in_stock INTEGER NOT NULL DEFAULT 1,
              label TEXT NOT NULL,
              attributes TEXT NOT NULL,
              image TEXT,
              active INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_variations_product ON product_variations(product_id);
            CREATE TABLE IF NOT EXISTS journal_entries (
              id INTEGER PRIMARY KEY,
              memo TEXT,
              source TEXT,
              source_id INTEGER,
              user_id INTEGER,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS journal_lines (
              id INTEGER PRIMARY KEY,
              entry_id INTEGER NOT NULL,
              account_id INTEGER NOT NULL,
              debit INTEGER NOT NULL DEFAULT 0,
              credit INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS purchases (
              id INTEGER PRIMARY KEY,
              product_id INTEGER NOT NULL,
              qty INTEGER NOT NULL,
              unit_cost INTEGER NOT NULL,
              total INTEGER NOT NULL,
              pay_account_id INTEGER NOT NULL,
              session_id INTEGER,
              user_id INTEGER,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS licenses (
              id INTEGER PRIMARY KEY,
              plan TEXT NOT NULL,
              list_price INTEGER NOT NULL,
              discount INTEGER NOT NULL,
              payable INTEGER NOT NULL,
              buyer_name TEXT NOT NULL,
              phone TEXT NOT NULL,
              starts_at TEXT NOT NULL,
              ends_at TEXT NOT NULL,
              payment_method TEXT NOT NULL,
              session_id INTEGER,
              user_id INTEGER,
              created_at TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'paid',
              gateway TEXT,
              gateway_ref TEXT,
              pay_url TEXT,
              host_saved INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS receipts (
              id INTEGER PRIMARY KEY,
              account_id INTEGER NOT NULL,
              amount INTEGER NOT NULL,
              payment_method TEXT NOT NULL,
              session_id INTEGER,
              memo TEXT,
              user_id INTEGER,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notifications (
              id INTEGER PRIMARY KEY,
              channel TEXT NOT NULL,
              recipient TEXT NOT NULL,
              body TEXT NOT NULL,
              status TEXT NOT NULL,
              detail TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS password_resets (
              id INTEGER PRIMARY KEY,
              user_id INTEGER NOT NULL,
              code_hash TEXT NOT NULL,
              channel TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              used INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS support_messages (
              id INTEGER PRIMARY KEY,
              kind TEXT NOT NULL,
              body TEXT NOT NULL,
              page TEXT,
              app_version TEXT,
              error TEXT,
              delivery TEXT,
              detail TEXT,
              user_id INTEGER,
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);
            CREATE INDEX IF NOT EXISTS idx_sales_session ON sales(session_id);
            CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
            """
        )
        user_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "email_verified" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
        if not conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            conn.execute(
                "INSERT INTO users (name, phone, email, password_hash, role, email_verified, created_at) VALUES (?,?,?,?,?,?,?)",
                ("مدیر", INITIAL_PHONE, None, hash_pw(INITIAL_PASSWORD), "admin", 1, iso()),
            )
        if not conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
            for code, name, kind in SYSTEM_ACCOUNTS:
                conn.execute(
                    "INSERT INTO accounts (code, name, type, system, active, created_at) VALUES (?,?,?,1,1,?)",
                    (code, name, kind, iso()),
                )
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (key, value))
        for key in ("wp_url", "gateway_callback", "gateway_merchant", "license_merchant"):
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            if row and not str(row["value"] or "").strip():
                conn.execute("UPDATE settings SET value=? WHERE key=?", (DEFAULT_SETTINGS[key], key))
        merchant_row = conn.execute("SELECT value FROM settings WHERE key='gateway_merchant'").fetchone()
        gateway_row = conn.execute("SELECT value FROM settings WHERE key='gateway'").fetchone()
        if merchant_row and merchant_row["value"] == ZIBAL_LICENSE_MERCHANT and gateway_row and gateway_row["value"] != "zibal":
            conn.execute("UPDATE settings SET value='zibal' WHERE key='gateway'")
            conn.execute("UPDATE settings SET value='0' WHERE key='gateway_sandbox'")
        price_50 = conn.execute("SELECT value FROM settings WHERE key='price_50y'").fetchone()
        if price_50 and str(price_50["value"]).strip() == "12000000":
            conn.execute("UPDATE settings SET value='15000000' WHERE key='price_50y'")
        have = {row["name"] for row in conn.execute("PRAGMA table_info(licenses)")}
        if "status" not in have:
            conn.execute("ALTER TABLE licenses ADD COLUMN status TEXT NOT NULL DEFAULT 'paid'")
        if "gateway" not in have:
            conn.execute("ALTER TABLE licenses ADD COLUMN gateway TEXT")
        if "gateway_ref" not in have:
            conn.execute("ALTER TABLE licenses ADD COLUMN gateway_ref TEXT")
        if "pay_url" not in have:
            conn.execute("ALTER TABLE licenses ADD COLUMN pay_url TEXT")
        if "host_saved" not in have:
            conn.execute("ALTER TABLE licenses ADD COLUMN host_saved INTEGER NOT NULL DEFAULT 0")
        product_cols = {row["name"] for row in conn.execute("PRAGMA table_info(products)")}
        if "tax_code" not in product_cols:
            conn.execute("ALTER TABLE products ADD COLUMN tax_code TEXT")
        if "product_type" not in product_cols:
            conn.execute("ALTER TABLE products ADD COLUMN product_type TEXT NOT NULL DEFAULT 'simple'")
        sale_item_cols = {row["name"] for row in conn.execute("PRAGMA table_info(sale_items)")}
        if "variation_id" not in sale_item_cols:
            conn.execute("ALTER TABLE sale_items ADD COLUMN variation_id INTEGER")
        sale_cols = {row["name"] for row in conn.execute("PRAGMA table_info(sales)")}
        for column in ("moadian_uid", "moadian_taxid", "moadian_reference", "moadian_status", "moadian_error"):
            if column not in sale_cols:
                conn.execute(f"ALTER TABLE sales ADD COLUMN {column} TEXT")


@app.errorhandler(AppError)
def handle_app_error(exc: AppError):
    payload = {"error": str(exc)}
    payload.update(exc.extra)
    return jsonify(payload), exc.status


@app.errorhandler(RequestEntityTooLarge)
def handle_large(_exc):
    return jsonify(error="حجم فایل زیاد است"), 413


@app.errorhandler(sqlite3.IntegrityError)
def handle_integrity(_exc):
    return jsonify(error="این کد یا بارکد قبلاً ثبت شده است"), 400


@app.errorhandler(Exception)
def handle_exception(exc: Exception):
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, AppError):
        return jsonify(error=str(exc)), exc.status
    log.exception("unhandled")
    if request.path.startswith("/api/"):
        return jsonify(error="خطای داخلی"), 500
    return "error", 500


@app.after_request
def no_store(resp):
    if request.path.startswith("/api/") or request.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
def home():
    resp = send_file(Path(__file__).resolve().parent / "templates" / "index.html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/manifest.webmanifest")
def web_manifest():
    resp = send_file(Path(__file__).resolve().parent / "static" / "manifest.webmanifest", mimetype="application/manifest+json")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/sw.js")
def service_worker():
    resp = send_file(Path(__file__).resolve().parent / "static" / "sw.js", mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.get("/uploads/<name>")
def uploaded(name: str):
    if not re.fullmatch(r"[a-f0-9]{32}\.(jpg|jpeg|png|webp|gif)", name):
        abort(404)
    return send_from_directory(UPLOAD, name)


@app.get("/api/health")
def health():
    return jsonify(ok=True, name="دفترچی", version=APP_VERSION)


@app.get("/api/update")
def update_info():
    current = APP_VERSION
    quiet = {
        "current": current,
        "available": False,
        "update": False,
        "version": "",
        "url": "",
        "notes": "",
        "manifest": UPDATE_MANIFEST_URL,
    }
    status, body, manifest = 404, None, UPDATE_MANIFEST_URL
    for candidate in UPDATE_MANIFEST_URLS:
        try:
            status, body = http_request("GET", candidate, timeout=4)
        except AppError:
            continue
        manifest = candidate
        if status < 400 and isinstance(body, dict) and body.get("version"):
            break
    else:
        return jsonify(quiet)
    if status >= 400 or not isinstance(body, dict):
        quiet["manifest"] = manifest
        return jsonify(quiet)
    latest = str(body.get("version") or "").strip()
    url = str(body.get("url") or "").strip()
    notes = str(body.get("notes") or "").strip()[:300]
    if not latest or not url.startswith("https://"):
        return jsonify(quiet)
    return jsonify(
        current=current,
        available=True,
        update=version_tuple(latest) > version_tuple(current),
        version=latest,
        url=url,
        notes=notes,
        manifest=manifest,
    )


def telegram_text(user, kind: str, body: str, page: str, error: str, settings: dict) -> str:
    shop = settings.get("shop_name") or "دفترچی"
    lines = [
        f"دفترچی {APP_VERSION}",
        f"فروشگاه: {shop}",
        f"کاربر: {user['name']}",
        f"نوع: {'گزارش خطا' if kind == 'bug' else 'چت'}",
        f"صفحه: {page or '—'}",
        body,
    ]
    if error:
        lines.append(f"آخرین خطا: {error}")
    return "\n".join(lines)[:3500]


def deliver_telegram(settings: dict, text: str) -> tuple[str, str]:
    token = (settings.get("telegram_bot_token") or "").strip()
    chat = (settings.get("telegram_chat_id") or "").strip()
    if re.fullmatch(r"\d{6,15}:[A-Za-z0-9_-]{20,}", token) and re.fullmatch(r"-?\d{1,20}", chat):
        try:
            status, body = http_request(
                "POST",
                f"https://api.telegram.org/bot{token}/sendMessage",
                {"chat_id": chat, "text": text},
                timeout=8,
            )
        except AppError as exc:
            return "stored", str(exc)
        if status < 400 and isinstance(body, dict) and body.get("ok"):
            return "telegram", "به تلگرام فرستاده شد"
        description = str(body.get("description") or "") if isinstance(body, dict) else ""
        return "stored", (description or "تلگرام پیام را نپذیرفت. توکن و شناسه چت را در تنظیمات بررسی کنید.")[:180]
    for url in HOST_TELEGRAM_URLS:
        try:
            status, body = http_request("POST", url, {"key": HOST_MAIL_KEY, "text": text}, timeout=6)
        except AppError:
            continue
        if status < 400 and isinstance(body, dict) and body.get("ok"):
            return "host", "از هاست به تلگرام فرستاده شد"
    return "stored", "پیام در دفترچی ماند. توکن ربات و شناسه چت را در تنظیمات بگذارید، یا telegram.php را روی هاست بگذارید."


@app.get("/api/support/messages")
def support_messages():
    require_user()
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, kind, body, page, error, delivery, detail, created_at FROM support_messages ORDER BY id DESC LIMIT 40"
        ).fetchall()
    return jsonify(messages=[dict(row) for row in reversed(rows)])


@app.post("/api/support/messages")
def support_send():
    user = require_user()
    payload = body_json()
    kind = payload.get("kind") if payload.get("kind") in {"chat", "bug"} else "chat"
    body = clean_text(payload.get("body"), "متن", 1000, required=True)
    page = clean_text(payload.get("page"), "صفحه", 40)
    error = clean_text(payload.get("error"), "خطا", 300)
    with connect() as conn:
        settings = get_settings(conn)
        delivery, detail = deliver_telegram(settings, telegram_text(user, kind, body, page, error, settings))
        cur = conn.execute(
            """INSERT INTO support_messages (kind, body, page, app_version, error, delivery, detail, user_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (kind, body, page, APP_VERSION, error, delivery, detail, user["id"], iso()),
        )
        message_id = cur.lastrowid
    return jsonify(ok=True, id=message_id, sent=delivery in {"telegram", "host"}, delivery=delivery, detail=detail)


def shop_profile(conn) -> dict:
    settings = get_settings(conn)
    return {"name": settings.get("shop_name") or "دفترچی", "logo": settings.get("shop_logo") or ""}


@app.get("/api/auth/bootstrap")
def bootstrap():
    with connect() as conn:
        settings = get_settings(conn)
        flag = settings.get("must_change_password") == "1"
        ready = smtp_ready(settings)
    extra = {"smtp_ready": ready, "host_mail": host_mail_ready(), "version": APP_VERSION}
    if flag:
        return jsonify(initial=True, phone=INITIAL_PHONE, password=INITIAL_PASSWORD, **extra)
    return jsonify(initial=False, **extra)


@app.post("/api/auth/login")
def login():
    payload = body_json()
    ident = str(payload.get("ident") or "")
    password = str(payload.get("password") or "")
    with connect() as conn:
        row = find_user(conn, ident)
        if not row or not check_pw(password, row["password_hash"]):
            raise AppError("شماره یا رمز نادرست است", 401)
        if row["email"] and not int(row["email_verified"] or 0):
            raise AppError(
                "این حساب هنوز با جیمیل تأیید نشده. کد شش‌رقمی را وارد کنید.",
                403,
                needs_verify=True,
                ident=row["email"],
            )
        user = public_user(row)
        flag = get_settings(conn).get("must_change_password") == "1"
        access = ensure_access(conn)
        shop = shop_profile(conn)
    session.clear()
    session["uid"] = row["id"]
    session.permanent = True
    return jsonify(user=user, must_change_password=flag, access=access, shop=shop)


@app.post("/api/auth/register")
def register():
    payload = body_json()
    name = clean_text(payload.get("name"), "نام", 80, required=True)
    phone = norm_phone(payload.get("phone") or "")
    email = gmail_address(payload.get("email") or payload.get("gmail"))
    password = str(payload.get("password") or "")
    if re.fullmatch(r"9\d{9}", phone):
        phone = "0" + phone
    if not re.fullmatch(r"09\d{9}", phone):
        raise AppError("شماره موبایل معتبر نیست")
    if len(password) < 6 or len(password) > 100:
        raise AppError("رمز باید حداقل ۶ حرف باشد")
    with connect() as conn:
        settings = get_settings(conn)
        phone_owner = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        existing = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
        if phone_owner and (not existing or phone_owner["id"] != existing["id"]):
            if not check_pw(password, phone_owner["password_hash"]):
                raise AppError("این شماره قبلاً ثبت شده. با همان رمز از صفحه ورود وارد شوید.")
            user_id = phone_owner["id"]
            reopen = True
        elif existing and int(existing["email_verified"] or 0):
            if not check_pw(password, existing["password_hash"]):
                raise AppError("این جیمیل قبلاً ثبت شده. با همان رمز از صفحه ورود وارد شوید.")
            user_id = existing["id"]
            reopen = True
        else:
            reopen = False
            if existing:
                conn.execute(
                    "UPDATE users SET name=?, phone=?, password_hash=? WHERE id=?",
                    (name, phone, hash_pw(password), existing["id"]),
                )
                user_id = existing["id"]
            else:
                others = conn.execute("SELECT COUNT(*) AS c FROM users WHERE phone<>?", (INITIAL_PHONE,)).fetchone()["c"]
                role = "admin" if settings.get("must_change_password") == "1" and others == 0 else "cashier"
                cur = conn.execute(
                    """INSERT INTO users (name, phone, email, password_hash, role, email_verified, created_at)
                       VALUES (?,?,?,?,?,0,?)""",
                    (name, phone, email, hash_pw(password), role, iso()),
                )
                user_id = cur.lastrowid
        if not reopen:
            send_gmail_code(conn, settings, email, user_id, "verify")
            return jsonify(ok=True, email=email, needs_verify=True, delivery="email")
        conn.execute("UPDATE users SET email_verified=1 WHERE id=?", (user_id,))
        fresh = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        flag = get_settings(conn).get("must_change_password") == "1"
        user = public_user(fresh)
    session.clear()
    session["uid"] = user_id
    session.permanent = True
    return jsonify(ok=True, email=email, needs_verify=False, delivery="local", user=user, must_change_password=flag)


@app.post("/api/auth/verify")
def verify_email():
    payload = body_json()
    ident = str(payload.get("ident") or payload.get("email") or "")
    code = str(payload.get("code") or "").translate(DIGITS).strip()
    if not re.fullmatch(r"\d{6}", code):
        raise AppError("کد باید ۶ رقم باشد")
    with connect() as conn:
        user = find_user(conn, ident)
        if not user or not user["email"]:
            raise AppError("حسابی با این جیمیل پیدا نشد")
        if int(user["email_verified"] or 0):
            return jsonify(ok=True, already=True)
        row = conn.execute(
            "SELECT * FROM password_resets WHERE user_id=? AND used=0 AND channel='verify' ORDER BY id DESC LIMIT 1",
            (user["id"],),
        ).fetchone()
        digest = hashlib.sha256(code.encode()).hexdigest()
        if not row or row["expires_at"] < iso() or not secrets.compare_digest(row["code_hash"], digest):
            raise AppError("کد نادرست یا منقضی است")
        conn.execute("UPDATE password_resets SET used=1 WHERE id=?", (row["id"],))
        conn.execute("UPDATE users SET email_verified=1 WHERE id=?", (user["id"],))
        fresh = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        clear_initial_secret(conn, fresh)
    return jsonify(ok=True)


@app.post("/api/auth/verify/resend")
def resend_verify():
    payload = body_json()
    ident = str(payload.get("ident") or payload.get("email") or "")
    with connect() as conn:
        user = find_user(conn, ident)
        if not user or not user["email"]:
            raise AppError("حسابی با این جیمیل پیدا نشد")
        if int(user["email_verified"] or 0):
            raise AppError("این حساب قبلاً تأیید شده. وارد شوید.")
        send_gmail_code(conn, get_settings(conn), user["email"], user["id"], "verify")
    return jsonify(ok=True, delivery="email")


@app.post("/api/auth/email")
def attach_email():
    user = require_user()
    email = gmail_address(body_json().get("email"))
    with connect() as conn:
        other = conn.execute(
            "SELECT id FROM users WHERE lower(email)=? AND id<>?",
            (email, user["id"]),
        ).fetchone()
        if other:
            raise AppError("این جیمیل برای کاربر دیگری است")
        settings = get_settings(conn)
        conn.execute("UPDATE users SET email=?, email_verified=0 WHERE id=?", (email, user["id"]))
        send_gmail_code(conn, settings, email, user["id"], "verify")
    return jsonify(ok=True, email=email, needs_verify=True)


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/auth/me")
def me():
    user = current_user()
    with connect() as conn:
        flag = get_settings(conn).get("must_change_password") == "1" if user else False
        access = ensure_access(conn) if user else None
        shop = shop_profile(conn) if user else None
    return jsonify(user=public_user(user) if user else None, must_change_password=flag if user else False, access=access, shop=shop)


@app.post("/api/auth/password")
def change_password():
    user = require_user()
    payload = body_json()
    current = str(payload.get("current") or "")
    new_password = str(payload.get("password") or "")
    if len(new_password) < 6 or len(new_password) > 100:
        raise AppError("رمز جدید باید حداقل ۶ حرف باشد")
    if not check_pw(current, user["password_hash"]):
        raise AppError("رمز فعلی نادرست است")
    with connect() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_pw(new_password), user["id"]))
        clear_initial_secret(conn, user)
    return jsonify(ok=True)


@app.post("/api/auth/forgot")
def forgot():
    payload = body_json()
    ident = str(payload.get("ident") or "").strip()
    with connect() as conn:
        user = find_user(conn, ident)
        if not user:
            raise AppError("کاربری با این مشخصات پیدا نشد")
        settings = get_settings(conn)
        if "@" in ident:
            if not user["email"]:
                raise AppError("برای این حساب جیمیل ثبت نشده")
            send_gmail_code(conn, settings, user["email"], user["id"], "reset")
            status, detail, channel = "sent", "جیمیل", "email"
            code = None
        else:
            code = store_code(conn, user["id"], "sms")
            text = f"کد بازیابی رمز دفترچی: {code}\nاین کد تا ۱۰ دقیقه معتبر است."
            status, detail = deliver_sms(conn, settings, user["phone"], text)
            channel = "sms"
    external = status == "sent"
    return jsonify(ok=True, delivery=channel if external else "internal", preview_code=None if external else code, detail=detail)


@app.post("/api/auth/reset")
def reset_password():
    payload = body_json()
    ident = str(payload.get("ident") or "")
    code = str(payload.get("code") or "").translate(DIGITS).strip()
    new_password = str(payload.get("password") or "")
    if not re.fullmatch(r"\d{6}", code):
        raise AppError("کد باید ۶ رقم باشد")
    if len(new_password) < 6 or len(new_password) > 100:
        raise AppError("رمز جدید باید حداقل ۶ حرف باشد")
    with connect() as conn:
        user = find_user(conn, ident)
        if not user:
            raise AppError("کاربری با این مشخصات پیدا نشد")
        row = conn.execute(
            "SELECT * FROM password_resets WHERE user_id=? AND used=0 AND channel IN ('email','sms') ORDER BY id DESC LIMIT 1",
            (user["id"],),
        ).fetchone()
        digest = hashlib.sha256(code.encode()).hexdigest()
        if not row or row["expires_at"] < iso() or not secrets.compare_digest(row["code_hash"], digest):
            raise AppError("کد نادرست یا منقضی است")
        conn.execute("UPDATE password_resets SET used=1 WHERE id=?", (row["id"],))
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_pw(new_password), user["id"]))
        clear_initial_secret(conn, user)
    return jsonify(ok=True)


@app.get("/api/users")
def list_users():
    require_admin()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return jsonify(users=[public_user(row) for row in rows])


@app.post("/api/users")
def create_user():
    require_admin()
    payload = body_json()
    name = clean_text(payload.get("name"), "نام", 80, required=True)
    phone = norm_phone(payload.get("phone") or "")
    email = clean_text(payload.get("email"), "ایمیل", 120).lower()
    password = str(payload.get("password") or "")
    role = payload.get("role") or "cashier"
    if not re.fullmatch(r"09\d{9}", phone):
        raise AppError("شماره موبایل کاربر معتبر نیست")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise AppError("ایمیل معتبر نیست")
    if role not in {"admin", "cashier"}:
        raise AppError("نقش کاربر نامعتبر است")
    if len(password) < 6:
        raise AppError("رمز حداقل ۶ حرف است")
    with connect() as conn:
        if conn.execute("SELECT 1 FROM users WHERE phone=?", (phone,)).fetchone():
            raise AppError("این شماره قبلاً ثبت شده")
        if email and conn.execute("SELECT 1 FROM users WHERE lower(email)=?", (email,)).fetchone():
            raise AppError("این ایمیل قبلاً ثبت شده")
        cur = conn.execute(
            "INSERT INTO users (name, phone, email, password_hash, role, email_verified, created_at) VALUES (?,?,?,?,?,?,?)",
            (name, phone, email or None, hash_pw(password), role, 1, iso()),
        )
        row = conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(user=public_user(row))


@app.get("/api/products")
def list_products():
    require_user()
    query = str(request.args.get("q") or "").strip()
    with connect() as conn:
        threshold = setting_int(get_settings(conn), "low_stock")
        if query:
            like = f"%{query}%"
            rows = conn.execute(
                """SELECT DISTINCT p.* FROM products p
                   LEFT JOIN product_variations v ON v.product_id=p.id AND v.active=1
                   WHERE p.active=1 AND (
                     p.name LIKE ? OR p.sku LIKE ? OR p.barcode LIKE ?
                     OR v.label LIKE ? OR v.sku LIKE ? OR v.barcode LIKE ?
                   )
                   ORDER BY p.name""",
                (like, like, like, like, like, like),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM products WHERE active=1 ORDER BY name").fetchall()
        products = present_products(conn, rows, threshold)
    return jsonify(products=products)


@app.post("/api/products")
def create_product():
    user = require_admin()
    payload = body_json()
    name = clean_text(payload.get("name"), "نام کالا", 120, required=True)
    price = parse_money(payload.get("price"), "قیمت")
    cost = parse_money(payload.get("cost"), "قیمت خرید", allow_empty=True)
    stock = parse_money(payload.get("stock"), "موجودی", allow_empty=True)
    sku = clean_code(payload.get("sku"), "کد")
    barcode = clean_code(payload.get("barcode"), "بارکد")
    tax_code = clean_tax_code(payload.get("tax_code"))
    image = clean_image(payload.get("image"))
    with connect() as conn:
        existing = match_product(conn, barcode, sku)
        if existing and existing["active"]:
            raise AppError("این بارکد یا کد قبلاً برای کالای دیگری ثبت شده")
        if existing:
            conn.execute(
                """UPDATE products SET name=?, sku=?, barcode=?, price=?, cost=?, stock=?, image=COALESCE(?, image),
                   tax_code=?, active=1, updated_at=? WHERE id=?""",
                (name, sku, barcode, price, cost, stock, image, tax_code, iso(), existing["id"]),
            )
            if price != existing["price"]:
                log_stock(conn, existing["id"], "price", 0, existing["price"], price, "بازگشت از بایگانی", user["id"])
            if stock != existing["stock"]:
                log_stock(conn, existing["id"], "adjust", stock - existing["stock"], existing["stock"], stock, "بازگشت از بایگانی", user["id"])
            product_id = existing["id"]
        else:
            cur = conn.execute(
                """INSERT INTO products (name, sku, barcode, price, cost, stock, image, tax_code, woo_id, active, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,NULL,1,?,?)""",
                (name, sku, barcode, price, cost, stock, image, tax_code, iso(), iso()),
            )
            product_id = cur.lastrowid
            if stock:
                log_stock(conn, product_id, "adjust", stock, 0, stock, "موجودی اولیه", user["id"])
        threshold = setting_int(get_settings(conn), "low_stock")
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        product = present_product(conn, row, threshold)
    return jsonify(product=product)


@app.patch("/api/products/<int:pid>")
def update_product(pid: int):
    user = require_admin()
    payload = body_json()
    with connect() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
        if not row:
            raise AppError("کالا پیدا نشد", 404)
        name = clean_text(payload["name"], "نام کالا", 120, True) if "name" in payload else row["name"]
        price = parse_money(payload["price"], "قیمت") if "price" in payload else row["price"]
        cost = parse_money(payload["cost"], "قیمت خرید", allow_empty=True) if "cost" in payload else row["cost"]
        stock = parse_money(payload["stock"], "موجودی", allow_empty=True) if "stock" in payload else row["stock"]
        sku = clean_code(payload["sku"], "کد") if "sku" in payload else row["sku"]
        barcode = clean_code(payload["barcode"], "بارکد") if "barcode" in payload else row["barcode"]
        tax_code = clean_tax_code(payload["tax_code"]) if "tax_code" in payload else row["tax_code"]
        image = clean_image(payload["image"]) if "image" in payload else row["image"]
        variable = product_kind(row) == "variable"
        if variable:
            price = row["price"]
            stock = row["stock"]
        conn.execute(
            """UPDATE products SET name=?, sku=?, barcode=?, price=?, cost=?, stock=?, image=?, tax_code=?, updated_at=? WHERE id=?""",
            (name, sku, barcode, price, cost, stock, image, tax_code, iso(), pid),
        )
        if not variable and price != row["price"]:
            log_stock(conn, pid, "price", 0, row["price"], price, "تغییر قیمت", user["id"])
        if not variable and stock != row["stock"]:
            log_stock(conn, pid, "adjust", stock - row["stock"], row["stock"], stock, "تعدیل موجودی", user["id"])
        if variable:
            variable_parent_stock(conn, pid)
        threshold = setting_int(get_settings(conn), "low_stock")
        updated = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        product = present_product(conn, updated, threshold)
    return jsonify(product=product)


@app.delete("/api/products/<int:pid>")
def archive_product(pid: int):
    require_admin()
    with connect() as conn:
        row = conn.execute("SELECT id FROM products WHERE id=? AND active=1", (pid,)).fetchone()
        if not row:
            raise AppError("کالا پیدا نشد", 404)
        conn.execute("UPDATE products SET active=0, updated_at=? WHERE id=?", (iso(), pid))
    return jsonify(ok=True)


@app.get("/api/products/template")
def product_template():
    require_user()
    book = Workbook()
    sheet = book.active
    sheet.title = "products"
    sheet.append(["نام کالا", "SKU", "موجودی", "قیمت فروش", "بارکد", "قیمت خرید", "تصویر", "شناسه مودیان"])
    sheet.append(["چای ۵۰۰ گرمی", "TEA-500", "6260000000011", 45000, 12, 30000, "", ""])
    buf = BytesIO()
    book.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name="daftarchi-products.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def read_product_sheet(upload):
    if not upload:
        raise AppError("فایل اکسل را انتخاب کنید")
    try:
        book = load_workbook(upload, data_only=True, read_only=True)
    except Exception:
        raise AppError("فایل اکسل خوانده نشد")
    try:
        sheet = book.active
        if sheet is None:
            raise AppError("فایل خالی است")
        rows = []
        for row in sheet.iter_rows(values_only=True):
            rows.append(tuple(row))
            if len(rows) > 5001:
                raise AppError("فایل بیشتر از ۵۰۰۰ کالا است")
    finally:
        book.close()
    if not rows:
        raise AppError("فایل خالی است")
    fields = [header_field(cell) for cell in rows[0]]
    if "name" not in fields or "price" not in fields:
        raise AppError("ستون نام و قیمت لازم است. سرستون می‌تواند نام کالا، SKU، موجودی و قیمت فروش باشد")
    parsed, errors = [], []
    for index, row in enumerate(rows[1:], start=2):
        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        data = {}
        for field, cell in zip(fields, row):
            if field and field not in data:
                data[field] = cell
        try:
            item = {
                "row": index,
                "name": clean_text(data.get("name"), "نام کالا", 180, required=True),
                "price": parse_money(data.get("price"), "قیمت"),
                "cost": parse_money(data.get("cost"), "قیمت خرید", allow_empty=True) if "cost" in fields else 0,
                "sku": clean_code(data.get("sku"), "کد") if "sku" in fields else None,
                "barcode": clean_code(data.get("barcode"), "بارکد") if "barcode" in fields else None,
                "image": clean_image(data.get("image")) if data.get("image") else None,
                "tax_code": clean_tax_code(data.get("tax_code")) if "tax_code" in fields else None,
                "stock": parse_money(data.get("stock"), "موجودی", allow_empty=True) if "stock" in fields and data.get("stock") not in (None, "") else None,
            }
            parsed.append(item)
        except AppError as exc:
            errors.append({"row": index, "error": str(exc)})
    return parsed, errors


def product_snapshot(row) -> dict:
    return {key: row[key] for key in row.keys()} if not isinstance(row, dict) else dict(row)


def signature_of(marks: dict):
    if marks["family"] not in FILTER_FAMILIES:
        return None
    if not (marks["inches"] or marks["microns"] or marks["codes"]):
        return None
    return (marks["family"], marks["inches"], marks["microns"], marks["codes"], marks["materials"], marks["roles"])


def remember_product(by_barcode, by_sku, by_name, item, by_sig):
    if item.get("barcode"):
        by_barcode[item["barcode"]] = item
    if item.get("sku"):
        by_sku[item["sku"]] = item
    key = name_key(item.get("name") or "")
    item["marks"] = product_marks(item.get("name") or "")
    sig = signature_of(item["marks"])
    if sig:
        bucket = by_sig.setdefault(sig, [])
        by_sig[sig] = [old for old in bucket if old["id"] != item["id"]]
        by_sig[sig].append(item)
    if not key:
        return
    bucket = by_name.setdefault(key, [])
    by_name[key] = [old for old in bucket if old["id"] != item["id"]]
    by_name[key].append(item)


def forget_product(by_barcode, by_sku, by_name, item, by_sig):
    if item.get("barcode") and by_barcode.get(item["barcode"], {}).get("id") == item["id"]:
        by_barcode.pop(item["barcode"], None)
    if item.get("sku") and by_sku.get(item["sku"], {}).get("id") == item["id"]:
        by_sku.pop(item["sku"], None)
    marks = item.get("marks") or product_marks(item.get("name") or "")
    sig = signature_of(marks)
    if sig and sig in by_sig:
        by_sig[sig] = [old for old in by_sig[sig] if old["id"] != item["id"]]
    key = name_key(item.get("name") or "")
    if key in by_name:
        by_name[key] = [old for old in by_name[key] if old["id"] != item["id"]]


def index_products(rows):
    by_barcode, by_sku, by_name, by_sig = {}, {}, {}, {}
    for row in rows:
        remember_product(by_barcode, by_sku, by_name, product_snapshot(row), by_sig)
    return by_barcode, by_sku, by_name, by_sig


def named_product(by_name, name, sku):
    matches = list(by_name.get(name_key(name)) or [])
    if not matches:
        return None
    if sku:
        for item in matches:
            if item.get("sku") == sku:
                return item
        blank = [item for item in matches if not item.get("sku")]
        return blank[0] if blank else None
    blank = [item for item in matches if not item.get("sku")]
    return (blank or matches)[0]


def fuzzy_product(by_sig, name, sku):
    sig = signature_of(product_marks(name))
    if not sig:
        return None
    found = []
    seen = set()
    for item in by_sig.get(sig) or []:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        if sku_blocks(sku, item.get("sku")):
            continue
        found.append(item)
    if len(found) == 1:
        return found[0]
    return None


def locate_import(by_barcode, by_sku, by_name, by_sig, item):
    found = by_barcode.get(item["barcode"]) if item.get("barcode") else None
    coded = by_sku.get(item["sku"]) if item.get("sku") else None
    if found and coded and found["id"] != coded["id"]:
        raise AppError("بارکد و کد به دو کالای متفاوت مربوط است")
    if found or coded:
        return found or coded
    named = named_product(by_name, item["name"], item.get("sku"))
    if named:
        return named
    return fuzzy_product(by_sig, item["name"], item.get("sku"))


def plan_product_import(conn, parsed):
    by_barcode, by_sku, by_name, by_sig = index_products(conn.execute("SELECT * FROM products").fetchall())
    creating = updating = 0
    errors = []
    temp_id = 0
    for item in parsed:
        try:
            existing = locate_import(by_barcode, by_sku, by_name, by_sig, item)
        except AppError as exc:
            errors.append({"row": item["row"], "error": str(exc)})
            continue
        if existing:
            updating += 1
            current = dict(existing)
            current["name"] = item["name"]
            current["sku"] = item["sku"] or existing.get("sku")
            current["barcode"] = item["barcode"] or existing.get("barcode")
            forget_product(by_barcode, by_sku, by_name, existing, by_sig)
            remember_product(by_barcode, by_sku, by_name, current, by_sig)
        else:
            creating += 1
            temp_id -= 1
            remember_product(by_barcode, by_sku, by_name, {
                "id": temp_id,
                "name": item["name"],
                "sku": item["sku"],
                "barcode": item["barcode"],
            }, by_sig)
    return creating, updating, errors


def save_imported_products(user, parsed):
    created, updated, errors, ids = 0, 0, [], []
    with connect() as conn:
        by_barcode, by_sku, by_name, by_sig = index_products(conn.execute("SELECT * FROM products").fetchall())
        for item in parsed:
            try:
                existing = locate_import(by_barcode, by_sku, by_name, by_sig, item)
                if existing and existing["id"] > 0:
                    new_stock = item["stock"] if item["stock"] is not None else existing["stock"]
                    conn.execute(
                        """UPDATE products SET name=?, sku=?, barcode=?, price=?, cost=?, stock=?, image=COALESCE(?, image),
                           tax_code=COALESCE(?, tax_code), active=1, updated_at=? WHERE id=?""",
                        (item["name"], item["sku"] or existing["sku"], item["barcode"] or existing["barcode"], item["price"], item["cost"], new_stock, item["image"], item["tax_code"], iso(), existing["id"]),
                    )
                    if item["price"] != existing["price"]:
                        log_stock(conn, existing["id"], "price", 0, existing["price"], item["price"], "ورود اکسل", user["id"])
                    if new_stock != existing["stock"]:
                        log_stock(conn, existing["id"], "adjust", new_stock - existing["stock"], existing["stock"], new_stock, "ورود اکسل", user["id"])
                    fresh = product_snapshot(conn.execute("SELECT * FROM products WHERE id=?", (existing["id"],)).fetchone())
                    forget_product(by_barcode, by_sku, by_name, existing, by_sig)
                    remember_product(by_barcode, by_sku, by_name, fresh, by_sig)
                    updated += 1
                    ids.append(existing["id"])
                else:
                    initial = item["stock"] or 0
                    cur = conn.execute(
                        """INSERT INTO products (name, sku, barcode, price, cost, stock, image, tax_code, woo_id, active, created_at, updated_at)
                           VALUES (?,?,?,?,?,?,?,?,NULL,1,?,?)""",
                        (item["name"], item["sku"], item["barcode"], item["price"], item["cost"], initial, item["image"], item["tax_code"], iso(), iso()),
                    )
                    if initial:
                        log_stock(conn, cur.lastrowid, "adjust", initial, 0, initial, "ورود اکسل", user["id"])
                    fresh = product_snapshot(conn.execute("SELECT * FROM products WHERE id=?", (cur.lastrowid,)).fetchone())
                    remember_product(by_barcode, by_sku, by_name, fresh, by_sig)
                    created += 1
                    ids.append(cur.lastrowid)
            except AppError as exc:
                errors.append({"row": item["row"], "error": str(exc)})
            except sqlite3.IntegrityError:
                errors.append({"row": item["row"], "error": "کد یا بارکد تکراری است"})
    return {"created": created, "updated": updated, "errors": errors, "ids": ids}


@app.post("/api/products/preview")
def preview_products():
    require_admin()
    parsed, errors = read_product_sheet(request.files.get("file"))
    with connect() as conn:
        creating, updating, plan_errors = plan_product_import(conn, parsed)
    errors = errors + plan_errors
    preview = [{
        "name": item["name"],
        "sku": item["sku"] or "",
        "stock": 0 if item["stock"] is None else item["stock"],
        "price": item["price"],
    } for item in parsed[:8]]
    return jsonify(total=len(parsed), preview=preview, errors=errors[:30], error_count=len(errors), creating=creating, updating=updating)


@app.post("/api/products/import")
def import_products():
    user = require_admin()
    parsed, errors = read_product_sheet(request.files.get("file"))
    saved = save_imported_products(user, parsed)
    saved["errors"] = (errors + saved["errors"])[:40]
    return jsonify(saved)


def fetch_woo_catalog(settings: dict) -> list[dict]:
    found = []
    page = 1
    while page <= 40:
        status, rows = woo_request(settings, "GET", "products", {"per_page": "100", "page": str(page)})
        if status >= 400 or not isinstance(rows, list):
            break
        found.extend(row for row in rows if isinstance(row, dict))
        if len(rows) < 100:
            break
        page += 1
    return found


def remote_product_id(remote: dict) -> int:
    try:
        return int(remote.get("id") or 0)
    except (TypeError, ValueError):
        return 0


def pick_remote_product(local, catalog: list[dict], used: set[int]) -> int | None:
    local_sku = str(local["sku"] or "").strip()
    same_sku = []
    open_hits = []
    for remote in catalog:
        rid = remote_product_id(remote)
        if not rid or rid in used:
            continue
        if str(remote.get("type") or "simple") not in {"simple", ""}:
            continue
        remote_sku = str(remote.get("sku") or "").strip()
        if local_sku and remote_sku == local_sku:
            same_sku.append(rid)
            continue
        if remote_sku or sku_blocks(local_sku, remote_sku):
            continue
        if goods_match(local["name"], remote.get("name") or ""):
            open_hits.append(rid)
    if len(same_sku) == 1:
        return same_sku[0]
    if same_sku or len(open_hits) != 1:
        return None
    return open_hits[0]


@app.post("/api/products/woo/push")
def woo_push():
    require_admin()
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids") if isinstance(payload, dict) else None
    with connect() as conn:
        settings = get_settings(conn)
        require_woo(settings)
        if ids:
            if not isinstance(ids, list) or not ids:
                raise AppError("فهرست کالا خالی است")
            marks = ",".join("?" for _ in ids)
            rows = conn.execute(f"SELECT * FROM products WHERE active=1 AND id IN ({marks})", [int(i) for i in ids]).fetchall()
        else:
            rows = conn.execute("SELECT * FROM products WHERE active=1 ORDER BY id").fetchall()
    skipped = 0
    pending = []
    update_pairs = []
    used = set()
    for row in rows:
        if product_kind(row) == "variable":
            skipped += 1
            continue
        if row["woo_id"]:
            try:
                used.add(int(row["woo_id"]))
            except (TypeError, ValueError):
                pass
            item = woo_item(row)
            item["id"] = row["woo_id"]
            update_pairs.append((row["id"], item))
        else:
            pending.append(row)
    catalog = None
    if pending:
        try:
            catalog = fetch_woo_catalog(settings)
        except AppError:
            catalog = None
    create_pairs = []
    for row in pending:
        item = woo_item(row)
        rid = pick_remote_product(row, catalog, used) if catalog is not None else None
        if rid:
            used.add(rid)
            item["id"] = rid
            update_pairs.append((row["id"], item))
        else:
            create_pairs.append((row["id"], item))
    created = updated = 0
    failed = []
    progress = {"consecutive": 0, "stop": False}

    def send(kind: str, pairs: list):
        nonlocal created, updated
        for offset in range(0, len(pairs), WOO_BATCH):
            if progress["stop"]:
                return
            chunk = pairs[offset:offset + WOO_BATCH]
            body = {kind: [item for _pid, item in chunk]}
            try:
                _status, response = woo_request(settings, "POST", "products/batch", payload=body)
                if not isinstance(response, dict) or not isinstance(response.get(kind), list):
                    message = response.get("message") if isinstance(response, dict) else "پاسخ نامعتبر"
                    raise AppError(f"ووکامرس خطا داد: {message}", 502)
            except AppError as exc:
                progress["consecutive"] += 1
                for _pid, item in chunk:
                    failed.append({"name": item.get("name"), "error": str(exc)})
                if progress["consecutive"] >= 3:
                    progress["stop"] = True
                continue
            progress["consecutive"] = 0
            with connect() as conn:
                for (pid, item), result in zip(chunk, response[kind]):
                    if isinstance(result, dict) and result.get("id") and "error" not in result:
                        conn.execute("UPDATE products SET woo_id=?, updated_at=? WHERE id=?", (result["id"], iso(), pid))
                        if kind == "create":
                            created += 1
                        else:
                            updated += 1
                    else:
                        failed.append({"name": item.get("name"), "error": str(result)[:180]})

    if update_pairs:
        send("update", update_pairs)
    if create_pairs:
        send("create", create_pairs)
    return jsonify(created=created, updated=updated, failed=failed, skipped=skipped)


def remote_image(remote: dict) -> str:
    images = remote.get("images") or []
    src = ""
    if images and isinstance(images[0], dict):
        src = str(images[0].get("src") or "")
    elif isinstance(remote.get("image"), dict):
        src = str(remote["image"].get("src") or "")
    return src[:400]


def attribute_title(raw: dict, parents: list) -> str:
    name = str(raw.get("name") or "").strip()
    try:
        attr_id = int(raw.get("id") or 0)
    except (TypeError, ValueError):
        attr_id = 0
    if attr_id:
        for parent in parents:
            if not isinstance(parent, dict):
                continue
            try:
                parent_id = int(parent.get("id") or 0)
            except (TypeError, ValueError):
                parent_id = 0
            parent_name = str(parent.get("name") or "").strip()
            if parent_id == attr_id and parent_name:
                name = parent_name
                break
    if name.lower().startswith("pa_"):
        name = name[3:]
    return name.replace("_", " ").replace("-", " ").strip()


def describe_variation(remote: dict, parents: list) -> tuple[str, list[dict]]:
    parts = []
    attributes = []
    for raw in remote.get("attributes") or []:
        if not isinstance(raw, dict):
            continue
        option = raw.get("option")
        if isinstance(option, list):
            option = "، ".join(str(item).strip() for item in option if str(item).strip())
        option = str(option or "").strip()
        name = attribute_title(raw, parents)
        if not name and not option:
            continue
        attributes.append({"name": name, "option": option})
        parts.append(f"{name}: {option}" if name and option else (option or name))
    label = " · ".join(parts)[:200] or "بدون نوع"
    return label, attributes


def variation_numbers(remote: dict) -> tuple[int | None, int]:
    status = str(remote.get("stock_status") or "instock")
    if remote.get("manage_stock"):
        raw = remote.get("stock_quantity")
        stock = parse_money(raw, "موجودی", allow_empty=True) if raw is not None else 0
        return stock, 1 if stock else 0
    return None, 0 if status == "outofstock" else 1


def fetch_woo_variations(settings: dict, woo_id: int) -> list[dict]:
    found = []
    page = 1
    while page <= 20:
        _status, rows = woo_request(
            settings, "GET", f"products/{int(woo_id)}/variations", {"per_page": "100", "page": str(page)},
        )
        if not isinstance(rows, list):
            raise AppError("پاسخ متغیرهای ووکامرس نامعتبر است", 502)
        found.extend(row for row in rows if isinstance(row, dict))
        if len(rows) < 100:
            break
        page += 1
    return found


def store_variation(conn, product_id: int, remote: dict, parents: list):
    if str(remote.get("status") or "publish") not in {"publish", ""}:
        return None
    try:
        woo_id = int(remote.get("id") or 0)
    except (TypeError, ValueError):
        return None
    if not woo_id:
        return None
    label, attributes = describe_variation(remote, parents)
    try:
        price = parse_money(remote.get("price") or remote.get("regular_price") or 0, "قیمت", allow_empty=True)
        stock, in_stock = variation_numbers(remote)
    except AppError:
        return None
    sku = clean_code(remote.get("sku"), "کد")
    barcode = remote_barcode(remote)
    image = remote_image(remote) or None
    payload = json.dumps(attributes, ensure_ascii=False)
    existing = conn.execute("SELECT * FROM product_variations WHERE woo_id=?", (woo_id,)).fetchone()
    if existing:
        conn.execute(
            """UPDATE product_variations
               SET product_id=?, sku=?, barcode=?, price=?, stock=?, in_stock=?, label=?, attributes=?, image=?, active=1
               WHERE id=?""",
            (product_id, sku, barcode, price, stock, in_stock, label, payload, image, existing["id"]),
        )
        return woo_id
    conn.execute(
        """INSERT INTO product_variations
           (product_id, woo_id, sku, barcode, price, stock, in_stock, label, attributes, image, active)
           VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
        (product_id, woo_id, sku, barcode, price, stock, in_stock, label, payload, image),
    )
    return woo_id


def find_unlinked_product(conn, name: str, remote_sku: str | None):
    key = name_key(name)
    wanted = product_marks(name)
    rows = conn.execute("SELECT * FROM products WHERE active=1 AND woo_id IS NULL").fetchall()
    exact, fuzzy = [], []
    for item in rows:
        if sku_blocks(remote_sku, item["sku"]):
            continue
        if key and name_key(item["name"]) == key:
            exact.append(item)
        elif marks_match(wanted, product_marks(item["name"])):
            fuzzy.append(item)
    if len(exact) == 1:
        return exact[0]
    if exact or len(fuzzy) != 1:
        return None
    return fuzzy[0]


def linked_from_index(index, name: str, remote_sku: str | None):
    by_name, by_sig = index
    key = name_key(name)
    exact = []
    if key:
        for item in by_name.get(key) or []:
            if not sku_blocks(remote_sku, item.get("sku")):
                exact.append(item)
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    return fuzzy_product(by_sig, name, remote_sku)


def store_remote_product(conn, remote: dict, variations: list[dict] | None, user_id: int, index=None) -> str:
    sku = str(remote.get("sku") or "").strip() or None
    barcode = remote_barcode(remote)
    row = conn.execute("SELECT * FROM products WHERE woo_id=?", (remote.get("id"),)).fetchone()
    if not row and sku:
        row = conn.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
    if not row and remote.get("name"):
        row = linked_from_index(index, remote["name"], sku) if index else find_unlinked_product(conn, remote["name"], sku)
    image = remote_image(remote)
    kind = "variable" if variations is not None else "simple"
    try:
        price_source = remote.get("regular_price") or remote.get("price") or 0
        price = parse_money(price_source, "قیمت", allow_empty=True)
    except AppError:
        return "skipped"
    if kind == "simple":
        raw_stock = remote.get("stock_quantity")
        stock = parse_money(raw_stock, "موجودی", allow_empty=True) if raw_stock is not None else 0
    else:
        stock = 0
    if row:
        conn.execute(
            """UPDATE products SET name=?, sku=COALESCE(?, sku), barcode=COALESCE(?, barcode), price=?, stock=?,
               image=COALESCE(?, image), woo_id=?, product_type=?, active=1, updated_at=? WHERE id=?""",
            (remote["name"], sku, barcode, price, stock, image or None, remote.get("id"), kind, iso(), row["id"]),
        )
        product_id = row["id"]
        state = "updated"
    else:
        cur = conn.execute(
            """INSERT INTO products
               (name, sku, barcode, price, cost, stock, image, woo_id, product_type, active, created_at, updated_at)
               VALUES (?,?,?,?,0,?,?,?,?,1,?,?)""",
            (remote["name"], sku, barcode, price, stock, image or None, remote.get("id"), kind, iso(), iso()),
        )
        product_id = cur.lastrowid
        state = "imported"
    if index and row is not None and not row["woo_id"]:
        snap = row if isinstance(row, dict) else product_snapshot(row)
        forget_product({}, {}, index[0], snap, index[1])
    if kind == "variable":
        seen = []
        parents = [item for item in (remote.get("attributes") or []) if isinstance(item, dict)]
        for item in variations or []:
            woo_id = store_variation(conn, product_id, item, parents)
            if woo_id:
                seen.append(woo_id)
        if seen:
            marks = ",".join("?" for _ in seen)
            conn.execute(
                f"UPDATE product_variations SET active=0 WHERE product_id=? AND (woo_id IS NULL OR woo_id NOT IN ({marks}))",
                [product_id, *seen],
            )
        else:
            conn.execute("UPDATE product_variations SET active=0 WHERE product_id=?", (product_id,))
        new_stock = variable_parent_stock(conn, product_id)
        if row and new_stock != row["stock"]:
            log_stock(conn, product_id, "adjust", new_stock - int(row["stock"]), int(row["stock"]), new_stock, "دریافت ووکامرس", user_id)
        elif not row and new_stock:
            log_stock(conn, product_id, "adjust", new_stock, 0, new_stock, "دریافت ووکامرس", user_id)
        return state
    conn.execute("UPDATE product_variations SET active=0 WHERE product_id=?", (product_id,))
    if row:
        if price != row["price"]:
            log_stock(conn, product_id, "price", 0, row["price"], price, "دریافت ووکامرس", user_id)
        if stock != row["stock"]:
            log_stock(conn, product_id, "adjust", stock - row["stock"], row["stock"], stock, "دریافت ووکامرس", user_id)
    elif stock:
        log_stock(conn, product_id, "adjust", stock, 0, stock, "دریافت ووکامرس", user_id)
    return state


@app.post("/api/products/woo/pull")
def woo_pull():
    user = require_admin()
    with connect() as conn:
        settings = get_settings(conn)
        require_woo(settings)
    imported = updated = 0
    page = 1
    while page <= 40:
        _status, remote_rows = woo_request(settings, "GET", "products", {"per_page": "50", "page": str(page)})
        if not isinstance(remote_rows, list) or not remote_rows:
            break
        prepared = []
        for remote in remote_rows:
            if not isinstance(remote, dict) or not remote.get("name"):
                continue
            if str(remote.get("type") or "simple") == "variation":
                continue
            variations = None
            if str(remote.get("type") or "") == "variable":
                variations = fetch_woo_variations(settings, int(remote["id"]))
            prepared.append((remote, variations))
        with connect() as conn:
            index = index_products(conn.execute("SELECT * FROM products WHERE active=1 AND woo_id IS NULL").fetchall())
            unlinked = (index[2], index[3])
            for remote, variations in prepared:
                state = store_remote_product(conn, remote, variations, user["id"], unlinked)
                if state == "imported":
                    imported += 1
                elif state == "updated":
                    updated += 1
        if len(remote_rows) < 50:
            break
        page += 1
    return jsonify(imported=imported, updated=updated)


@app.post("/api/upload")
def upload_image():
    require_admin()
    upload = request.files.get("file")
    if not upload:
        raise AppError("فایل تصویر را انتخاب کنید")
    blob = upload.read()
    if len(blob) > 2 * 1024 * 1024:
        raise AppError("حجم تصویر باید کمتر از ۲ مگابایت باشد")
    ext = sniff_image(blob)
    if not ext:
        raise AppError("فرمت تصویر باید jpg، png، webp یا gif باشد")
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD / name).write_bytes(blob)
    return jsonify(url=f"/uploads/{name}")


def sniff_image(blob: bytes) -> str | None:
    if blob.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if blob.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if blob.startswith(b"RIFF") and blob[8:12] == b"WEBP":
        return ".webp"
    return None


@app.get("/api/inventory")
def inventory():
    require_admin()
    with connect() as conn:
        threshold = setting_int(get_settings(conn), "low_stock")
        products = conn.execute("SELECT * FROM products WHERE active=1 ORDER BY stock ASC, name").fetchall()
        logs = conn.execute(
            """SELECT l.*, p.name AS product_name FROM inventory_logs l
               JOIN products p ON p.id = l.product_id ORDER BY l.id DESC LIMIT 40"""
        ).fetchall()
        pay = conn.execute("SELECT id, code, name FROM accounts WHERE code IN ('1000','1010','2000') ORDER BY code").fetchall()
        listed = present_products(conn, products, threshold)
    return jsonify(
        products=listed,
        logs=[{**dict(row), "at_jalali": to_jalali(row["created_at"])} for row in logs],
        pay_accounts=[dict(row) for row in pay],
    )


def stock_target(payload) -> tuple[int, int]:
    raw = str(payload.get("product_id") or "")
    variation_raw = payload.get("variation_id")
    if ":" in raw:
        left, right = raw.split(":", 1)
        raw = left
        variation_raw = right
    try:
        pid = int(raw or 0)
        variation_id = int(variation_raw or 0)
    except (TypeError, ValueError):
        raise AppError("کالا نامعتبر است")
    return pid, variation_id


@app.post("/api/inventory/adjust")
def adjust_inventory():
    user = require_admin()
    payload = body_json()
    pid, variation_id = stock_target(payload)
    stock = parse_money(payload.get("stock"), "موجودی", allow_empty=True)
    note = clean_text(payload.get("note"), "شرح", 120) or "تعدیل موجودی"
    with connect() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
        if not row:
            raise AppError("کالا پیدا نشد", 404)
        if product_kind(row) == "variable":
            if not variation_id:
                raise AppError("موجودی کالای متغیر را روی همان متغیر ثبت کنید")
            var = conn.execute(
                "SELECT * FROM product_variations WHERE id=? AND product_id=? AND active=1",
                (variation_id, pid),
            ).fetchone()
            if not var:
                raise AppError("این متغیر پیدا نشد", 404)
            old = int(var["stock"] or 0)
            conn.execute(
                "UPDATE product_variations SET stock=?, in_stock=? WHERE id=?",
                (stock, 1 if stock else 0, var["id"]),
            )
            variable_parent_stock(conn, pid)
            log_stock(conn, pid, "adjust", stock - old, old, stock, f"{note} · {var['label']}", user["id"])
        else:
            conn.execute("UPDATE products SET stock=?, updated_at=? WHERE id=?", (stock, iso(), pid))
            log_stock(conn, pid, "adjust", stock - row["stock"], row["stock"], stock, note, user["id"])
    return jsonify(ok=True)


@app.post("/api/purchases")
def create_purchase():
    user = require_admin()
    payload = body_json()
    pid, variation_id = stock_target(payload)
    qty = parse_qty(payload.get("qty"))
    unit_cost = parse_money(payload.get("unit_cost"), "فی خرید", allow_empty=True)
    pay_code = str(payload.get("pay_code") or "1000")
    if pay_code not in {"1000", "1010", "2000"}:
        raise AppError("حساب پرداخت نامعتبر است")
    total = qty * unit_cost
    with connect() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
        if not row:
            raise AppError("کالا پیدا نشد", 404)
        sess = open_session(conn)
        if pay_code == "1000" and not sess:
            raise AppError("برای پرداخت نقدی، اول صندوق را باز کنید")
        session_id = sess["id"] if sess and pay_code == "1000" else None
        if product_kind(row) == "variable":
            if not variation_id:
                raise AppError("خرید کالای متغیر را روی همان متغیر ثبت کنید")
            var = conn.execute(
                "SELECT * FROM product_variations WHERE id=? AND product_id=? AND active=1",
                (variation_id, pid),
            ).fetchone()
            if not var:
                raise AppError("این متغیر پیدا نشد", 404)
            if var["stock"] is None:
                raise AppError("این متغیر در ووکامرس موجودی عددی ندارد. اول آنجا موجودی را روشن کنید و دوباره دریافت کنید.")
            old = int(var["stock"])
            new_stock = old + qty
            conn.execute(
                "UPDATE product_variations SET stock=?, in_stock=? WHERE id=?",
                (new_stock, 1 if new_stock else 0, var["id"]),
            )
            variable_parent_stock(conn, pid)
            note_name = f"{row['name']} — {var['label']}"
            log_stock(conn, pid, "purchase", qty, old, new_stock, f"خرید با فی {unit_cost} · {var['label']}", user["id"])
        else:
            new_stock = int(row["stock"]) + qty
            note_name = row["name"]
            log_stock(conn, pid, "purchase", qty, row["stock"], new_stock, f"خرید با فی {unit_cost}", user["id"])
            conn.execute("UPDATE products SET stock=?, updated_at=? WHERE id=?", (new_stock, iso(), pid))
        new_cost = moving_avg(int(row["stock"]), int(row["cost"]), qty, unit_cost)
        conn.execute("UPDATE products SET cost=?, updated_at=? WHERE id=?", (new_cost, iso(), pid))
        pay = acc(conn, pay_code)
        cur = conn.execute(
            """INSERT INTO purchases (product_id, qty, unit_cost, total, pay_account_id, session_id, user_id, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (pid, qty, unit_cost, total, pay["id"], session_id, user["id"], iso()),
        )
        if total:
            post_entry(
                conn,
                f"خرید {note_name}",
                [(acc(conn, "1200")["id"], total, 0), (pay["id"], 0, total)],
                "purchase",
                cur.lastrowid,
                user["id"],
            )
    return jsonify(ok=True, total=total)


@app.post("/api/sales")
def create_sale():
    user = require_user()
    payload = body_json()
    method = payload.get("payment_method") or "cash"
    if method not in {"cash", "card", "gateway", "credit"}:
        raise AppError("روش پرداخت نامعتبر است")
    dtype = payload.get("discount_type") or "amount"
    pos_ref = clean_text(payload.get("pos_ref"), "پیگیری", 64)
    alerts = []
    with connect() as conn:
        require_access(conn)
        sess = require_open(conn) if method != "gateway" else open_session(conn)
        if method != "gateway" and not sess:
            raise AppError("صندوق بسته است. از صفحه صندوق آن را باز کنید.")
        items, subtotal = load_cart(conn, payload.get("items"))
        discount = calc_discount(subtotal, dtype, payload.get("discount_value"))
        customer = walk_in_customer(conn, payload, method == "credit")
        if method == "gateway" and (subtotal - discount) < 1000:
            raise AppError("حداقل مبلغ درگاه ۱۰۰۰ تومان است")
        sale_id = insert_sale(
            conn, user["id"], customer, items, subtotal, discount, method, pos_ref,
            sess["id"] if sess and method != "gateway" else None,
        )
        settings = get_settings(conn)
        if method != "gateway":
            alerts = finalize_sale(conn, sale_id, user["id"])
        else:
            conn.execute("UPDATE sales SET gateway=? WHERE id=?", (settings.get("gateway") or "zarinpal", sale_id))
        result = sale_payload(conn, sale_id)
        payable = result["sale"]["payable"]
        phone = result["sale"]["customer_phone"]
    if method == "gateway":
        try:
            ref, pay_url = gateway_request(settings, sale_id, payable, phone)
        except Exception:
            with connect() as conn:
                conn.execute("UPDATE sales SET status='canceled' WHERE id=? AND status='pending'", (sale_id,))
            raise
        with connect() as conn:
            conn.execute("UPDATE sales SET gateway_ref=?, pay_url=? WHERE id=?", (ref, pay_url, sale_id))
            result = sale_payload(conn, sale_id)
        return jsonify(**result)
    if settings.get("sms_on_sale") == "1":
        notify_manager(settings, f"دفترچی: فروش {payable:,} تومان، فاکتور {sale_id}")
    if alerts and settings.get("sms_low_stock") == "1":
        notify_manager(settings, "دفترچی: موجودی کم شد: " + "، ".join(alerts))
    maybe_send_moadian(sale_id)
    with connect() as conn:
        result = sale_payload(conn, sale_id)
    result["sms"] = notify_buyer(result["sale"])
    return jsonify(**result)


@app.get("/api/sales")
def list_sales():
    require_user()
    status = request.args.get("status")
    try:
        limit = min(int(request.args.get("limit") or 50), 200)
    except ValueError:
        limit = 50
    with connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM sales WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM sales WHERE status='paid' ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        sales = []
        for row in rows:
            item = dict(row)
            item["at_jalali"] = to_jalali(row["created_at"])
            sales.append(item)
    return jsonify(sales=sales)


@app.post("/api/sales/<int:sale_id>/confirm")
def confirm_sale(sale_id: int):
    user = require_user()
    payload = body_json()
    mode = payload.get("mode") or "verify"
    with connect() as conn:
        sale = conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        if not sale:
            raise AppError("فاکتور پیدا نشد", 404)
        if sale["status"] == "paid":
            return jsonify(**sale_payload(conn, sale_id))
        if sale["status"] != "pending":
            raise AppError("این فاکتور قابل تأیید نیست")
        settings = get_settings(conn)
    ref = sale["gateway_ref"]
    if mode == "manual":
        ref = clean_text(payload.get("ref"), "پیگیری", 64)
        if len(ref) < 3:
            raise AppError("شماره پیگیری را وارد کنید")
    else:
        ref = gateway_verify(settings, sale)
    with connect() as conn:
        current = conn.execute("SELECT status FROM sales WHERE id=?", (sale_id,)).fetchone()
        if current["status"] == "paid":
            return jsonify(**sale_payload(conn, sale_id))
        alerts = finalize_sale(conn, sale_id, user["id"])
        conn.execute("UPDATE sales SET gateway_ref=?, pos_ref=? WHERE id=?", (ref, ref, sale_id))
        result = sale_payload(conn, sale_id)
        settings = get_settings(conn)
    if settings.get("sms_on_sale") == "1":
        notify_manager(settings, f"دفترچی: فروش درگاهی {result['sale']['payable']:,} تومان، فاکتور {sale_id}")
    if alerts and settings.get("sms_low_stock") == "1":
        notify_manager(settings, "دفترچی: موجودی کم شد: " + "، ".join(alerts))
    maybe_send_moadian(sale_id)
    with connect() as conn:
        result = sale_payload(conn, sale_id)
    result["sms"] = notify_buyer(result["sale"])
    return jsonify(**result)


@app.post("/api/sales/<int:sale_id>/cancel")
def cancel_sale(sale_id: int):
    require_user()
    with connect() as conn:
        sale = conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        if not sale:
            raise AppError("فاکتور پیدا نشد", 404)
        if sale["status"] != "pending":
            raise AppError("فقط پیش‌فاکتور باز را می‌توان لغو کرد")
        conn.execute("UPDATE sales SET status='canceled' WHERE id=?", (sale_id,))
    return jsonify(ok=True)


@app.post("/api/pos/prepare")
def pos_prepare():
    require_user()
    with connect() as conn:
        settings = get_settings(conn)
    host = (settings.get("pos_host") or "").strip()
    if not host:
        return jsonify(ok=True, mode="manual", message="کارت‌خوان تنظیم نشده؛ پرداخت کارت به‌صورت دستی و با شماره پیگیری ثبت می‌شود.")
    try:
        port = int(str(settings.get("pos_port") or "0").translate(DIGITS))
        with socket.create_connection((host, port), timeout=4):
            pass
    except Exception as exc:
        return jsonify(ok=False, mode="network", message=f"کارت‌خوان پاسخ نداد: {exc}")
    provider = settings.get("pos_provider") or "manual"
    return jsonify(ok=True, mode="network", message=f"ارتباط با کارت‌خوان ({provider}) برقرار شد. شماره پیگیری رسید را وارد کنید.")


@app.get("/api/reports/summary")
def reports():
    require_user()
    with connect() as conn:
        data = {kind: summary_for(conn, kind) for kind in ("day", "week", "month")}
    return jsonify(**data)


@app.get("/api/accounts")
def list_accounts():
    require_admin()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM accounts WHERE active=1 ORDER BY code").fetchall()
        items = []
        debit_total = credit_total = 0
        for row in rows:
            sums = conn.execute(
                "SELECT COALESCE(SUM(debit),0) AS d, COALESCE(SUM(credit),0) AS c FROM journal_lines WHERE account_id=?",
                (row["id"],),
            ).fetchone()
            signed = int(sums["d"]) - int(sums["c"])
            side, amount = side_of(signed)
            debit_col = signed if signed > 0 else 0
            credit_col = -signed if signed < 0 else 0
            debit_total += debit_col
            credit_total += credit_col
            items.append({
                "id": row["id"], "code": row["code"], "name": row["name"], "type": row["type"],
                "system": row["system"], "side": side, "amount": amount,
                "debit_col": debit_col, "credit_col": credit_col,
            })
    return jsonify(accounts=items, balanced=debit_total == credit_total, debit_total=debit_total, credit_total=credit_total)


@app.post("/api/accounts")
def create_account():
    user = require_admin()
    payload = body_json()
    name = clean_text(payload.get("name"), "نام حساب", 80, required=True)
    kind = payload.get("type") or "person"
    if kind not in {"asset", "liability", "equity", "income", "expense", "person"}:
        raise AppError("نوع حساب نامعتبر است")
    opening = parse_money(payload.get("opening"), "مانده اول", allow_empty=True)
    opening_side = payload.get("opening_side") or "debit"
    with connect() as conn:
        if kind == "person":
            account_id = create_person_account(conn, name)
        else:
            cur = conn.execute(
                "INSERT INTO accounts (code, name, type, system, active, created_at) VALUES (NULL,?,?,0,1,?)",
                (name, kind, iso()),
            )
            account_id = cur.lastrowid
            conn.execute("UPDATE accounts SET code=? WHERE id=?", (f"A{account_id:04d}", account_id))
        if opening:
            if opening_side == "credit":
                lines = [(acc(conn, "3000")["id"], opening, 0), (account_id, 0, opening)]
            else:
                lines = [(account_id, opening, 0), (acc(conn, "3000")["id"], 0, opening)]
            post_entry(conn, f"مانده اول {name}", lines, "opening", account_id, user["id"])
    return jsonify(ok=True, id=account_id)


@app.post("/api/journal")
def manual_journal():
    user = require_admin()
    payload = body_json()
    memo = clean_text(payload.get("memo"), "شرح", 160, required=True)
    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list) or len(raw_lines) < 2:
        raise AppError("حداقل دو ردیف سند لازم است")
    lines = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            raise AppError("ردیف سند نامعتبر است")
        try:
            account_id = int(raw.get("account_id") or 0)
        except (TypeError, ValueError):
            raise AppError("حساب نامعتبر است")
        debit = parse_money(raw.get("debit"), "بدهکار", allow_empty=True)
        credit = parse_money(raw.get("credit"), "بستانکار", allow_empty=True)
        if debit and credit:
            raise AppError("یک ردیف نمی‌تواند هم بدهکار و هم بستانکار باشد")
        if debit or credit:
            lines.append((account_id, debit, credit))
    with connect() as conn:
        known = {row["id"] for row in conn.execute("SELECT id FROM accounts WHERE active=1")}
        for account_id, _d, _c in lines:
            if account_id not in known:
                raise AppError("حساب پیدا نشد")
        post_entry(conn, memo, lines, "manual", None, user["id"])
    return jsonify(ok=True)


@app.get("/api/journal")
def list_journal():
    require_admin()
    account_filter = request.args.get("account_id")
    with connect() as conn:
        if account_filter:
            entries = conn.execute(
                """SELECT DISTINCT e.* FROM journal_entries e
                   JOIN journal_lines l ON l.entry_id=e.id
                   WHERE l.account_id=? ORDER BY e.id DESC LIMIT 80""",
                (int(account_filter),),
            ).fetchall()
        else:
            entries = conn.execute("SELECT * FROM journal_entries ORDER BY id DESC LIMIT 80").fetchall()
        result = []
        for entry in entries:
            lines = conn.execute(
                """SELECT l.debit, l.credit, a.name, a.code FROM journal_lines l
                   JOIN accounts a ON a.id=l.account_id WHERE l.entry_id=? ORDER BY l.id""",
                (entry["id"],),
            ).fetchall()
            result.append({
                "id": entry["id"],
                "memo": entry["memo"],
                "source": entry["source"],
                "at_jalali": to_jalali(entry["created_at"]),
                "lines": [dict(line) for line in lines],
            })
    return jsonify(entries=result)


@app.get("/api/register")
def get_register():
    require_user()
    with connect() as conn:
        sess = open_session(conn)
        book = account_balance(conn, acc(conn, "1000")["id"])
        history_rows = conn.execute(
            "SELECT * FROM register_sessions WHERE status='closed' ORDER BY id DESC LIMIT 12"
        ).fetchall()
        history = [public_session(conn, row) for row in history_rows]
        current = public_session(conn, sess) if sess else None
    return jsonify(open=current is not None, session=current, suggested_opening=book, history=history)


@app.post("/api/register/open")
def register_open():
    user = require_user()
    payload = body_json()
    opening = parse_money(payload.get("opening_cash"), "موجودی اول صندوق", allow_empty=True)
    with connect() as conn:
        if open_session(conn):
            raise AppError("صندوق همین حالا باز است")
        cur = conn.execute(
            """INSERT INTO register_sessions (opened_at, closed_at, opening_cash, counted_cash, status, opened_by, closed_by)
               VALUES (?, NULL, ?, NULL, 'open', ?, NULL)""",
            (iso(), opening, user["id"]),
        )
        session_id = cur.lastrowid
        book = account_balance(conn, acc(conn, "1000")["id"])
        delta = opening - book
        if delta > 0:
            post_entry(
                conn, "موجودی اول صندوق",
                [(acc(conn, "1000")["id"], delta, 0), (acc(conn, "3000")["id"], 0, delta)],
                "register_open", session_id, user["id"],
            )
        elif delta < 0:
            post_entry(
                conn, "برداشت از صندوق هنگام باز کردن",
                [(acc(conn, "3000")["id"], -delta, 0), (acc(conn, "1000")["id"], 0, -delta)],
                "register_open", session_id, user["id"],
            )
        sess = conn.execute("SELECT * FROM register_sessions WHERE id=?", (session_id,)).fetchone()
        data = public_session(conn, sess)
    return jsonify(ok=True, session=data)


@app.post("/api/register/close")
def register_close():
    user = require_user()
    payload = body_json()
    counted = parse_money(payload.get("counted_cash"), "شمارش صندوق", allow_empty=True)
    with connect() as conn:
        sess = open_session(conn)
        if not sess:
            raise AppError("صندوق باز نیست")
        figures = session_figures(conn, sess)
        book = account_balance(conn, acc(conn, "1000")["id"])
        delta = counted - book
        if delta > 0:
            post_entry(
                conn, f"اضافه صندوق نوبت {sess['id']}",
                [(acc(conn, "1000")["id"], delta, 0), (acc(conn, "5100")["id"], 0, delta)],
                "register_close", sess["id"], user["id"],
            )
        elif delta < 0:
            post_entry(
                conn, f"کسری صندوق نوبت {sess['id']}",
                [(acc(conn, "5100")["id"], -delta, 0), (acc(conn, "1000")["id"], 0, -delta)],
                "register_close", sess["id"], user["id"],
            )
        conn.execute(
            "UPDATE register_sessions SET status='closed', closed_at=?, counted_cash=?, closed_by=? WHERE id=?",
            (iso(), counted, user["id"], sess["id"]),
        )
        settings = get_settings(conn)
        diff = counted - figures["expected_cash"]
    if settings.get("sms_on_close") == "1":
        notify_manager(
            settings,
            f"دفترچی: صندوق بسته شد. نقد {figures['cash_sales']:,} کارت {figures['card_sales']:,} اختلاف {diff:,} تومان",
        )
    return jsonify(ok=True, difference=diff, expected_cash=figures["expected_cash"], counted_cash=counted)


@app.get("/api/customers")
def list_customers():
    require_user()
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.*,
                 COALESCE((SELECT SUM(debit)-SUM(credit) FROM journal_lines WHERE account_id=c.account_id), 0) AS balance,
                 (SELECT COUNT(*) FROM sales s WHERE s.customer_id=c.id AND s.status='paid') AS purchases
               FROM customers c ORDER BY c.id DESC"""
        ).fetchall()
    customers = []
    for row in rows:
        item = dict(row)
        item["balance"] = int(item["balance"] or 0)
        side, amount = side_of(item["balance"])
        item["side"] = side
        item["amount"] = amount
        customers.append(item)
    return jsonify(customers=customers)


@app.post("/api/receipts")
def create_receipt():
    user = require_admin()
    payload = body_json()
    try:
        account_id = int(payload.get("account_id") or 0)
    except (TypeError, ValueError):
        raise AppError("حساب نامعتبر است")
    amount = parse_money(payload.get("amount"), "مبلغ")
    if amount <= 0:
        raise AppError("مبلغ باید بیشتر از صفر باشد")
    method = payload.get("payment_method") or "cash"
    if method not in {"cash", "card"}:
        raise AppError("روش دریافت نامعتبر است")
    memo = clean_text(payload.get("memo"), "شرح", 120) or "دریافت طلب"
    with connect() as conn:
        account = conn.execute("SELECT * FROM accounts WHERE id=? AND active=1", (account_id,)).fetchone()
        if not account:
            raise AppError("حساب پیدا نشد", 404)
        balance = account_balance(conn, account_id)
        if balance <= 0:
            raise AppError("این حساب مانده بدهکار ندارد")
        if amount > balance:
            raise AppError("مبلغ از مانده بدهکار بیشتر است")
        sess = require_open(conn)
        cur = conn.execute(
            """INSERT INTO receipts (account_id, amount, payment_method, session_id, memo, user_id, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (account_id, amount, method, sess["id"], memo, user["id"], iso()),
        )
        counter = acc(conn, "1000" if method == "cash" else "1010")["id"]
        post_entry(conn, memo, [(counter, amount, 0), (account_id, 0, amount)], "receipt", cur.lastrowid, user["id"])
    return jsonify(ok=True)


def license_out(row) -> dict:
    item = dict(row)
    item["starts_jalali"] = to_jalali(row["starts_at"]) if row["starts_at"] else ""
    item["ends_jalali"] = to_jalali(row["ends_at"]) if row["ends_at"] else ""
    item["title"] = PLANS.get(row["plan"], (row["plan"], 0, ""))[0]
    item["status"] = row["status"] or "paid"
    item["host_saved"] = bool(row["host_saved"]) if "host_saved" in row.keys() else False
    return item


def mark_license_paid(conn, license_id: int, user_id: int, ref: str):
    row = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
    if not row:
        raise AppError("لایسنس پیدا نشد", 404)
    if row["status"] == "paid":
        return row
    if row["status"] != "pending":
        raise AppError("این لایسنس قابل تأیید نیست")
    title, months, _price_key = PLANS[row["plan"]]
    start = now_dt().replace(microsecond=0)
    end = add_months(start, months)
    updated = conn.execute(
        "UPDATE licenses SET status='paid', gateway_ref=?, starts_at=?, ends_at=? WHERE id=? AND status='pending'",
        (ref, iso(start), iso(end), license_id),
    )
    if updated.rowcount != 1:
        return conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
    return conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()


@app.get("/api/licenses")
def list_licenses():
    require_admin()
    with connect() as conn:
        settings = get_settings(conn)
        sold = conn.execute("SELECT COUNT(*) AS c FROM licenses WHERE plan='50y' AND status!='canceled'").fetchone()["c"]
        cap = setting_int(settings, "cap_50y")
        sync_licenses_to_host(conn)
        rows = conn.execute("SELECT * FROM licenses ORDER BY id DESC LIMIT 50").fetchall()
        access = ensure_access(conn)
    plans = []
    for key, (title, months, price_key) in PLANS.items():
        item = {"id": key, "title": title, "months": months, "price": setting_int(settings, price_key)}
        if key == "50y":
            item["cap"] = cap
            item["remaining"] = max(0, cap - sold)
        plans.append(item)
    return jsonify(plans=plans, licenses=[license_out(row) for row in rows], access=access)


@app.put("/api/licenses/prices")
def update_license_prices():
    require_admin()
    payload = body_json()
    allowed = {key: payload[key] for key in ("price_3m", "price_6m", "price_12m", "price_50y", "cap_50y") if key in payload}
    with connect() as conn:
        save_settings(conn, allowed)
    return jsonify(ok=True)


@app.post("/api/licenses")
def sell_license():
    user = require_admin()
    payload = body_json()
    plan = payload.get("plan")
    if plan not in PLANS:
        raise AppError("طرح لایسنس نامعتبر است")
    title, months, price_key = PLANS[plan]
    method = payload.get("payment_method") or "cash"
    if method not in {"cash", "card", "gateway"}:
        raise AppError("روش پرداخت لایسنس نامعتبر است")
    buyer = clean_text(payload.get("buyer_name"), "نام خریدار", 80, required=True)
    phone = norm_phone(payload.get("phone") or "")
    if not re.fullmatch(r"0\d{10}", phone):
        raise AppError("شماره تماس خریدار معتبر نیست")
    with connect() as conn:
        settings = get_settings(conn)
        if plan == "50y":
            cap = setting_int(settings, "cap_50y")
            sold = conn.execute("SELECT COUNT(*) AS c FROM licenses WHERE plan='50y' AND status!='canceled'").fetchone()["c"]
            if sold >= cap:
                raise AppError("ظرفیت لایسنس پنجاه‌ساله تمام شده است")
        list_price = setting_int(settings, price_key)
        discount = calc_discount(list_price, payload.get("discount_type") or "amount", payload.get("discount_value"))
        payable = list_price - discount
        if method == "gateway" and payable < 1000:
            raise AppError("حداقل مبلغ درگاه ۱۰۰۰ تومان است")
        start = now_dt().replace(microsecond=0)
        end = add_months(start, months)
        status = "pending" if method == "gateway" else "paid"
        cur = conn.execute(
            """INSERT INTO licenses (plan, list_price, discount, payable, buyer_name, phone, starts_at, ends_at,
               payment_method, session_id, user_id, created_at, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                plan, list_price, discount, payable, buyer, phone, iso(start), iso(end), method,
                None, user["id"], iso(), status,
            ),
        )
        license_id = cur.lastrowid
        saved = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
        host_saved = store_license_on_host(conn, saved)
        saved = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
    if method == "gateway":
        try:
            gateway_name, ref, pay_url = webakery_payment(settings, license_id, title, payable, buyer, phone)
        except Exception:
            with connect() as conn:
                conn.execute(
                    "UPDATE licenses SET status='canceled', host_saved=0 WHERE id=? AND status='pending'",
                    (license_id,),
                )
                row = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
                if row:
                    store_license_on_host(conn, row)
            raise
        with connect() as conn:
            conn.execute(
                "UPDATE licenses SET gateway=?, gateway_ref=?, pay_url=? WHERE id=?",
                (gateway_name, ref, pay_url, license_id),
            )
            saved = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
            host_saved = store_license_on_host(conn, saved)
            saved = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
    return jsonify(ok=True, payable=payable, license=license_out(saved), host_saved=bool(saved["host_saved"]))


@app.post("/api/licenses/<int:license_id>/confirm")
def confirm_license(license_id: int):
    user = require_admin()
    payload = body_json()
    mode = payload.get("mode") or "verify"
    with connect() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
        if not row:
            raise AppError("لایسنس پیدا نشد", 404)
        if row["status"] == "paid":
            return jsonify(ok=True, license=license_out(row))
        if row["status"] != "pending":
            raise AppError("این لایسنس قابل تأیید نیست")
        settings = get_settings(conn)
    if row["gateway"] != "woocommerce":
        settings = license_gateway_settings(settings)
    if mode == "manual":
        ref = clean_text(payload.get("ref"), "پیگیری", 64)
        if len(ref) < 3:
            raise AppError("شماره پیگیری را وارد کنید")
    elif (row["gateway"] or "zibal") == "zibal":
        ref = host_zibal_verify(row["gateway_ref"] or "")
    else:
        ref = gateway_verify(settings, row)
    with connect() as conn:
        saved = mark_license_paid(conn, license_id, user["id"], ref)
        store_license_on_host(conn, saved)
        saved = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
        settings = get_settings(conn)
    if settings.get("sms_on_sale") == "1":
        notify_manager(settings, f"دفترچی: لایسنس وب‌بیکری {saved['payable']:,} تومان برای {saved['buyer_name']}")
    return jsonify(ok=True, payable=saved["payable"], license=license_out(saved))


@app.post("/api/licenses/<int:license_id>/cancel")
def cancel_license(license_id: int):
    require_admin()
    with connect() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
        if not row:
            raise AppError("لایسنس پیدا نشد", 404)
        if row["status"] != "pending":
            raise AppError("فقط لایسنس در انتظار پرداخت را می‌توان لغو کرد")
        conn.execute("UPDATE licenses SET status='canceled', host_saved=0 WHERE id=?", (license_id,))
        row = conn.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
        store_license_on_host(conn, row)
    return jsonify(ok=True)


@app.get("/pay/return")
def pay_return():
    authority = (request.args.get("Authority") or request.args.get("authority") or request.args.get("trackId") or request.args.get("id") or "").strip()
    success = (request.args.get("success") or "").strip()
    status = (request.args.get("Status") or request.args.get("status") or "").strip().upper()
    if not authority:
        return pay_page("شناسه پرداخت نیامد", False), 400
    failed = success == "0" or status in {"NOK", "NO", "FAILED", "3"}
    if not failed and status and success != "1" and status not in {"OK", "100", "1", "2", "SUCCESS"}:
        failed = True
    if failed:
        return pay_page("پرداخت در وب‌بیکری انجام نشد یا لغو شد.", False)
    with connect() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE gateway_ref=? AND status='pending'", (authority,)).fetchone()
        sale = None if row else conn.execute("SELECT * FROM sales WHERE gateway_ref=? AND status='pending'", (authority,)).fetchone()
        settings = get_settings(conn)
        if row and row["gateway"] != "woocommerce":
            settings = license_gateway_settings(settings)
    try:
        if row:
            if (row["gateway"] or "zibal") == "zibal":
                ref = host_zibal_verify(row["gateway_ref"] or "")
            else:
                ref = gateway_verify(settings, row)
            with connect() as conn:
                saved = mark_license_paid(conn, row["id"], row["user_id"], ref)
                store_license_on_host(conn, saved)
            return pay_page("لایسنس پرداخت شد و در دفترچی فعال است.", True)
        if sale:
            ref = gateway_verify(settings, sale)
            with connect() as conn:
                current = conn.execute("SELECT status FROM sales WHERE id=?", (sale["id"],)).fetchone()
                if current and current["status"] == "pending":
                    finalize_sale(conn, sale["id"], sale["user_id"])
                    conn.execute("UPDATE sales SET gateway_ref=?, pos_ref=? WHERE id=?", (ref, ref, sale["id"]))
                    paid_now = True
                else:
                    paid_now = False
            maybe_send_moadian(sale["id"])
            if paid_now:
                with connect() as conn:
                    paid = sale_payload(conn, sale["id"])
                notify_buyer(paid["sale"])
            return pay_page("فاکتور پرداخت شد.", True)
    except AppError as exc:
        return pay_page(str(exc), False), exc.status
    return pay_page("پرداختی با این شناسه در انتظار تأیید نیست.", False), 404


def pay_page(message: str, ok: bool):
    tone = "#1f7a4d" if ok else "#9b3a3a"
    safe = html.escape(message)
    return (
        "<!doctype html><html lang='fa' dir='rtl'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>دفترچی</title><body style='font-family:tahoma,sans-serif;background:#f6f4ef;color:#1c1a17;padding:32px'>"
        f"<main style='max-width:420px;margin:auto;background:#fff;border:1px solid #e4ddd2;border-radius:16px;padding:24px'>"
        f"<h1 style='font-size:20px;margin:0 0 12px'>بازگشت از وب‌بیکری</h1>"
        f"<p style='color:{tone}'>{safe}</p>"
        "<p><a href='/'>برگشت به دفترچی</a></p></main></body></html>"
    )


@app.get("/api/sms")
def list_sms():
    require_admin()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 100").fetchall()
    messages = []
    for row in rows:
        item = dict(row)
        item["at_jalali"] = to_jalali(row["created_at"])
        messages.append(item)
    return jsonify(messages=messages)


@app.post("/api/sms")
def send_sms():
    require_admin()
    payload = body_json()
    recipient = norm_phone(payload.get("recipient") or "")
    text = clean_text(payload.get("body"), "متن", 500, required=True)
    if not re.fullmatch(r"09\d{9}", recipient):
        raise AppError("شماره گیرنده معتبر نیست")
    with connect() as conn:
        status, detail = deliver_sms(conn, get_settings(conn), recipient, text)
    return jsonify(ok=status != "failed", status=status, detail=detail)


def public_settings(data: dict) -> dict:
    out = dict(data)
    out.pop("must_change_password", None)
    out["moadian_key_saved"] = "1" if out.get("moadian_private_key") else "0"
    out["moadian_private_key"] = ""
    out["telegram_token_saved"] = "1" if out.get("telegram_bot_token") else "0"
    out["telegram_bot_token"] = ""
    return out


@app.get("/api/settings")
def get_settings_route():
    require_admin()
    with connect() as conn:
        data = get_settings(conn)
    return jsonify(settings=public_settings(data))


@app.put("/api/settings")
def put_settings():
    require_admin()
    with connect() as conn:
        save_settings(conn, body_json())
        data = get_settings(conn)
    return jsonify(settings=public_settings(data))


def moadian_ready(settings: dict) -> tuple[str, str, str]:
    fiscal = (settings.get("moadian_fiscal_id") or "").strip().upper()
    economic = re.sub(r"\D", "", str(settings.get("moadian_economic_code") or ""))
    private_key = settings.get("moadian_private_key") or ""
    if not re.fullmatch(r"[A-Z0-9]{6}", fiscal) or not re.fullmatch(r"\d{11,14}", economic) or "PRIVATE KEY" not in private_key:
        raise AppError("شناسه حافظه مالیاتی، کد اقتصادی و کلید خصوصی را در تنظیمات وارد کنید")
    return fiscal, economic, private_key


def moadian_client(settings: dict):
    try:
        import moadian
    except ImportError:
        raise AppError("کتابخانه رمزنگاری روی این رایانه نیست. دفترچی را دوباره اجرا کنید.")
    fiscal, _economic, private_key = moadian_ready(settings)
    return moadian.Client(fiscal, private_key, settings.get("moadian_sandbox") == "1", http_request)


def call_moadian(action):
    try:
        import moadian
    except ImportError:
        raise AppError("کتابخانه رمزنگاری روی این رایانه نیست. دفترچی را دوباره اجرا کنید.")
    try:
        return action()
    except moadian.MoadianError as exc:
        raise AppError(str(exc), 502)
    except AppError:
        raise
    except Exception:
        log.exception("moadian")
        raise AppError("سامانه مودیان پاسخ نداد", 502)


def split_rial_discount(amounts: list[int], discount: int) -> list[int]:
    if discount <= 0 or not amounts:
        return [0] * len(amounts)
    total = sum(amounts)
    discount = min(discount, total)
    shares = []
    used = 0
    for index, amount in enumerate(amounts):
        share = discount - used if index == len(amounts) - 1 else (discount * amount // total if total else 0)
        share = max(0, min(share, amount))
        shares.append(share)
        used += share
    return shares


def build_moadian_invoice(sale, items, fiscal: str, economic: str, vat_rate: int) -> dict:
    import moadian
    when = datetime.fromisoformat(sale["created_at"])
    if when.tzinfo is None:
        when = when.replace(tzinfo=TEHRAN)
    taxid = moadian.generate_tax_id(fiscal, when, int(sale["id"]))
    indatim = int(when.timestamp() * 1000)
    amounts = [int(item["unit_price"]) * 10 * int(item["qty"]) for item in items]
    discounts = split_rial_discount(amounts, int(sale["discount"]) * 10)
    body = []
    for item, prdis, dis in zip(items, amounts, discounts):
        adis = prdis - dis
        vam = int((Decimal(adis) * Decimal(vat_rate) / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        body.append({
            "sstid": item["tax_code"],
            "sstt": item["name"],
            "am": int(item["qty"]),
            "mu": "1627",
            "fee": int(item["unit_price"]) * 10,
            "prdis": prdis,
            "dis": dis,
            "adis": adis,
            "vra": int(vat_rate),
            "vam": vam,
            "tsstam": adis + vam,
        })
    tprdis = sum(line["prdis"] for line in body)
    tdis = sum(line["dis"] for line in body)
    tadis = sum(line["adis"] for line in body)
    tvam = sum(line["vam"] for line in body)
    tbill = sum(line["tsstam"] for line in body)
    credit = sale["payment_method"] == "credit"
    invoice = {
        "header": {
            "taxid": taxid,
            "indatim": indatim,
            "indati2m": indatim,
            "inty": 2,
            "inno": moadian.invoice_serial_hex(int(sale["id"])),
            "irtaxid": None,
            "inp": 1,
            "ins": 1,
            "tins": economic,
            "tprdis": tprdis,
            "tdis": tdis,
            "tadis": tadis,
            "tvam": tvam,
            "todam": 0,
            "tbill": tbill,
            "setm": 2 if credit else 1,
            "cap": 0 if credit else tbill,
            "insp": tbill if credit else 0,
            "tvop": 0 if credit else tvam,
            "tax17": 0,
        },
        "body": body,
    }
    if not credit:
        pmt = {"cash": 3, "card": 4, "gateway": 5}.get(sale["payment_method"], 8)
        invoice["payments"] = [{"pmt": pmt, "pdt": indatim, "pv": tbill}]
    return invoice


def remember_moadian(sale_id: int, status: str, error: str = "", **extra):
    assignments = ["moadian_status=?", "moadian_error=?"]
    values: list = [status, (error or "")[:400]]
    for key in ("moadian_uid", "moadian_taxid", "moadian_reference"):
        if key in extra:
            assignments.append(f"{key}=?")
            values.append(extra[key])
    values.append(sale_id)
    with connect() as conn:
        conn.execute(f"UPDATE sales SET {', '.join(assignments)} WHERE id=?", values)


def enqueue_reference(body: dict) -> tuple[str, str]:
    result = body.get("result") if isinstance(body, dict) else None
    row = result[0] if isinstance(result, list) and result else result if isinstance(result, dict) else None
    if not isinstance(row, dict):
        raise AppError("پاسخ سامانه مودیان نامشخص است", 502)
    error = row.get("errorCode") or row.get("errorDetail")
    if error:
        raise AppError(str(error)[:240], 502)
    ref = str(row.get("referenceNumber") or "")
    if not ref:
        raise AppError("شماره پیگیری سامانه مودیان نیامد", 502)
    return str(row.get("uid") or ""), ref


def submit_moadian(sale_id: int) -> dict:
    with connect() as conn:
        sale = conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        if not sale:
            raise AppError("فاکتور پیدا نشد", 404)
        if sale["status"] != "paid":
            raise AppError("فقط فاکتور پرداخت‌شده به سامانه مودیان می‌رود")
        if sale["moadian_status"] in {"sent", "success", "pending"} and sale["moadian_reference"]:
            payload = sale_payload(conn, sale_id)
            payload["message"] = "این فاکتور قبلاً به سامانه رفته است"
            return payload
        settings = get_settings(conn)
        if settings.get("moadian_enabled") != "1":
            raise AppError("در تنظیمات، اتصال سامانه مودیان خاموش است")
        fiscal, economic, _key = moadian_ready(settings)
        items = conn.execute(
            """SELECT si.name, si.qty, si.unit_price, p.tax_code
               FROM sale_items si LEFT JOIN products p ON p.id = si.product_id
               WHERE si.sale_id=? ORDER BY si.id""",
            (sale_id,),
        ).fetchall()
        missing = [row["name"] for row in items if not (row["tax_code"] or "").strip()]
        if missing:
            message = "شناسه کالا/خدمت مودیان نیست: " + "، ".join(missing)
            conn.execute(
                "UPDATE sales SET moadian_status='skipped', moadian_error=? WHERE id=?",
                (message[:400], sale_id),
            )
            payload = sale_payload(conn, sale_id)
            payload["message"] = message
            return payload
        rate = setting_int(settings, "moadian_vat")
        if rate > 100:
            rate = 10
        invoice = build_moadian_invoice(sale, items, fiscal, economic, rate)
        conn.execute("UPDATE sales SET moadian_taxid=?, moadian_error='' WHERE id=?", (invoice["header"]["taxid"], sale_id))
        client = moadian_client(settings)
    try:
        response = call_moadian(lambda: client.send_invoice(invoice))
        uid, ref = enqueue_reference(response)
    except AppError as exc:
        remember_moadian(sale_id, "failed", str(exc), moadian_taxid=invoice["header"]["taxid"])
        raise
    remember_moadian(sale_id, "sent", "", moadian_uid=uid, moadian_reference=ref, moadian_taxid=invoice["header"]["taxid"])
    with connect() as conn:
        payload = sale_payload(conn, sale_id)
    payload["message"] = "صورتحساب در صف سامانه مودیان قرار گرفت"
    return payload


def maybe_send_moadian(sale_id: int):
    try:
        with connect() as conn:
            row = conn.execute("SELECT status, moadian_status FROM sales WHERE id=?", (sale_id,)).fetchone()
            enabled = get_settings(conn).get("moadian_enabled") == "1"
        if not row or row["status"] != "paid" or not enabled:
            return
        if row["moadian_status"] in {"sent", "success", "pending"}:
            return
        submit_moadian(sale_id)
    except AppError as exc:
        with connect() as conn:
            current = conn.execute("SELECT moadian_status FROM sales WHERE id=?", (sale_id,)).fetchone()
        if current and current["moadian_status"]:
            return
        remember_moadian(sale_id, "failed", str(exc))
    except Exception:
        log.exception("moadian send")
        remember_moadian(sale_id, "failed", "ارسال به سامانه مودیان انجام نشد")


def inquiry_moadian(sale_id: int) -> dict:
    with connect() as conn:
        sale = conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        if not sale:
            raise AppError("فاکتور پیدا نشد", 404)
        if not sale["moadian_reference"]:
            raise AppError("این فاکتور هنوز شماره پیگیری مودیان ندارد")
        client = moadian_client(get_settings(conn))
        reference = sale["moadian_reference"]
    body = call_moadian(lambda: client.inquiry(reference))
    result = body.get("result") if isinstance(body, dict) else None
    data = result.get("data") if isinstance(result, dict) else None
    row = data[0] if isinstance(data, list) and data else {}
    status = str((row or {}).get("status") or "").upper()
    errors = []
    detail = (row or {}).get("data") if isinstance(row, dict) else None
    if isinstance(detail, dict):
        for item in detail.get("error") or []:
            if isinstance(item, dict) and item.get("message"):
                errors.append(str(item["message"]))
    text = "؛ ".join(errors)[:400]
    if status == "SUCCESS":
        stored, text, message = "success", "", "سامانه مودیان صورتحساب را تأیید کرد"
    elif status == "FAILED":
        stored = "failed"
        text = text or "سامانه صورتحساب را نپذیرفت"
        message = text
    else:
        stored = "pending"
        text = text or "هنوز در سامانه در حال بررسی است"
        message = text
    remember_moadian(sale_id, stored, text)
    with connect() as conn:
        payload = sale_payload(conn, sale_id)
    payload["message"] = message
    return payload


@app.post("/api/sales/<int:sale_id>/moadian")
def send_sale_moadian(sale_id: int):
    require_user()
    try:
        payload = submit_moadian(sale_id)
    except AppError as exc:
        if exc.status < 500:
            raise
        with connect() as conn:
            payload = sale_payload(conn, sale_id)
        payload["message"] = str(exc)
    return jsonify(**payload)


@app.post("/api/sales/<int:sale_id>/moadian/inquiry")
def inquiry_sale_moadian(sale_id: int):
    require_user()
    try:
        payload = inquiry_moadian(sale_id)
    except AppError as exc:
        if exc.status < 500:
            raise
        with connect() as conn:
            payload = sale_payload(conn, sale_id)
        payload["message"] = str(exc)
    return jsonify(**payload)


@app.post("/api/settings/test/<kind>")
def test_setting(kind: str):
    require_admin()
    posted = request.get_json(silent=True) or {}
    with connect() as conn:
        settings = get_settings(conn)
        for key in ("wp_url", "woo_key", "woo_secret"):
            text = str(posted.get(key) or "").strip()
            if text:
                settings[key] = text
        if kind == "wp":
            message = wordpress_status(settings)
        elif kind == "woo":
            _status, body = woo_request(settings, "GET", "products", {"per_page": "1"})
            if not isinstance(body, list):
                raise AppError("ووکامرس فهرست کالا نداد", 502)
            message = "اتصال ووکامرس برقرار است"
        elif kind == "pos":
            host = (settings.get("pos_host") or "").strip()
            if not host:
                raise AppError("آدرس کارت‌خوان را وارد کنید")
            port = int(str(settings.get("pos_port") or "0").translate(DIGITS) or "0")
            if not 1 <= port <= 65535:
                raise AppError("پورت نامعتبر است")
            try:
                with socket.create_connection((host, port), timeout=4):
                    pass
            except OSError as exc:
                raise AppError(f"کارت‌خوان پاسخ نداد: {exc}", 502)
            message = f"ارتباط با {host}:{port} برقرار شد"
        elif kind == "sms":
            phone = manager_phone(settings)
            if not phone:
                raise AppError("شماره موبایل مدیر را وارد کنید")
            status, detail = deliver_sms(conn, settings, phone, "پیام آزمایشی دفترچی")
            message = "پیامک ارسال شد" if status == "sent" else detail
        elif kind == "email":
            if not host_mail_ready():
                raise AppError(explain_host_mail("تنظیم نشده"), 502)
            message = "هاست وب‌بیکری برای فرستادن کد به جیمیل پاسخ داد"
        elif kind == "moadian":
            _fiscal, economic, _key = moadian_ready(settings)
            client = moadian_client(settings)
            call_moadian(client.server_information)
            call_moadian(client.token)
            eco = call_moadian(lambda: client.economic_code(economic))
            data = ((eco.get("result") or {}).get("data") or {}) if isinstance(eco, dict) else {}
            trade = data.get("nameTrade") or "کد اقتصادی پذیرفته شد"
            mode = "آزمایشی" if settings.get("moadian_sandbox") == "1" else "واقعی"
            message = f"اتصال {mode} به سامانه مودیان برقرار است: {trade}"
        else:
            raise AppError("آزمایش نامعتبر است")
    return jsonify(ok=True, message=message)


init_db()


def main():
    port = int(os.environ.get("PORT", "8080"))
    print(f"دفترچی روی http://127.0.0.1:{port}")
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port)
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
