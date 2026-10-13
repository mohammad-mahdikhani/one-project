from ste.telegram import crawl_channel


def test_demo_channel_does_not_need_network():
    crawled = crawl_channel("demo")
    assert crawled["channel"] == "demo"
    assert any(row.sku == "01103008" for row in crawled["rows"])
