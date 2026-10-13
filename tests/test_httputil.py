from ste.httputil import CA_FILE, normalize_shop_url, ssl_context


def test_normalize_shop_url():
    assert normalize_shop_url("aquasafe.ir") == "https://aquasafe.ir"
    assert normalize_shop_url("http://shop.com/wp-admin") == "https://shop.com"
    assert normalize_shop_url("https://shop.com/wp-json/wc/v3/") == "https://shop.com"
    assert normalize_shop_url("  https://shop.com/  ") == "https://shop.com"


def test_bundled_ca_exists():
    assert CA_FILE.is_file()
    ctx = ssl_context()
    assert ctx.check_hostname is True
