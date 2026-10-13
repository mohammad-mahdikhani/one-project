from ste.websearch import parse_hits, shop_host


def test_shop_host():
    assert shop_host("https://www.aquasafe.ir/wp-admin") == "aquasafe.ir"


def test_parse_google_style_hits():
    html = """
    <a href="/url?q=https://aquasafe.ir/product/elite">تصفیه آب الیت</a>
    <a href="https://other.com/x">دیگر</a>
    <a href="https://www.aquasafe.ir/lotus">لوتوس آکواجوی</a>
    """
    hits = parse_hits(html, "aquasafe.ir")
    urls = [item.url for item in hits]
    assert any("elite" in url for url in urls)
    assert any("lotus" in url for url in urls)
    assert all("other.com" not in url for url in urls)