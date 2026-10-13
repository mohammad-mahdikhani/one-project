"""Match supplier rows to shop products by code, number, name, then web search."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .normalize import fold_persian, model_tokens, name_tokens, normalize_code, normalize_name

AUTO_UPDATE_SCORE = 78
SUGGEST_SCORE = 58

ALIASES = {
    "الیت": "elite",
    "elite": "elite",
    "elit": "elite",
    "اکونومی": "economy",
    "economy": "economy",
    "لوتوس": "lotus",
    "lotus": "lotus",
    "پرایم": "prime",
    "prime": "prime",
    "لیلیوم": "lilium",
    "lilium": "lilium",
    "تولیپ": "tulip",
    "tulip": "tulip",
    "لجند": "legend",
    "legend": "legend",
    "ساکورا": "sakura",
    "sakura": "sakura",
    "ویتا": "vita",
    "vita": "vita",
    "ارکید": "orchid",
    "ارکیده": "orchid",
    "orchid": "orchid",
    "سه": "3",
    "مرحله": "stage",
    "مرحله‌ای": "stage",
    "مرحله ای": "stage",
}

DISTINCTIVE = {
    "elite",
    "economy",
    "lotus",
    "prime",
    "lilium",
    "tulip",
    "legend",
    "sakura",
    "vita",
    "orchid",
}

PRODUCT_KINDS = {
    "هوزینگ",
    "ممبران",
    "پمپ",
    "فیلتر",
    "دستگاه",
    "متر",
    "هپا",
    "voc",
    "هوا",
    "اب",
}

KIND_CONFLICTS = (
    ({"دستگاه"}, {"فیلتر", "ممبران", "هوزینگ", "پمپ"}),
    ({"هوا"}, {"اب"}),
    ({"هپا", "voc"}, {"ممبران", "هوزینگ"}),
)

CODE_RE = re.compile(r"(?:0\d{7}|99\d{6}|02\d{6}|\d{6,12})")
DIGIT_RE = re.compile(r"\d{2,}")


@dataclass
class Product:
    id: int
    name: str
    sku: str = ""
    barcode: str = ""
    price: int | None = None
    sale_price: int | None = None
    stock: int | None = None
    permalink: str = ""
    slug: str = ""


@dataclass
class SheetRow:
    row: int
    name: str
    sku: str | None = None
    price: int | None = None
    sale_price: int | None = None
    stock: int | None = None
    source: str = "file"
    source_url: str = ""
    source_date: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class MatchResult:
    sheet: SheetRow
    product: Product | None
    score: int
    reason: str
    action: str
    suggested: Product | None = None

    @property
    def status(self) -> str:
        return self.action


def _code_key(value: str | None) -> str:
    return (normalize_code(value) or "").lower()


def extract_codes(*parts: str | None) -> set[str]:
    found: set[str] = set()
    for part in parts:
        text = fold_persian(str(part or "")).replace(" ", "").replace("-", "")
        for match in CODE_RE.findall(text):
            if match:
                found.add(match.lower())
    return {item for item in found if item}


def alias_set(text: str) -> set[str]:
    out = set()
    for token in name_tokens(text) + list(model_tokens(text)):
        out.add(ALIASES.get(token, token))
    return out


def _codes_overlap(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    for one in left:
        for other in right:
            if len(one) >= 6 and len(other) >= 6 and (one.endswith(other) or other.endswith(one)):
                return True
    return False


def token_score(sheet_name: str, product_name: str) -> tuple[int, str]:
    sheet_norm = normalize_name(sheet_name)
    product_norm = normalize_name(product_name)
    if not sheet_norm or not product_norm:
        return 0, "نام خالی است"
    if sheet_norm == product_norm:
        return 98, "نام یکسان است"

    sheet_words = name_tokens(sheet_name)
    product_words = name_tokens(product_name)
    if not sheet_words or not product_words:
        return 0, "واژه قابل تطابق ندارد"

    sheet_set = set(sheet_words)
    product_set = set(product_words)
    overlap = sheet_set & product_set
    sheet_all = set(sheet_norm.split())
    product_all = set(product_norm.split())
    sheet_kind = sheet_all & PRODUCT_KINDS
    product_kind = product_all & PRODUCT_KINDS
    if sheet_kind and product_kind and sheet_kind.isdisjoint(product_kind):
        return 0, "نوع کالا فرق دارد"
    only_sheet = sheet_kind - product_kind
    only_product = product_kind - sheet_kind
    for left, right in KIND_CONFLICTS:
        if (only_sheet & left and only_product & right) or (only_sheet & right and only_product & left):
            return 0, "نوع کالا فرق دارد"

    sheet_alias = alias_set(sheet_name)
    product_alias = alias_set(product_name)
    sheet_mark = sheet_alias & DISTINCTIVE
    product_mark = product_alias & DISTINCTIVE
    if sheet_mark and product_mark and sheet_mark.isdisjoint(product_mark):
        return 0, "مدل کالا فرق دارد"

    sheet_models = model_tokens(sheet_name)
    product_models = model_tokens(product_name)
    shared_models = sheet_models & product_models
    sheet_digits = set(DIGIT_RE.findall(sheet_norm))
    product_digits = set(DIGIT_RE.findall(product_norm))
    shared_digits = {d for d in sheet_digits & product_digits if len(d) >= 2 and d not in {"10", "12", "20"}}

    if sheet_models and product_models and not shared_models:
        numeric = {m for m in sheet_models if m.isdigit()}
        other = {m for m in product_models if m.isdigit()}
        if numeric and other and numeric.isdisjoint(other) and not shared_digits:
            return 0, "مدل کالا فرق دارد"
        if (sheet_mark & DISTINCTIVE) and (product_mark & DISTINCTIVE) and sheet_mark.isdisjoint(product_mark):
            return 0, "مدل کالا فرق دارد"

    recall = len(overlap) / len(sheet_set) if sheet_set else 0
    precision = len(overlap) / len(product_set) if product_set else 0
    dice = 2 * len(overlap) / (len(sheet_set) + len(product_set)) if (sheet_set or product_set) else 0
    fuzzy = SequenceMatcher(None, sheet_norm, product_norm).ratio()
    alias_hit = len(sheet_alias & product_alias)
    base = int(round(100 * (0.28 * recall + 0.22 * precision + 0.20 * dice + 0.30 * fuzzy)))
    if shared_models:
        base += min(18, 6 * len(shared_models))
    if shared_digits:
        base += min(10, 4 * len(shared_digits))
    if alias_hit:
        base += min(10, 3 * alias_hit)
    if sheet_mark and sheet_mark == product_mark:
        base += 8

    if sheet_mark != product_mark and (sheet_mark or product_mark):
        base = min(base, 74)

    return min(max(base, 0), 96), "تطابق هوشمند نام و عدد"


def _decide(sheet: SheetRow, product: Product | None, score: int, reason: str, suggested: Product | None = None) -> MatchResult:
    if product and score >= AUTO_UPDATE_SCORE:
        return MatchResult(sheet, product, score, reason, "update")
    if suggested and score >= SUGGEST_SCORE:
        return MatchResult(sheet, None, score, "نام نزدیک است؛ تأیید کنید", "suggest", suggested=suggested)
    if product and score >= SUGGEST_SCORE:
        return MatchResult(sheet, None, score, "نام نزدیک است؛ تأیید کنید", "suggest", suggested=product)
    if sheet.price is None:
        return MatchResult(sheet, None, 0, "قیمت مصرف‌کننده ندارد", "skip")
    return MatchResult(sheet, None, score, "روی سایت پیدا نشد", "create")


def match_row(sheet: SheetRow, products: list[Product]) -> MatchResult:
    sheet_codes = extract_codes(sheet.sku, sheet.name)
    for product in products:
        product_codes = extract_codes(product.sku, product.barcode, product.name, product.slug)
        if sheet_codes and product_codes and _codes_overlap(sheet_codes, product_codes):
            return MatchResult(sheet, product, 100, "کد یا عدد کالا یکی است", "update")
        if sheet.sku and (
            _code_key(product.sku) == _code_key(sheet.sku) or _code_key(product.barcode) == _code_key(sheet.sku)
        ):
            return MatchResult(sheet, product, 100, "کد کالا یکی است", "update")

    best: tuple[int, Product, str] | None = None
    for product in products:
        score, reason = token_score(sheet.name, product.name)
        if best is None or score > best[0]:
            best = (score, product, reason)
    if not best:
        return _decide(sheet, None, 0, "روی سایت پیدا نشد")
    if best[0] >= AUTO_UPDATE_SCORE:
        return MatchResult(sheet, best[1], best[0], best[2], "update")
    if best[0] >= SUGGEST_SCORE:
        return MatchResult(sheet, None, best[0], "نام نزدیک است؛ تأیید کنید", "suggest", suggested=best[1])
    return _decide(sheet, None, best[0], best[2])


def _product_from_hit(hit_url: str, hit_title: str, products: list[Product]) -> tuple[Product, int, str] | None:
    host_hits = []
    for product in products:
        link = (product.permalink or product.slug or "").lower()
        if link and hit_url and (link.rstrip("/") in hit_url.rstrip("/") or product.slug and product.slug in hit_url):
            return product, 95, "گوگل صفحه همین کالا را پیدا کرد"
        score, _reason = token_score(hit_title, product.name)
        host_hits.append((score, product))
    host_hits.sort(key=lambda item: item[0], reverse=True)
    if host_hits and host_hits[0][0] >= SUGGEST_SCORE:
        score, product = host_hits[0]
        reason = "گوگل نام کالا را روی سایت پیدا کرد" if score >= AUTO_UPDATE_SCORE else "گوگل یک کالای نزدیک پیدا کرد"
        return product, min(score + 4, 96), reason
    return None


def match_rows(rows: list[SheetRow], products: list[Product], shop_url: str | None = None, search=None) -> list[MatchResult]:
    used: set[int] = set()
    results: list[MatchResult] = []
    pending: list[int] = []
    for sheet in rows:
        available = [item for item in products if id(item) not in used]
        result = match_row(sheet, available)
        chosen = result.product or (result.suggested if result.score >= AUTO_UPDATE_SCORE else None)
        if chosen:
            used.add(id(chosen))
        results.append(result)
        if result.action in {"create", "suggest"}:
            pending.append(len(results) - 1)

    if shop_url and search and pending:
        for index in pending[:20]:
            result = results[index]
            available = [item for item in products if id(item) not in used]
            try:
                hits = search(result.sheet.name, shop_url, result.sheet.sku) or []
            except Exception:
                continue
            best_hit = None
            for hit in hits[:8]:
                title = getattr(hit, "title", "") or (hit.get("title") if isinstance(hit, dict) else "")
                url = getattr(hit, "url", "") or (hit.get("url") if isinstance(hit, dict) else "")
                found = _product_from_hit(str(url), str(title), available)
                if not found:
                    continue
                product, score, reason = found
                if best_hit is None or score > best_hit[1]:
                    best_hit = (product, score, reason)
            if not best_hit:
                continue
            product, score, reason = best_hit
            results[index] = _decide(result.sheet, product if score >= AUTO_UPDATE_SCORE else None, score, reason, suggested=product)
            chosen = results[index].product or (results[index].suggested if results[index].score >= AUTO_UPDATE_SCORE else None)
            if chosen:
                used.add(id(chosen))
    return results
