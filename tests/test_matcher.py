from ste.matcher import Product, SheetRow, match_row, match_rows
from ste.normalize import format_money, normalize_name, parse_money
from ste.site_seed import SITE_PRODUCTS


def test_persian_letters_and_money():
    assert normalize_name("شرح كالاي پالستيكي") == "شرح کالای پلاستیکی"
    assert parse_money("132,000,000") == 132000000
    assert format_money(132000000) == "132٬000٬000"


def test_match_by_supplier_code():
    site = [Product(id=1, sku="01103008", name="یک کالای دیگر", price=1)]
    sheet = SheetRow(row=1, sku="01103008", name="دستگاه تصفیه آب سه مرحله ای", price=132000000)
    result = match_row(sheet, site)
    assert result.action == "update"
    assert result.reason == "کد کالا یکی است"


def test_match_elite_by_name_when_code_missing():
    site = [item for item in SITE_PRODUCTS]
    sheet = SheetRow(row=17, sku="01105512", name="دستگاه تصفیه آب آکواجوی مدل الیت (ELITE)", price=546000000)
    result = match_row(sheet, site)
    assert result.action == "update"
    assert "الیت" in result.product.name


def test_match_economy_401_by_name():
    site = [Product(id=1, sku="", name="دستگاه تصفیه آب آکواجوی ۴۰۱ اکونومی", price=1)]
    sheet = SheetRow(row=2, sku="01105559", name="دستگاه تصفیه آب آکواجوی مدل 401 (E) اکونومی", price=325000000)
    result = match_row(sheet, site)
    assert result.action == "update"
    assert result.score >= 90


def test_generic_401_is_not_economy():
    site = [Product(id=1, sku="", name="تصفیه آب آکواجوی مدل 401", price=1)]
    sheet = SheetRow(row=2, sku="01105559", name="دستگاه تصفیه آب آکواجوی مدل 401 (E) اکونومی", price=325000000)
    result = match_row(sheet, site)
    assert result.action == "create"
    assert result.suggested is None


def test_generic_brand_does_not_match_elite():
    site = [Product(id=1, sku="", name="دستگاه تصفیه آب آکواجوی الیت ELITE", price=1)]
    sheet = SheetRow(row=3, sku="", name="دستگاه تصفیه آب آکواجوی", price=400000000)
    result = match_row(sheet, site)
    assert result.action == "create"
    assert result.suggested is None


def test_filter_does_not_match_device():
    site = [Product(id=1, sku="", name="دستگاه تصفیه آب آکواجوی الیت ELITE", price=1)]
    sheet = SheetRow(row=8, sku="", name="فیلتر کربن نهایی آکواجوی LP", price=12900000)
    result = match_row(sheet, site)
    assert result.action == "create"
    assert result.reason == "روی سایت پیدا نشد"


def test_do_not_match_elite_with_lotus():
    site = [Product(id=1, sku="", name="تصفیه آب آکواجوی لوتوس", price=1)]
    sheet = SheetRow(row=17, sku="01105512", name="دستگاه تصفیه آب آکواجوی مدل الیت (ELITE)", price=546000000)
    result = match_row(sheet, site)
    assert result.action != "update"


def test_missing_site_product_is_create():
    site = [Product(id=1, sku="01103008", name="تصفیه آب سه مرحله‌ای", price=1)]
    sheet = SheetRow(row=22, sku="02101005", name="دستگاه تصفیه هوا AJ-3500", price=992000000)
    result = match_row(sheet, site)
    assert result.action == "create"


def test_code_wins_over_similar_names():
    products = [
        Product(id=1, sku="01105516", name="تصفیه آب آکواجوی مدل 401", price=400000000),
        Product(id=2, sku="", name="دستگاه تصفیه آب آکواجوی ۴۰۱ اکونومی", price=310000000),
    ]
    rows = [
        SheetRow(row=2, sku="01105559", name="دستگاه تصفیه آب آکواجوی مدل 401 (E) اکونومی", price=325000000),
        SheetRow(row=4, sku="01105516", name="دستگاه تصفیه آب آکواجوی مدل 401", price=406000000),
    ]
    results = match_rows(rows, products)
    by_sku = {item.sheet.sku: item for item in results}
    assert by_sku["01105516"].product.id == 1
    assert by_sku["01105559"].product.id == 2
