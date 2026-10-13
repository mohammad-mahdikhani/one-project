"""Sample site catalog: some codes match the sheet, some only the name, some are missing."""

from __future__ import annotations

from .matcher import Product

# Names are written the way a shop page often stores them — shorter, different order,
# Persian yeh/kaf already normalized, or missing the supplier code.
SITE_PRODUCTS = [
    Product(id=1, sku="01103008", name="تصفیه آب سه مرحله‌ای", price=128000000),
    Product(id=2, sku="", name="دستگاه تصفیه آب آکواجوی ۴۰۱ اکونومی", price=310000000),
    Product(id=3, sku="01105516", name="تصفیه آب آکواجوی مدل 401", price=400000000),
    Product(id=4, sku="", name="دستگاه تصفیه آب آکواجوی الیت ELITE", price=530000000),
    Product(id=5, sku="", name="تصفیه آب آکواجوی لوتوس", price=750000000),
    Product(id=6, sku="01105007", name="دستگاه تصفیه آب لیلیوم آکواجوی", price=980000000),
    Product(id=7, sku="", name="پک فیلتر یخچال HS", price=15000000),
    Product(id=8, sku="01305506", name="فیلتر کربن نهایی آکواجوی LP با اتصال QC", price=12900000),
    Product(id=9, sku="", name="فیلتر الیافی یک میکرون اینلاین ۱۲ اینچ QC", price=21000000),
    Product(id=10, sku="", name="ممبران RO آکواجوی 75GPD ده اینچ", price=55000000),
    Product(id=11, sku="01316002", name="پمپ تصفیه ۵۰ گالن آکواجوی", price=130000000),
    Product(id=12, sku="", name="هوزینگ ۱۰ اینچ آکواجوی با درپوش", price=29000000),
    Product(id=13, sku="01313101", name="TDS متر قلمی آکواجوی", price=20000000),
    Product(id=14, sku="", name="فیلتر هپا تصفیه هوا مدل 2000", price=64000000),
    Product(id=15, sku="02301001", name="فیلتر هوای VOC مدل ۱۰۰۰", price=28000000),
    Product(id=16, sku="99999999", name="دستگاه تصفیه آب صنعتی سفارشی", price=1500000000),
]
