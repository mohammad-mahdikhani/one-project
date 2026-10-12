"""Normalize Persian product names, codes, and money values."""

from __future__ import annotations

import re
import unicodedata

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

CHAR_MAP = str.maketrans({
    "ك": "ک",
    "ي": "ی",
    "ى": "ی",
    "ة": "ه",
    "أ": "ا",
    "إ": "ا",
    "ؤ": "و",
    "ئ": "ی",
    "ۀ": "ه",
    "‌": " ",
    "‍": "",
    "‐": "-",
    "–": "-",
    "—": "-",
    "−": "-",
    "×": " ",
    "*": " ",
})

OCR_FIXES = (
    ("پالستیک", "پلاستیک"),
    ("كاال", "کالا"),
    ("مرصف", "مصرف"),
    ("فاضالب", "فاضلاب"),
    ("باال", "بالا"),
    ("الیافي", "الیافی"),
    ("میكرون", "میکرون"),
    ("يك ", "یک "),
    ("یك ", "یک "),
    ("كربن", "کربن"),
    ("فلزي", "فلزی"),
    ("دنده اي", "دنده‌ای"),
    ("دنده ای", "دنده‌ای"),
    ("اتصاالت", "اتصالات"),
    ("سه راهی", "سه راهی"),
    ("سه راهي", "سه راهی"),
    ("زانویي", "زانویی"),
    ("زانوئی", "زانویی"),
    ("مادگي", "مادگی"),
    ("نري", "نری"),
    ("كنترل", "کنترل"),
    ("كننده", "کننده"),
    ("پيش", "پیش"),
    ("مرحله اي", "مرحله‌ای"),
    ("مرحله ای", "مرحله‌ای"),
)

STOPWORDS = {
    "دستگاه", "مدل", "با", "و", "در", "به", "از", "برای", "بدون", "تا",
    "عدد", "عددی", "سري", "سری", "پک", "بسته", "طول", "بطول", "سایز",
    "اینچ", "میکرون", "لیتر", "روز", "سفید", "آبی", "مشکی", "سیاه",
    "نقره", "ای", "تایوان", "ساده", "کامل", "خاص", "مخصوص",
}

SPACE_RE = re.compile(r"[\s\u200c\u200f\u202a-\u202e]+")
PUNCT_RE = re.compile(r"[()\[\]{},.;:|/\\'\"«»<>`~!@#$%^&+=?]+")
CODE_RE = re.compile(r"^\d{5,12}$")


def clean_space(text: str) -> str:
    return SPACE_RE.sub(" ", (text or "").strip())


def fold_persian(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    value = value.translate(PERSIAN_DIGITS).translate(CHAR_MAP)
    for src, dst in OCR_FIXES:
        value = value.replace(src, dst)
    return clean_space(value)


def normalize_name(text: str) -> str:
    value = fold_persian(text).lower()
    value = PUNCT_RE.sub(" ", value)
    value = value.replace("آ", "ا")
    return clean_space(value)


def name_tokens(text: str) -> list[str]:
    tokens = []
    for raw in normalize_name(text).split():
        if raw in STOPWORDS or len(raw) == 1:
            continue
        tokens.append(raw)
    return tokens


def model_tokens(text: str) -> set[str]:
    value = normalize_name(text)
    found: set[str] = set()
    for match in re.finditer(r"[a-z]{1,10}\d{1,4}[a-z0-9\-]*|\d{2,4}[a-z]{2,6}|\d+\s*gpd|[a-z]{2,}(?:-[a-z0-9]+)+", value):
        token = match.group(0).replace(" ", "")
        if token not in STOPWORDS:
            found.add(token)
    for match in re.finditer(r"\b(\d{2,4})\b", value):
        number = match.group(1)
        if number not in {"10", "12", "20", "24", "220", "300", "1000", "2000", "1600"}:
            found.add(number)
    for special in ("elite", "prime", "lotus", "legend", "tulip", "lilium", "vita", "orchid", "sakura", "qc", "ln", "hs", "lp", "bb", "slim", "inline", "hepa", "voc"):
        if re.search(rf"\b{special}\b", value):
            found.add(special)
    return found


def normalize_code(value) -> str | None:
    if value is None:
        return None
    text = fold_persian(str(value)).replace(" ", "").replace("-", "")
    if not text or text in {"-", "—", "نان", "none"}:
        return None
    return text


def parse_money(value, allow_empty: bool = False) -> int | None:
    if value is None or value == "":
        if allow_empty:
            return None
        raise ValueError("قیمت خالی است")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(round(float(value)))
    text = fold_persian(str(value)).replace(",", "").replace("٬", "").replace("،", "")
    text = text.replace("ریال", "").replace("تومان", "").replace(" ", "")
    if text in {"", "-", "—", "نان", "none"}:
        if allow_empty:
            return None
        raise ValueError("قیمت خالی است")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        raise ValueError(f"قیمت نامعتبر است: {value}")
    return int(round(float(text)))


def format_money(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", "٬")
