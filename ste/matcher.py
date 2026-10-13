"""Match supplier sheet rows to site products by code, then by name."""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalize import model_tokens, name_tokens, normalize_code, normalize_name


@dataclass
class Product:
    id: int
    name: str
    sku: str = ""
    barcode: str = ""
    price: int | None = None
    sale_price: int | None = None
    stock: int | None = None


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
    if not overlap:
        return 0, "هیچ واژه مشترکی ندارد"

    recall = len(overlap) / len(sheet_set)
    precision = len(overlap) / len(product_set)
    dice = 2 * len(overlap) / (len(sheet_set) + len(product_set))
    base = int(round(100 * (0.40 * recall + 0.30 * precision + 0.30 * dice)))

    distinctive = {"اکونومی", "الیت", "لوتوس", "پرایم", "لیلیوم", "تولیپ", "لجند", "ساکورا", "ویتا"}
    sheet_mark = set(sheet_words) & distinctive
    product_mark = set(product_words) & distinctive
    if sheet_mark and product_mark and sheet_mark.isdisjoint(product_mark):
        return 0, "مدل کالا فرق دارد"
    if sheet_mark != product_mark and (sheet_mark or product_mark):
        base = min(base, 70)

    sheet_models = model_tokens(sheet_name)
    product_models = model_tokens(product_name)
    shared_models = sheet_models & product_models
    if sheet_models and product_models and not shared_models:
        numeric = {m for m in sheet_models if m.isdigit()}
        other = {m for m in product_models if m.isdigit()}
        if numeric and other and numeric.isdisjoint(other):
            return 0, "مدل کالا فرق دارد"
        letters = {m for m in sheet_models if not m.isdigit()}
        other_letters = {m for m in product_models if not m.isdigit()}
        strong = {"elite", "prime", "lotus", "legend", "vita", "orchid"}
        if (letters & strong) and (other_letters & strong) and not (letters & other_letters & strong):
            return 0, "مدل کالا فرق دارد"
        return min(base, 58), "مدل کالا یکی نیست"
    if shared_models:
        base += min(12, 4 * len(shared_models))

    shorter, longer = sorted((len(sheet_norm), len(product_norm)))
    if longer and shorter / longer < 0.5:
        base -= 12
    if len(overlap) < 2 and not shared_models:
        return min(base, 60), "شباهت اسم کم است"
    if recall < 0.55:
        base = min(base, 72)

    return min(max(base, 0), 96), "تطابق از روی نام"


def match_row(sheet: SheetRow, products: list[Product]) -> MatchResult:
    if sheet.sku:
        code = _code_key(sheet.sku)
        for product in products:
            if _code_key(product.sku) == code or _code_key(product.barcode) == code:
                return MatchResult(sheet, product, 100, "کد کالا یکی است", "update")

    best: tuple[int, Product, str] | None = None
    for product in products:
        score, reason = token_score(sheet.name, product.name)
        if best is None or score > best[0]:
            best = (score, product, reason)

    if best and best[0] >= 88:
        return MatchResult(sheet, best[1], best[0], best[2], "update")
    if best and best[0] >= 74:
        return MatchResult(sheet, None, best[0], "نام نزدیک است؛ تأیید کنید", "suggest", suggested=best[1])
    if sheet.price is None:
        return MatchResult(sheet, None, 0, "قیمت مصرف‌کننده ندارد", "skip")
    return MatchResult(sheet, None, best[0] if best else 0, "روی سایت پیدا نشد", "create")


def match_rows(rows: list[SheetRow], products: list[Product]) -> list[MatchResult]:
    used: set[int] = set()
    results: list[MatchResult] = []
    for sheet in rows:
        available = [item for item in products if id(item) not in used]
        result = match_row(sheet, available)
        chosen = result.product or (result.suggested if result.score >= 88 else None)
        if chosen:
            used.add(id(chosen))
        results.append(result)
    return results
