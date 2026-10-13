from ste.matcher import Product, SheetRow, match_row, match_rows
from ste.normalize import format_money, normalize_name, parse_money
from ste.site_seed import SITE_PRODUCTS


def test_persian_letters_and_money():
    assert normalize_name("شرح كالاي پالستيكي") == "شرح کالای پلاستیکی"
    assert parse_money("132,000,000") == 132000000
    assert format_money(132000000) == "132٬000٬000 تومان"
    glued = normalize_name("فیلترالیافی1میکرون10اینچB.B")
    assert "فیلتر الیافی 1" in glued
    assert "bb" in glued
    assert "inline" in normalize_name("فیلتر 10 اینچ IN LINE")


def test_match_by_supplier_code():
    site = [Product(id=1, sku="01103008", name="یک کالای دیگر", price=1)]
    sheet = SheetRow(row=1, sku="01103008", name="دستگاه تصفیه آب سه مرحله ای", price=132000000)
    result = match_row(sheet, site)
    assert result.action == "update"
    assert "کد" in result.reason


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
    assert result.score >= 78


def test_generic_401_is_not_economy():
    site = [Product(id=1, sku="", name="تصفیه آب آکواجوی مدل 401", price=1)]
    sheet = SheetRow(row=2, sku="01105559", name="دستگاه تصفیه آب آکواجوی مدل 401 (E) اکونومی", price=325000000)
    result = match_row(sheet, site)
    assert result.action != "update"


def test_generic_brand_does_not_match_elite():
    site = [Product(id=1, sku="", name="دستگاه تصفیه آب آکواجوی الیت ELITE", price=1)]
    sheet = SheetRow(row=3, sku="", name="دستگاه تصفیه آب آکواجوی", price=400000000)
    result = match_row(sheet, site)
    assert result.action != "update"


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


def test_code_inside_name_matches():
    site = [Product(id=9, sku="01305506", name="فیلتر کربن نهایی", price=1)]
    sheet = SheetRow(row=1, sku="", name="فیلتر کربن نهایی کد 01305506", price=12900000)
    result = match_row(sheet, site)
    assert result.action == "update"


def test_google_hit_matches_shop_url():
    site = [Product(id=4, sku="", name="تصفیه آب آکواجوی الیت", permalink="https://shop.com/elite", slug="elite", price=1)]
    rows = [SheetRow(row=1, sku="", name="آب شیرین کن خانگی فروش ویژه سری جدید", price=100)]
    hits = [type("H", (), {"title": "تصفیه آب آکواجوی الیت", "url": "https://shop.com/elite"})()]
    results = match_rows(rows, site, shop_url="https://shop.com", search=lambda *args, **kwargs: hits)
    assert results[0].action == "update"
    assert results[0].product.id == 4


def test_word_by_word_elite_and_brand():
    site = [Product(id=4, sku="", name="تصفیه آب آکواجوی الیت", price=1)]
    sheet = SheetRow(row=1, sku="", name="دستگاه تصفیه آب آکواجوی مدل الیت( ELITE )", price=546000000)
    result = match_row(sheet, site)
    assert result.action == "update"
    assert result.score >= 78


def test_qc_acronym_matches_hyphen_form():
    site = [Product(id=8, sku="", name="فیلتر کربن نهایی آکواجوی LP با اتصال QC", price=1)]
    sheet = SheetRow(row=1, sku="", name="فیلتر کربن نهایی آکواجوی LP-QC", price=12900000)
    result = match_row(sheet, site)
    assert result.action == "update"


def test_qe_does_not_match_qc():
    site = [Product(id=8, sku="", name="فیلتر کربن نهایی آکواجوی QC", price=1)]
    sheet = SheetRow(row=1, sku="", name="فیلتر کربن نهایی آکواجوی QE", price=12900000)
    result = match_row(sheet, site)
    assert result.action != "update"


def test_glued_bb_filter_matches_site_name():
    site = [Product(id=20, sku="", name="فیلتر الیافی 1 میکرون 10 اینچ BB", price=18000000)]
    sheet = SheetRow(row=1, sku="", name="فیلترالیافی1میکرون10اینچB.B", price=18900000)
    result = match_row(sheet, site)
    assert result.action == "update"
    assert result.product.id == 20


def test_leading_zero_sku_variants_match():
    site = [Product(id=21, sku="01310110", name="ممبران RO آکواجوی 50GPD", price=50000000)]
    sheet = SheetRow(row=1, sku="00131010", name="ممبران RO طول 10 اینچ Aquajoy 50GPD", price=55300000)
    result = match_row(sheet, site)
    assert result.action == "update"
    assert result.product.id == 21


def test_one_micron_does_not_match_five_micron():
    site = [Product(id=22, sku="", name="فیلتر الیافی 5 میکرون 10 اینچ BB", price=17000000)]
    sheet = SheetRow(row=1, sku="", name="فیلتر الیافی1 میکرون10اینچB.B", price=18900000)
    result = match_row(sheet, site)
    assert result.action != "update"


def test_lookup_finds_missing_catalog_sku():
    site = [Product(id=1, sku="01103008", name="تصفیه آب سه مرحله‌ای", price=1)]
    rows = [SheetRow(row=1, sku="01306577", name="فیلتر دوش حمام مشکی", price=12200000)]
    found = [Product(id=33, sku="01306577", name="فیلتر دوش حمام مشکی", price=11000000)]
    results = match_rows(rows, site, lookup=lambda sheet: found)
    assert results[0].action == "update"
    assert results[0].product.id == 33


def test_inline_and_aquajoy_aliases():
    site = [Product(id=24, sku="", name="فیلتر الیافی اینلاین 10 اینچ شفاف", price=14000000)]
    sheet = SheetRow(row=1, sku="", name="فیلتر 10 اینچ IN LINE (شفاف)", price=14100000)
    result = match_row(sheet, site)
    assert result.action == "update"
    assert result.score >= 78
