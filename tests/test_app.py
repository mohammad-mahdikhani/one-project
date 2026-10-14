import io
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = tempfile.mkdtemp(prefix="daftarchi-test-")
os.environ["DAFTARCHI_DATA"] = ROOT

import app as appmod  # noqa: E402
from openpyxl import Workbook  # noqa: E402


class DaftarchiTest(unittest.TestCase):
    def setUp(self):
        folder = Path(os.environ["DAFTARCHI_DATA"])
        for path in folder.glob("daftarchi.db*"):
            path.unlink()
        appmod.init_db()
        self.client = appmod.app.test_client()
        self.login()

    def login(self, ident="09120000000", password="daftarchi", client=None):
        client = client or self.client
        response = client.post("/api/auth/login", json={"ident": ident, "password": password})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def open_register(self, opening=0):
        response = self.client.post("/api/register/open", json={"opening_cash": opening})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def add_product(self, **kwargs):
        payload = {"name": "چای", "price": 10000, "stock": 5, "cost": 4000, "barcode": "111"}
        payload.update(kwargs)
        response = self.client.post("/api/products", json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["product"]

    def accounts(self):
        response = self.client.get("/api/accounts")
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertTrue(data["balanced"], data)
        self.assertEqual(data["debit_total"], data["credit_total"])
        return {row["code"]: row for row in data["accounts"]}

    def test_shop_logo_is_saved_for_the_invoice(self):
        logo = "/uploads/" + ("a" * 32) + ".png"
        saved = self.client.put("/api/settings", json={"shop_name": "وب‌بیکری", "shop_logo": logo})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        settings = saved.get_json()["settings"]
        self.assertEqual(settings["shop_name"], "وب‌بیکری")
        self.assertEqual(settings["shop_logo"], logo)
        me = self.client.get("/api/auth/me").get_json()
        self.assertEqual(me["shop"]["name"], "وب‌بیکری")
        self.assertEqual(me["shop"]["logo"], logo)
        rejected = self.client.put("/api/settings", json={"shop_logo": "javascript:alert(1)"})
        self.assertEqual(rejected.status_code, 400, rejected.get_json())

    def test_login_and_health(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.get_json()["name"], "دفترچی")
        bad = self.client.post("/api/auth/login", json={"ident": "09120000000", "password": "wrong"})
        self.assertEqual(bad.status_code, 401)

    def test_sale_discount_stock_and_books(self):
        closed = self.client.post("/api/sales", json={"items": [{"product_id": 1, "qty": 1}], "payment_method": "cash"})
        self.assertEqual(closed.status_code, 400)
        self.open_register(0)
        product = self.add_product()
        nameless = self.client.post("/api/sales", json={
            "items": [{"product_id": product["id"], "qty": 1}],
            "payment_method": "cash",
            "customer_name": "علی",
            "customer_phone": "09121111111",
        })
        self.assertEqual(nameless.status_code, 400, nameless.get_json())
        self.assertIn("نام خانوادگی", nameless.get_json()["error"])
        nophone = self.client.post("/api/sales", json={
            "items": [{"product_id": product["id"], "qty": 1}],
            "payment_method": "cash",
            "customer_first": "علی",
            "customer_last": "رضایی",
        })
        self.assertEqual(nophone.status_code, 400, nophone.get_json())
        self.assertIn("موبایل", nophone.get_json()["error"])
        self.assertEqual(self.client.get("/api/products").get_json()["products"][0]["stock"], 5)
        response = self.client.post("/api/sales", json={
            "items": [{"product_id": product["id"], "qty": 2}],
            "discount_type": "percent",
            "discount_value": 10,
            "payment_method": "cash",
            "customer_first": "علی",
            "customer_last": "رضایی",
            "customer_phone": "۰۹۱۲۱۱۱۱۱۱۱",
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        sale = response.get_json()["sale"]
        self.assertEqual(sale["customer_name"], "علی رضایی")
        self.assertIn("صندوق پیامک", response.get_json()["sms"]["detail"])
        inbox = self.client.get("/api/sms").get_json()["messages"]
        self.assertEqual(inbox[0]["recipient"], "09121111111")
        self.assertIn("خرید حضوری", inbox[0]["body"])
        self.assertIn("18,000", inbox[0]["body"])
        self.assertEqual(sale["subtotal"], 20000)
        self.assertEqual(sale["discount"], 2000)
        self.assertEqual(sale["payable"], 18000)
        self.assertEqual(sale["status"], "paid")
        products = self.client.get("/api/products").get_json()["products"]
        self.assertEqual(products[0]["stock"], 3)
        books = self.accounts()
        self.assertEqual(books["1000"]["amount"], 18000)
        self.assertEqual(books["1000"]["side"], "بدهکار")
        self.assertEqual(books["4000"]["amount"], 20000)
        self.assertEqual(books["4000"]["side"], "بستانکار")
        self.assertEqual(books["4100"]["amount"], 2000)
        self.assertEqual(books["5000"]["amount"], 8000)
        self.assertEqual(books["1200"]["amount"], 8000)
        over = self.client.post("/api/sales", json={"items": [{"product_id": product["id"], "qty": 10}], "payment_method": "cash"})
        self.assertEqual(over.status_code, 400)
        summary = self.client.get("/api/reports/summary").get_json()
        self.assertEqual(summary["day"]["total"], 18000)
        self.assertEqual(summary["week"]["count"], 1)
        self.assertEqual(summary["month"]["count"], 1)
        customers = self.client.get("/api/customers").get_json()["customers"]
        self.assertEqual(customers[0]["phone"], "09121111111")
        self.assertEqual(customers[0]["balance"], 0)

    def test_credit_receipt_purchase_and_close(self):
        self.open_register(100000)
        books = self.accounts()
        self.assertEqual(books["1000"]["amount"], 100000)
        self.assertEqual(books["3000"]["amount"], 100000)
        product = self.add_product(name="قند", price=10000, cost=0, stock=4, barcode="222")
        credit = self.client.post("/api/sales", json={
            "items": [{"product_id": product["id"], "qty": 1}],
            "payment_method": "credit",
            "customer_name": "مریم احمدی",
            "customer_phone": "09123334444",
        })
        self.assertEqual(credit.status_code, 200, credit.get_json())
        customers = self.client.get("/api/customers").get_json()["customers"]
        buyer = next(row for row in customers if row["phone"] == "09123334444")
        self.assertEqual(buyer["balance"], 10000)
        self.assertEqual(buyer["side"], "بدهکار")
        receipt = self.client.post("/api/receipts", json={"account_id": buyer["account_id"], "amount": 4000, "payment_method": "cash"})
        self.assertEqual(receipt.status_code, 200, receipt.get_json())
        buyer = next(row for row in self.client.get("/api/customers").get_json()["customers"] if row["phone"] == "09123334444")
        self.assertEqual(buyer["balance"], 6000)
        purchase = self.client.post("/api/purchases", json={"product_id": product["id"], "qty": 2, "unit_cost": 3000, "pay_code": "1000"})
        self.assertEqual(purchase.status_code, 200, purchase.get_json())
        stock = next(row for row in self.client.get("/api/products").get_json()["products"] if row["id"] == product["id"])
        self.assertEqual(stock["stock"], 5)
        self.assertEqual(stock["cost"], 1200)
        preview = self.client.get("/api/register").get_json()["session"]["figures"]
        self.assertEqual(preview["cash_sales"], 0)
        self.assertEqual(preview["credit_sales"], 10000)
        self.assertEqual(preview["cash_receipts"], 4000)
        self.assertEqual(preview["cash_purchases"], 6000)
        self.assertEqual(preview["expected_cash"], 98000)
        closed = self.client.post("/api/register/close", json={"counted_cash": 97000})
        self.assertEqual(closed.status_code, 200, closed.get_json())
        self.assertEqual(closed.get_json()["difference"], -1000)
        books = self.accounts()
        self.assertEqual(books["1000"]["amount"], 97000)
        self.assertEqual(books["5100"]["amount"], 1000)
        again = self.client.post("/api/sales", json={"items": [{"product_id": product["id"], "qty": 1}], "payment_method": "cash"})
        self.assertEqual(again.status_code, 400)

    def test_trial_lasts_seven_days_then_blocks_sales(self):
        access = self.client.get("/api/auth/me").get_json()["access"]
        self.assertEqual(access["mode"], "trial")
        self.assertTrue(access["active"])
        self.assertEqual(access["days_left"], 7)
        self.assertEqual(access["title"], "۷ روز رایگان")
        again = self.client.get("/api/licenses").get_json()["access"]
        self.assertEqual(again["ends_at"], access["ends_at"])
        import sqlite3
        past = (appmod.now_dt() - appmod.timedelta(days=1)).isoformat(timespec="seconds")
        db = sqlite3.connect(Path(os.environ["DAFTARCHI_DATA"]) / "daftarchi.db")
        db.execute("UPDATE settings SET value=? WHERE key='trial_ends_at'", (past,))
        db.commit()
        db.close()
        product = self.add_product(barcode="trial-block")
        self.open_register(0)
        blocked = self.client.post("/api/sales", json={
            "items": [{"product_id": product["id"], "qty": 1}], "payment_method": "cash",
        })
        self.assertEqual(blocked.status_code, 402, blocked.get_json())
        self.assertIn("رایگان", blocked.get_json()["error"])

    def test_license_cap_and_discount(self):
        self.open_register(0)
        saved = self.client.put("/api/licenses/prices", json={"cap_50y": 1})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        first = self.client.post("/api/licenses", json={
            "plan": "50y", "buyer_name": "فروشگاه الف", "phone": "09120001111",
            "discount_type": "amount", "discount_value": 2000000, "payment_method": "cash",
        })
        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertEqual(first.get_json()["payable"], 10000000)
        second = self.client.post("/api/licenses", json={
            "plan": "50y", "buyer_name": "فروشگاه ب", "phone": "09120002222", "payment_method": "cash",
        })
        self.assertEqual(second.status_code, 400)
        plans = {row["id"]: row for row in self.client.get("/api/licenses").get_json()["plans"]}
        self.assertEqual(plans["3m"]["price"], 6000000)
        self.assertEqual(plans["6m"]["price"], 12000000)
        self.assertEqual(plans["12m"]["price"], 15000000)
        self.assertEqual(plans["50y"]["price"], 12000000)
        self.assertEqual(plans["50y"]["remaining"], 0)
        books = self.accounts()
        self.assertEqual(books["4200"]["amount"], 0)
        self.assertEqual(books["1000"]["amount"], 0)

    def test_archived_barcode_can_be_used_again(self):
        product = self.add_product()
        removed = self.client.delete(f"/api/products/{product['id']}")
        self.assertEqual(removed.status_code, 200)
        again = self.add_product(name="چای تازه", price=45000, stock=10)
        self.assertEqual(again["id"], product["id"])
        self.assertEqual(again["name"], "چای تازه")
        self.assertEqual(again["stock"], 10)
        duplicate = self.client.post("/api/products", json={"name": "دیگر", "price": 1000, "barcode": "111"})
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("بارکد", duplicate.get_json()["error"])

    def test_excel_import_and_archive(self):
        book = Workbook()
        sheet = book.active
        sheet.append(["نام", "کد", "بارکد", "قیمت", "موجودی", "قیمت خرید", "تصویر"])
        sheet.append(["برنج", "RICE", "6261", "۴۵٬۰۰۰", 3, 30000, ""])
        sheet.append(["", "", "", "", "", "", ""])
        sheet.append(["", "X", "1", "abc", 1, 1, ""])
        buf = io.BytesIO()
        book.save(buf)
        buf.seek(0)
        response = self.client.post("/api/products/import", data={"file": (buf, "goods.xlsx")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body["created"], 1)
        self.assertEqual(len(body["errors"]), 1)
        product = self.client.get("/api/products").get_json()["products"][0]
        self.assertEqual(product["price"], 45000)
        self.assertEqual(product["name"], "برنج")
        removed = self.client.delete(f"/api/products/{product['id']}")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.client.get("/api/products").get_json()["products"], [])

    def test_excel_preview_then_save_shop_columns(self):
        book = Workbook()
        sheet = book.active
        sheet.append(["نام کالا", "SKU", "موجودی", "قیمت فروش"])
        sheet.append(["بلوز شلوار دایناسور", 1001, 0, 0])
        sheet.append(["بلوز شلوار تراکتور", 1007, 0, 220000])
        for index in range(3, 41):
            sheet.append([f"کالای {index}", 2000 + index, index, 0])
        buf = io.BytesIO()
        book.save(buf)
        payload = buf.getvalue()
        preview = self.client.post(
            "/api/products/preview",
            data={"file": (io.BytesIO(payload), "Daftarchi-sample.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(preview.status_code, 200, preview.get_json())
        body = preview.get_json()
        self.assertEqual(body["total"], 40)
        self.assertEqual(body["preview"][0]["name"], "بلوز شلوار دایناسور")
        self.assertEqual(body["preview"][0]["sku"], "1001")
        self.assertEqual(body["preview"][0]["price"], 0)
        self.assertEqual(body["preview"][1]["price"], 220000)
        self.assertEqual(self.client.get("/api/products").get_json()["products"], [])
        saved = self.client.post(
            "/api/products/import",
            data={"file": (io.BytesIO(payload), "Daftarchi-sample.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(saved.status_code, 200, saved.get_json())
        result = saved.get_json()
        self.assertEqual(result["created"], 40)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["errors"], [])
        self.assertIn("created", result)
        products = self.client.get("/api/products").get_json()["products"]
        self.assertEqual(len(products), 40)
        tractor = next(item for item in products if item["sku"] == "1007")
        self.assertEqual(tractor["name"], "بلوز شلوار تراکتور")
        self.assertEqual(tractor["price"], 220000)
        again = self.client.post(
            "/api/products/import",
            data={"file": (io.BytesIO(payload), "Daftarchi-sample.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(again.get_json()["updated"], 40)
        self.assertEqual(len(self.client.get("/api/products").get_json()["products"]), 40)

    def test_excel_matches_products_by_name_when_they_have_no_code(self):
        self.add_product(name="عسل کوهی", price=10000, stock=2, sku=None, barcode=None)
        self.add_product(name="پیراهن", price=80000, stock=1, sku="P1", barcode=None)
        book = Workbook()
        sheet = book.active
        sheet.append(["نام کالا", "SKU", "موجودی", "قیمت فروش"])
        sheet.append(["عسل کوهي", None, 4, 45000])
        sheet.append(["عسل‌کوهی", None, 5, 48000])
        sheet.append(["شلوار کتان", None, 1, 1000])
        sheet.append(["شلوار کتان", "", 2, 5000])
        sheet.append(["پیراهن", "P2", 3, 90000])
        buf = io.BytesIO()
        book.save(buf)
        payload = buf.getvalue()
        preview = self.client.post(
            "/api/products/preview",
            data={"file": (io.BytesIO(payload), "names.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(preview.status_code, 200, preview.get_json())
        seen = preview.get_json()
        self.assertEqual(seen["updating"], 3)
        self.assertEqual(seen["creating"], 2)
        saved = self.client.post(
            "/api/products/import",
            data={"file": (io.BytesIO(payload), "names.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(saved.status_code, 200, saved.get_json())
        result = saved.get_json()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["updated"], 3)
        products = self.client.get("/api/products").get_json()["products"]
        self.assertEqual(len(products), 4)
        honey = next(item for item in products if "عسل" in item["name"])
        self.assertEqual(honey["price"], 48000)
        self.assertEqual(honey["stock"], 5)
        self.assertFalse(honey["sku"])
        cotton = next(item for item in products if item["name"] == "شلوار کتان")
        self.assertEqual(cotton["price"], 5000)
        shirts = [item for item in products if item["name"] == "پیراهن"]
        self.assertEqual(sorted(item["sku"] for item in shirts), ["P1", "P2"])

    def test_filter_signatures_keep_air_water_and_bath_apart(self):
        water = appmod.product_marks("فیلتر تصفیه آب ۱۰ اینچ ۵ میکرون")
        plain = appmod.product_marks("فیلتر آب 10 اینچ 5 میکرون")
        self.assertEqual(water["family"], "water")
        self.assertEqual(water["inches"], frozenset({"10"}))
        self.assertEqual(water["microns"], frozenset({"5"}))
        self.assertTrue(appmod.marks_match(water, plain))
        self.assertFalse(appmod.marks_match(water, appmod.product_marks("فیلتر تصفیه هوا ۱۰ اینچ ۵ میکرون")))
        self.assertFalse(appmod.marks_match(water, appmod.product_marks("فیلتر آب ۲۰ اینچ ۵ میکرون")))
        self.assertFalse(appmod.marks_match(water, appmod.product_marks("فیلتر حمام ۱۰ اینچ")))
        self.assertFalse(appmod.marks_match(
            appmod.product_marks("فیلتر آب 10 اینچ 5 میکرون PP"),
            appmod.product_marks("فیلتر آب 10 اینچ 5 میکرون CTO"),
        ))
        self.assertFalse(appmod.marks_match(
            appmod.product_marks("فیلتر آب 10 اینچ 5 میکرون elite"),
            appmod.product_marks("فیلتر آب 10 اینچ 5 میکرون lotus"),
        ))
        self.assertEqual(appmod.product_marks("فیلتر آب نیم اینچ")["inches"], frozenset({"0.5"}))
        self.assertFalse(appmod.marks_match(water, appmod.product_marks("دستگاه تصفیه آب ۱۰ اینچ ۵ میکرون")))
        self.assertEqual(appmod.product_marks("عسل کوهی")["family"], "")
        self.add_product(name="فیلتر آب 10 اینچ 5 میکرون", price=1000, stock=1, sku=None, barcode=None)
        self.add_product(name="فیلتر تصفیه هوا 10 اینچ 5 میکرون", price=2000, stock=1, sku=None, barcode=None)
        self.add_product(name="فیلتر حمام 10 اینچ", price=3000, stock=1, sku=None, barcode=None)
        self.add_product(name="فیلتر آب 10 اینچ 5 میکرون PP", price=4000, stock=1, sku=None, barcode=None)
        self.add_product(name="عسل کوهی", price=5000, stock=1, sku=None, barcode=None)
        book = Workbook()
        sheet = book.active
        sheet.append(["نام کالا", "SKU", "موجودی", "قیمت فروش"])
        sheet.append(["فیلتر تصفیه آب ۱۰ اینچ ۵ میکرون", "W10-5", 6, 9000])
        sheet.append(["فیلتر هوا ۱۰ اینچ ۵ میکرون", "A10-5", 2, 8000])
        sheet.append(["فیلتر آب ۲۰ اینچ ۵ میکرون", "W20-5", 1, 11000])
        sheet.append(["فیلتر حمام ۱۰ اینچ", None, 2, 3500])
        sheet.append(["فیلتر آب 10 اینچ 5 میکرون CTO", "C10", 1, 7000])
        sheet.append(["عسل", None, 1, 1000])
        buf = io.BytesIO()
        book.save(buf)
        payload = buf.getvalue()
        preview = self.client.post(
            "/api/products/preview",
            data={"file": (io.BytesIO(payload), "filters.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(preview.status_code, 200, preview.get_json())
        seen = preview.get_json()
        self.assertEqual(seen["updating"], 3)
        self.assertEqual(seen["creating"], 3)
        saved = self.client.post(
            "/api/products/import",
            data={"file": (io.BytesIO(payload), "filters.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(saved.status_code, 200, saved.get_json())
        result = saved.get_json()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["updated"], 3)
        self.assertEqual(result["created"], 3)
        products = self.client.get("/api/products").get_json()["products"]
        self.assertEqual(len(products), 8)
        matched = next(item for item in products if item["sku"] == "W10-5")
        self.assertEqual(matched["price"], 9000)
        self.assertEqual(matched["stock"], 6)
        self.assertEqual(matched["family"], "water")
        air = next(item for item in products if item["sku"] == "A10-5")
        self.assertEqual(air["family"], "air")
        self.assertEqual(air["price"], 8000)
        bath = next(item for item in products if item["family"] == "bath")
        self.assertEqual(bath["price"], 3500)
        self.assertEqual(bath["stock"], 2)
        pp = next(item for item in products if "PP" in item["name"])
        self.assertEqual(pp["price"], 4000)
        self.assertFalse(pp["sku"])
        cto = next(item for item in products if item["sku"] == "C10")
        self.assertEqual(cto["family"], "water")
        wide = next(item for item in products if item["sku"] == "W20-5")
        self.assertEqual(wide["family"], "water")
        self.assertIn("۲۰", wide["name"])
        honey = [item for item in products if "عسل" in item["name"]]
        self.assertEqual(sorted(item["name"] for item in honey), ["عسل", "عسل کوهی"])
        twin = self.add_product(name="فیلتر تصفیه آب 10 اینچ 5 میکرون خانگی", price=1000, stock=1, sku=None, barcode=None)
        self.assertEqual(twin["family"], "water")
        again = Workbook()
        sheet = again.active
        sheet.append(["نام کالا", "SKU", "موجودی", "قیمت فروش"])
        sheet.append(["فیلتر آب 10 اینچ 5 میکرون سری تازه", None, 1, 12000])
        buf = io.BytesIO()
        again.save(buf)
        ambiguous = self.client.post(
            "/api/products/import",
            data={"file": (io.BytesIO(buf.getvalue()), "ambiguous.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(ambiguous.status_code, 200, ambiguous.get_json())
        self.assertEqual(ambiguous.get_json()["created"], 1)
        self.assertEqual(ambiguous.get_json()["updated"], 0)

    def test_woo_links_the_same_filter_and_writes_the_missing_code(self):
        water = self.add_product(
            name="فیلتر تصفیه آب ۱۰ اینچ ۵ میکرون", price=9000, stock=4,
            sku="W10-5", barcode="6260001", cost=0,
        )
        air = self.add_product(
            name="فیلتر تصفیه هوا ۱۰ اینچ ۵ میکرون", price=8000, stock=2,
            sku="A10-5", barcode="6260002", cost=0,
        )
        wide = self.add_product(
            name="فیلتر آب ۲۰ اینچ ۵ میکرون", price=11000, stock=1,
            sku="W20-5", barcode="6260003", cost=0,
        )
        catalog = [
            {"id": 70, "name": "فیلتر آب 10 اینچ 5 میکرون", "type": "simple", "sku": "", "regular_price": "1000", "stock_quantity": 1},
            {"id": 71, "name": "فیلتر هوا 10 اینچ 5 میکرون", "type": "simple", "sku": "", "regular_price": "1000", "stock_quantity": 1},
            {"id": 72, "name": "فیلتر آب 20 اینچ 1 میکرون", "type": "simple", "sku": "OTHER", "regular_price": "1000", "stock_quantity": 1},
        ]
        seen = {"update": [], "create": []}

        def fake_http(method, url, payload=None, headers=None, form=None, timeout=12):
            if "batch" in url:
                kind = "update" if payload.get("update") else "create"
                seen[kind].extend(payload[kind])
                return 200, {kind: [{"id": item.get("id") or 90, "name": item["name"]} for item in payload[kind]]}
            if "/products?" in url:
                return 200, catalog
            return 200, []

        original = appmod.http_request
        appmod.http_request = fake_http
        try:
            self.client.put("/api/settings", json={
                "wp_url": "https://shop.example",
                "woo_key": "ck",
                "woo_secret": "cs",
            })
            pushed = self.client.post("/api/products/woo/push", json={})
            self.assertEqual(pushed.status_code, 200, pushed.get_json())
            body = pushed.get_json()
            self.assertEqual(body["updated"], 2)
            self.assertEqual(body["created"], 1)
            self.assertEqual(body["failed"], [])
            updates = {item["id"]: item for item in seen["update"]}
            self.assertEqual(set(updates), {70, 71})
            self.assertEqual(updates[70]["sku"], "W10-5")
            self.assertEqual(updates[70]["meta_data"], [{"key": "barcode", "value": "6260001"}])
            self.assertEqual(updates[71]["sku"], "A10-5")
            self.assertEqual(seen["create"][0]["sku"], "W20-5")
            self.assertNotIn("id", seen["create"][0])
            products = {item["id"]: item for item in self.client.get("/api/products").get_json()["products"]}
            self.assertEqual(products[water["id"]]["woo_id"], 70)
            self.assertEqual(products[air["id"]]["woo_id"], 71)
            self.assertEqual(products[wide["id"]]["woo_id"], 90)
        finally:
            appmod.http_request = original

    def test_woo_pull_links_a_coded_filter_without_duplicating_it(self):
        local = self.add_product(
            name="فیلتر آب 10 اینچ 5 میکرون", price=9000, stock=4,
            sku="W10-5", barcode=None, cost=0,
        )
        remote = [
            {"id": 70, "name": "فیلتر تصفیه آب 10 اینچ 5 میکرون", "type": "simple", "sku": "", "regular_price": "9000", "stock_quantity": 4},
            {"id": 71, "name": "فیلتر تصفیه هوا 10 اینچ 5 میکرون", "type": "simple", "sku": "", "regular_price": "8000", "stock_quantity": 1},
            {"id": 72, "name": "فیلتر آب 10 اینچ 5 میکرون", "type": "simple", "sku": "OTHER", "regular_price": "1000", "stock_quantity": 1},
        ]

        def fake_http(method, url, payload=None, headers=None, form=None, timeout=12):
            if "/products?" in url:
                return 200, remote
            return 200, []

        original = appmod.http_request
        appmod.http_request = fake_http
        try:
            self.client.put("/api/settings", json={
                "wp_url": "https://shop.example",
                "woo_key": "ck",
                "woo_secret": "cs",
            })
            pulled = self.client.post("/api/products/woo/pull", json={})
        finally:
            appmod.http_request = original
        self.assertEqual(pulled.status_code, 200, pulled.get_json())
        self.assertEqual(pulled.get_json()["updated"], 1)
        self.assertEqual(pulled.get_json()["imported"], 2)
        products = self.client.get("/api/products").get_json()["products"]
        self.assertEqual(len(products), 3)
        kept = next(item for item in products if item["id"] == local["id"])
        self.assertEqual(kept["woo_id"], 70)
        self.assertEqual(kept["sku"], "W10-5")
        self.assertEqual(kept["family"], "water")
        other = next(item for item in products if item["woo_id"] == 72)
        self.assertEqual(other["sku"], "OTHER")
        self.assertNotEqual(other["id"], local["id"])

    def test_woo_push_keeps_rows_confirmed_before_a_later_failure(self):
        first = self.add_product(name="عسل یک", price=1000, stock=1, sku="H1", barcode="6261001", cost=0)
        second = self.add_product(name="عسل دو", price=2000, stock=1, sku="H2", barcode="6261002", cost=0)
        calls = {"batch": 0}

        def fake_http(method, url, payload=None, headers=None, form=None, timeout=12):
            if "batch" in url:
                calls["batch"] += 1
                if calls["batch"] > 1:
                    raise appmod.AppError("قطع شد", 502)
                return 200, {"create": [{"id": 55, "name": payload["create"][0]["name"]}]}
            return 200, []

        original = appmod.http_request
        appmod.WOO_BATCH = 1
        appmod.http_request = fake_http
        try:
            self.client.put("/api/settings", json={
                "wp_url": "https://shop.example",
                "woo_key": "ck",
                "woo_secret": "cs",
            })
            pushed = self.client.post("/api/products/woo/push", json={})
        finally:
            appmod.WOO_BATCH = 20
            appmod.http_request = original
        self.assertEqual(pushed.status_code, 200, pushed.get_json())
        body = pushed.get_json()
        self.assertEqual(body["created"], 1)
        self.assertEqual(len(body["failed"]), 1)
        products = {item["id"]: item for item in self.client.get("/api/products").get_json()["products"]}
        self.assertEqual(products[first["id"]]["woo_id"], 55)
        self.assertIsNone(products[second["id"]]["woo_id"])

    def test_support_message_reaches_telegram_without_showing_the_token(self):
        token = "123456789:AAHxxxxxxxxxxxxxxxxxxxx"
        rejected = self.client.put("/api/settings", json={"telegram_bot_token": "nope"})
        self.assertEqual(rejected.status_code, 400)
        saved = self.client.put("/api/settings", json={"telegram_bot_token": token, "telegram_chat_id": "۵۵۰۰۱"})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        shown = saved.get_json()["settings"]
        self.assertEqual(shown["telegram_bot_token"], "")
        self.assertEqual(shown["telegram_token_saved"], "1")
        self.assertEqual(shown["telegram_chat_id"], "55001")
        kept = self.client.put("/api/settings", json={"shop_name": "فروشگاه آزمایش"})
        self.assertEqual(kept.get_json()["settings"]["telegram_token_saved"], "1")
        seen = {}

        def deliver(method, url, payload=None, headers=None, form=None, timeout=12):
            seen["url"] = url
            seen["text"] = (payload or {}).get("text")
            seen["chat"] = (payload or {}).get("chat_id")
            return 200, {"ok": True, "result": {"message_id": 9}}

        original = appmod.http_request
        appmod.http_request = deliver
        try:
            sent = self.client.post("/api/support/messages", json={
                "kind": "bug", "body": "صندوق بسته ماند", "page": "pos", "error": "صندوق بسته است",
            })
        finally:
            appmod.http_request = original
        self.assertEqual(sent.status_code, 200, sent.get_json())
        self.assertTrue(sent.get_json()["sent"])
        self.assertIn("api.telegram.org/bot" + token + "/sendMessage", seen["url"])
        self.assertEqual(seen["chat"], "55001")
        self.assertIn("صندوق بسته ماند", seen["text"])
        self.assertIn("1.1.1", seen["text"])
        listed = self.client.get("/api/support/messages").get_json()["messages"]
        self.assertEqual(listed[-1]["body"], "صندوق بسته ماند")
        self.assertEqual(listed[-1]["delivery"], "telegram")
        appmod.http_request = lambda *args, **kwargs: (_ for _ in ()).throw(appmod.AppError("اتصال برقرار نشد", 502))
        try:
            self.client.put("/api/settings", json={"telegram_bot_token": "", "telegram_chat_id": ""})
        finally:
            appmod.http_request = original
        # Empty token is ignored, so clear the chat id only and replace the token by storing a space-skipped value.
        with appmod.connect() as conn:
            conn.execute("DELETE FROM settings WHERE key IN ('telegram_bot_token', 'telegram_chat_id')")
        appmod.http_request = lambda *args, **kwargs: (_ for _ in ()).throw(appmod.AppError("اتصال برقرار نشد", 502))
        try:
            kept_local = self.client.post("/api/support/messages", json={"kind": "chat", "body": "کسی جواب نمی‌دهد"})
        finally:
            appmod.http_request = original
        self.assertEqual(kept_local.status_code, 200, kept_local.get_json())
        self.assertFalse(kept_local.get_json()["sent"])
        self.assertIn("توکن", kept_local.get_json()["detail"])

    def test_password_reset_and_cashier(self):
        forgot = self.client.post("/api/auth/forgot", json={"ident": "09120000000"})
        self.assertEqual(forgot.status_code, 200, forgot.get_json())
        code = forgot.get_json()["preview_code"]
        self.assertRegex(code, r"\d{6}")
        reset = self.client.post("/api/auth/reset", json={"ident": "09120000000", "code": code, "password": "secret1"})
        self.assertEqual(reset.status_code, 200, reset.get_json())
        self.client.post("/api/auth/logout")
        self.login(password="secret1")
        created = self.client.post("/api/users", json={
            "name": "صندوقدار", "phone": "09125556677", "password": "cashier1", "role": "cashier",
        })
        self.assertEqual(created.status_code, 200, created.get_json())
        cashier = appmod.app.test_client()
        self.login("09125556677", "cashier1", cashier)
        denied = cashier.put("/api/settings", json={"low_stock": "2"})
        self.assertEqual(denied.status_code, 403)
        self.open_register(0)
        product = self.add_product(name="شیر", barcode="333", stock=2, price=8000, cost=0)
        sold = cashier.post("/api/sales", json={
            "items": [{"product_id": product["id"], "qty": 1}],
            "payment_method": "cash",
            "customer_name": "صندوق دار",
            "customer_phone": "09124445566",
        })
        self.assertEqual(sold.status_code, 200, sold.get_json())

    def test_manual_journal_must_balance(self):
        accounts = self.accounts()
        cash = next(row["id"] for row in self.client.get("/api/accounts").get_json()["accounts"] if row["code"] == "1000")
        bank = next(row["id"] for row in self.client.get("/api/accounts").get_json()["accounts"] if row["code"] == "1010")
        bad = self.client.post("/api/journal", json={
            "memo": "آزمایش",
            "lines": [{"account_id": cash, "debit": 1000, "credit": 0}, {"account_id": bank, "debit": 0, "credit": 500}],
        })
        self.assertEqual(bad.status_code, 400)
        good = self.client.post("/api/journal", json={
            "memo": "انتقال به بانک",
            "lines": [{"account_id": bank, "debit": 1000, "credit": 0}, {"account_id": cash, "debit": 0, "credit": 1000}],
        })
        self.assertEqual(good.status_code, 200, good.get_json())
        self.accounts()
        self.assertTrue(accounts)

    def test_gateway_and_woo_without_network(self):
        self.open_register(0)
        product = self.add_product(name="عسل", barcode="444", price=20000, stock=2, cost=0)

        def fake_http(method, url, payload=None, headers=None, form=None, timeout=12):
            if url.endswith("/request.json"):
                return 200, {"data": {"code": 100, "authority": "AUTH123"}}
            if url.endswith("/verify.json"):
                return 200, {"data": {"code": 100, "ref_id": 999}}
            if "batch" in url:
                return 200, {"create": [{"id": 55, "name": payload["create"][0]["name"]}]}
            if url.endswith("/wp-json"):
                return 200, {"name": "فروشگاه تست"}
            return 200, []

        original = appmod.http_request
        appmod.http_request = fake_http
        try:
            self.client.put("/api/settings", json={
                "wp_url": "https://shop.example",
                "woo_key": "ck",
                "woo_secret": "cs",
                "gateway_merchant": "merchant",
                "gateway_callback": "https://shop.example/back",
                "gateway": "zarinpal",
            })
            pending = self.client.post("/api/sales", json={
                "items": [{"product_id": product["id"], "qty": 1}],
                "payment_method": "gateway",
                "customer_name": "نگار موسوی",
                "customer_phone": "09125556677",
            })
            self.assertEqual(pending.status_code, 200, pending.get_json())
            sale = pending.get_json()["sale"]
            self.assertEqual(sale["status"], "pending")
            self.assertIn("AUTH123", sale["pay_url"])
            self.assertEqual(self.client.get("/api/products").get_json()["products"][0]["stock"], 2)
            confirmed = self.client.post(f"/api/sales/{sale['id']}/confirm", json={"mode": "verify"})
            self.assertEqual(confirmed.status_code, 200, confirmed.get_json())
            self.assertEqual(confirmed.get_json()["sale"]["status"], "paid")
            self.assertEqual(confirmed.get_json()["sms"]["status"], "internal")
            self.assertIn("09125556677", self.client.get("/api/sms").get_json()["messages"][0]["recipient"])
            self.assertEqual(self.client.get("/api/products").get_json()["products"][0]["stock"], 1)
            pushed = self.client.post("/api/products/woo/push", json={})
            self.assertEqual(pushed.status_code, 200, pushed.get_json())
            self.assertEqual(pushed.get_json()["created"], 1)
            site = self.client.post("/api/settings/test/wp")
            self.assertEqual(site.status_code, 200, site.get_json())
            self.assertIn("فروشگاه تست", site.get_json()["message"])
        finally:
            appmod.http_request = original


    def test_variable_woo_product_stays_one_product(self):
        red = {
            "id": 801, "status": "publish", "sku": "SHIRT-RED", "price": "180000",
            "manage_stock": True, "stock_quantity": 3, "stock_status": "instock",
            "attributes": [
                {"id": 1, "name": "pa_color", "option": "قرمز"},
                {"id": 2, "name": "pa_size", "option": "M"},
            ],
        }
        blue = {
            "id": 802, "status": "publish", "sku": "SHIRT-BLUE", "price": "210000",
            "manage_stock": False, "stock_quantity": None, "stock_status": "instock",
            "attributes": [
                {"id": 1, "name": "رنگ", "option": "آبی"},
                {"id": 2, "name": "سایز", "option": "L"},
            ],
        }
        small = {
            "id": 803, "status": "publish", "sku": "SHIRT-S", "price": "190000",
            "manage_stock": True, "stock_quantity": 0, "stock_status": "outofstock",
            "attributes": [{"id": 2, "name": "سایز", "option": "S"}],
        }
        parent = {
            "id": 80, "name": "پیراهن", "type": "variable", "sku": "SHIRT",
            "price": "180000", "regular_price": "", "manage_stock": False,
            "attributes": [
                {"id": 1, "name": "رنگ", "options": ["قرمز", "آبی"]},
                {"id": 2, "name": "سایز", "options": ["S", "M", "L"]},
            ],
            "variations": [801, 802, 803],
        }
        simple = {
            "id": 81, "name": "عسل", "type": "simple", "sku": "HONEY",
            "regular_price": "20000", "stock_quantity": 4,
        }
        stray = {
            "id": 801, "name": "پیراهن - قرمز", "type": "variation", "sku": "SHIRT-RED",
            "regular_price": "180000", "stock_quantity": 3,
        }
        state = {"variations": [red, blue, small]}
        pushed = {}

        def fake_http(method, url, payload=None, headers=None, form=None, timeout=12):
            if "/variations" in url:
                return 200, state["variations"]
            if "batch" in url:
                pushed["body"] = payload
                kind = "update" if payload.get("update") else "create"
                return 200, {kind: [{"id": item.get("id") or 90, "name": item["name"]} for item in payload[kind]]}
            if "/products?" in url:
                return 200, [parent, simple, stray]
            return 200, []

        original = appmod.http_request
        appmod.http_request = fake_http
        try:
            self.client.put("/api/settings", json={
                "wp_url": "https://shop.example",
                "woo_key": "ck",
                "woo_secret": "cs",
            })
            pulled = self.client.post("/api/products/woo/pull", json={})
            self.assertEqual(pulled.status_code, 200, pulled.get_json())
            self.assertEqual(pulled.get_json()["imported"], 2)
            products = self.client.get("/api/products").get_json()["products"]
            self.assertEqual(sorted(item["name"] for item in products), ["عسل", "پیراهن"])
            shirt = next(item for item in products if item["name"] == "پیراهن")
            self.assertEqual(shirt["type"], "variable")
            self.assertEqual(shirt["stock"], 3)
            self.assertEqual(shirt["price"], 180000)
            self.assertEqual(len(shirt["variations"]), 3)
            labels = {item["label"]: item for item in shirt["variations"]}
            self.assertEqual(labels["رنگ: قرمز · سایز: M"]["stock"], 3)
            self.assertEqual(labels["رنگ: قرمز · سایز: M"]["sku"], "SHIRT-RED")
            self.assertIsNone(labels["رنگ: آبی · سایز: L"]["stock"])
            self.assertFalse(labels["رنگ: آبی · سایز: L"]["tracked"])
            self.assertTrue(labels["رنگ: آبی · سایز: L"]["in_stock"])
            self.assertEqual(labels["سایز: S"]["stock"], 0)
            self.assertFalse(labels["سایز: S"]["in_stock"])
            found = self.client.get("/api/products?q=SHIRT-BLUE").get_json()["products"]
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["name"], "پیراهن")
            self.open_register(0)
            buyer = {"customer_first": "نگار", "customer_last": "موسوی", "customer_phone": "09125556677"}
            missing = self.client.post("/api/sales", json={
                "items": [{"product_id": shirt["id"], "qty": 1}],
                "payment_method": "cash",
                **buyer,
            })
            self.assertEqual(missing.status_code, 400, missing.get_json())
            self.assertIn("نوع متغیر", missing.get_json()["error"])
            red_id = labels["رنگ: قرمز · سایز: M"]["id"]
            sold = self.client.post("/api/sales", json={
                "items": [{"product_id": shirt["id"], "variation_id": red_id, "qty": 2}],
                "payment_method": "cash",
                **buyer,
            })
            self.assertEqual(sold.status_code, 200, sold.get_json())
            self.assertEqual(sold.get_json()["items"][0]["name"], "پیراهن — رنگ: قرمز · سایز: M")
            self.assertEqual(sold.get_json()["items"][0]["unit_price"], 180000)
            fresh = next(item for item in self.client.get("/api/products").get_json()["products"] if item["id"] == shirt["id"])
            red_now = next(item for item in fresh["variations"] if item["id"] == red_id)
            self.assertEqual(red_now["stock"], 1)
            self.assertEqual(fresh["stock"], 1)
            blocked = self.client.post("/api/sales", json={
                "items": [{"product_id": shirt["id"], "variation_id": labels["سایز: S"]["id"], "qty": 1}],
                "payment_method": "cash",
                **buyer,
            })
            self.assertEqual(blocked.status_code, 400, blocked.get_json())
            blue_id = labels["رنگ: آبی · سایز: L"]["id"]
            open_stock = self.client.post("/api/sales", json={
                "items": [{"product_id": shirt["id"], "variation_id": blue_id, "qty": 1}],
                "payment_method": "cash",
                **buyer,
            })
            self.assertEqual(open_stock.status_code, 200, open_stock.get_json())
            after_open = next(item for item in self.client.get("/api/products").get_json()["products"] if item["id"] == shirt["id"])
            self.assertEqual(after_open["stock"], 1)
            self.assertIsNone(next(item for item in after_open["variations"] if item["id"] == blue_id)["stock"])
            state["variations"] = [{**red, "stock_quantity": 5}]
            again = self.client.post("/api/products/woo/pull", json={})
            self.assertEqual(again.status_code, 200, again.get_json())
            self.assertEqual(again.get_json()["updated"], 2)
            latest = next(item for item in self.client.get("/api/products").get_json()["products"] if item["id"] == shirt["id"])
            self.assertEqual(len(latest["variations"]), 1)
            self.assertEqual(latest["variations"][0]["label"], "رنگ: قرمز · سایز: M")
            self.assertEqual(latest["variations"][0]["stock"], 5)
            self.assertEqual(latest["stock"], 5)
            adjusted = self.client.post("/api/inventory/adjust", json={
                "product_id": f"{shirt['id']}:{latest['variations'][0]['id']}",
                "stock": 9,
            })
            self.assertEqual(adjusted.status_code, 200, adjusted.get_json())
            counted = next(item for item in self.client.get("/api/products").get_json()["products"] if item["id"] == shirt["id"])
            self.assertEqual(counted["variations"][0]["stock"], 9)
            self.assertEqual(counted["stock"], 9)
            parent_only = self.client.post("/api/inventory/adjust", json={"product_id": shirt["id"], "stock": 1})
            self.assertEqual(parent_only.status_code, 400, parent_only.get_json())
            sent = self.client.post("/api/products/woo/push", json={})
            self.assertEqual(sent.status_code, 200, sent.get_json())
            self.assertEqual(sent.get_json()["skipped"], 1)
            self.assertEqual(sent.get_json()["updated"], 1)
            self.assertEqual(pushed["body"]["update"][0]["name"], "عسل")
            self.assertEqual(pushed["body"]["update"][0]["type"], "simple")
            self.assertNotIn("create", pushed["body"])
        finally:
            appmod.http_request = original

    def test_woo_oauth_signature_matches_woocommerce(self):
        params = {
            "per_page": "1",
            "oauth_consumer_key": "ck_test",
            "oauth_timestamp": "1700000000",
            "oauth_nonce": "abc123",
            "oauth_signature_method": "HMAC-SHA256",
        }
        signature = appmod.woo_oauth_signature(
            "GET", "https://aquasafe.ir/wp-json/wc/v3/products", params, "cs_test",
        )
        self.assertEqual(signature, "Ivb/iWSAiLzYWBlo7+hIvtGWyyAnmK9LaxdKaW1cAQ8=")

    def test_woo_test_uses_the_typed_shop_and_retries_auth(self):
        seen = []
        oauth_ok = {"value": False}

        def fake_http(method, url, payload=None, headers=None, form=None, timeout=12):
            import base64
            seen.append((url, headers or {}, timeout))
            auth = (headers or {}).get("Authorization", "")
            if "oauth_consumer_key=ck_live" in url:
                if oauth_ok["value"]:
                    return 200, [{"id": 7, "name": "فیلتر"}]
                return 401, {"code": "woocommerce_rest_authentication_error", "message": "کلید مصرف کننده نامعتبر است"}
            if auth.startswith("Basic "):
                decoded = base64.b64decode(auth.split()[1]).decode()
                if decoded == "ck_live:cs_live":
                    return 200, [{"id": 7, "name": "فیلتر"}]
                return 401, {"code": "woocommerce_rest_authentication_error", "message": "کلید API نامعتبر است"}
            if "consumer_key=ck_live" in url:
                return 401, {"code": "woocommerce_rest_cannot_view", "message": "متاسفیم ، شما اجازه مشاهده لیست منابع را ندارید."}
            if url.endswith("/wp-json/") or url.endswith("/wp-json"):
                return 200, {"name": "فروشگاه آکواسیف"}
            return 404, {"message": "پیدا نشد"}

        original = appmod.http_request
        appmod.http_request = fake_http
        try:
            self.client.put("/api/settings", json={
                "wp_url": "https://old.example",
                "woo_key": "ck_old",
                "woo_secret": "cs_old",
            })
            denied = self.client.post("/api/settings/test/woo", json={
                "wp_url": "https://aquasafe.ir/",
                "woo_key": "ck_live",
                "woo_secret": "",
            })
            self.assertEqual(denied.status_code, 502, denied.get_json())
            self.assertIn("کلید مصرف کننده نامعتبر است", denied.get_json()["error"])
            self.assertNotIn("اجازه مشاهده", denied.get_json()["error"])
            oauth_ok["value"] = True
            before = len(seen)
            connected = self.client.post("/api/settings/test/woo", json={
                "wp_url": "https://aquasafe.ir/",
                "woo_key": "ck_live",
                "woo_secret": "cs_live",
            })
            self.assertEqual(connected.status_code, 200, connected.get_json())
            self.assertIn("اتصال ووکامرس برقرار است", connected.get_json()["message"])
            tried = seen[before:]
            self.assertTrue(any("consumer_key=ck_live" in url and "oauth_" not in url for url, _headers, _timeout in tried))
            self.assertTrue(any("oauth_signature=" in url and "oauth_consumer_key=ck_live" in url for url, _headers, _timeout in tried))
            self.assertTrue(any(url.startswith("https://aquasafe.ir/wp-json/wc/v3/products?") for url, _headers, _timeout in tried))
            saved = self.client.get("/api/settings").get_json()["settings"]
            self.assertEqual(saved["wp_url"], "https://old.example")
            self.assertEqual(saved["woo_key"], "ck_old")
            site = self.client.post("/api/settings/test/wp", json={"wp_url": "https://aquasafe.ir"})
            self.assertEqual(site.status_code, 200, site.get_json())
            self.assertIn("فروشگاه آکواسیف", site.get_json()["message"])
        finally:
            appmod.http_request = original

    def test_license_pays_through_zibal(self):
        calls = []

        def fake_http(method, url, payload=None, headers=None, form=None, timeout=12):
            calls.append((method, url, payload))
            if str(url).endswith("/pay.php") and payload and payload.get("action") == "request":
                self.assertEqual(payload["key"], "daftarchi-webakery-mail")
                self.assertEqual(payload["callbackUrl"], "https://webakery.ir")
                self.assertEqual(payload["amount"], 60000000)
                self.assertIn("webakery.ir", payload["description"])
                self.assertTrue(str(url).startswith("https://webakery.ir/license-server/"))
                return 200, {
                    "ok": True, "service": "daftarchi-pay", "result": 100,
                    "trackId": 998877, "payUrl": "https://gateway.zibal.ir/start/998877",
                }
            if str(url).endswith("/pay.php") and payload and payload.get("action") == "verify":
                self.assertEqual(payload["trackId"], 998877)
                return 200, {"ok": True, "service": "daftarchi-pay", "result": 100, "refNumber": "445566"}
            if url.endswith("/wp-json"):
                return 500, None
            if url.endswith("/wp-login.php"):
                return 200, {"raw": "<title>ورود وردپرس</title>"}
            return 200, []

        original = appmod.http_request
        appmod.http_request = fake_http
        try:
            self.client.put("/api/settings", json={
                "gateway_sandbox": "1", "gateway": "zarinpal", "gateway_merchant": "",
            })
            pending = self.client.post("/api/licenses", json={
                "plan": "3m", "buyer_name": "فروشگاه وب", "phone": "09123334455", "payment_method": "gateway",
            })
            self.assertEqual(pending.status_code, 200, pending.get_json())
            lic = pending.get_json()["license"]
            self.assertEqual(lic["status"], "pending")
            self.assertEqual(lic["gateway"], "zibal")
            self.assertIn("gateway.zibal.ir/start/998877", lic["pay_url"])
            self.assertEqual(self.accounts()["4200"]["amount"], 0)
            returned = self.client.get("/pay/return?trackId=998877&success=1&status=2")
            self.assertEqual(returned.status_code, 200)
            self.assertIn("فعال", returned.get_data(as_text=True))
            books = self.accounts()
            self.assertEqual(books["4200"]["amount"], 0)
            self.assertEqual(books["1020"]["amount"], 0)
            self.assertEqual(books["1000"]["amount"], 0)
            listed = self.client.get("/api/licenses").get_json()["licenses"]
            self.assertEqual(listed[0]["status"], "paid")
            self.assertEqual(listed[0]["gateway_ref"], "445566")
            site = self.client.post("/api/settings/test/wp")
            self.assertEqual(site.status_code, 200, site.get_json())
            self.assertIn("وردپرس", site.get_json()["message"])

            def rejected(method, url, payload=None, headers=None, form=None, timeout=12):
                if str(url).endswith("/pay.php"):
                    return 502, {"ok": False, "error": "invalid IP 203.0.113.8"}
                return 200, []

            appmod.http_request = rejected
            denied = self.client.post("/api/licenses", json={
                "plan": "6m", "buyer_name": "بدون آی‌پی", "phone": "09120001111", "payment_method": "gateway",
            })
            self.assertEqual(denied.status_code, 502)
            self.assertIn("203.0.113.8", denied.get_json()["error"])
            self.assertIn("هاست", denied.get_json()["error"])
            rows = self.client.get("/api/licenses").get_json()["licenses"]
            self.assertTrue(all(row["buyer_name"] != "بدون آی‌پی" or row["status"] == "canceled" for row in rows))
        finally:
            appmod.http_request = original
        self.assertTrue(calls)


    def test_gmail_signup_sends_code_and_blocks_login(self):
        refused = self.client.post("/api/auth/register", json={
            "name": "نگار", "phone": "09121112222", "email": "negar@yahoo.com", "password": "secret1",
        })
        self.assertEqual(refused.status_code, 400)
        self.assertIn("جیمیل", refused.get_json()["error"])
        original = appmod.http_request
        appmod.http_request = lambda *args, **kwargs: (_ for _ in ()).throw(appmod.AppError("اتصال برقرار نشد", 502))
        try:
            offline = self.client.post("/api/auth/register", json={
                "name": "نگار", "phone": "09121112222", "email": "negar@gmail.com", "password": "secret1",
            })
            self.assertEqual(offline.status_code, 502, offline.get_json())
            self.assertIn("هاست", offline.get_json()["error"])
        finally:
            appmod.http_request = original

        inbox = []

        def host_mail(method, url, payload=None, headers=None, form=None, timeout=12):
            if url == appmod.HOST_MAIL_URL:
                if method == "GET":
                    return 200, {"ok": True, "service": "daftarchi-mail"}
                self.assertEqual(payload["key"], appmod.HOST_MAIL_KEY)
                self.assertTrue(str(payload["to"]).endswith("@gmail.com"))
                inbox.append(payload)
                return 200, {"ok": True, "service": "daftarchi-mail"}
            raise appmod.AppError("unexpected url", 502)

        original = appmod.http_request
        appmod.http_request = host_mail
        try:
            created = self.client.post("/api/auth/register", json={
                "name": "نگار دوم", "phone": "09123334455", "email": "negar2@gmail.com", "password": "secret1",
            })
            self.assertEqual(created.status_code, 200, created.get_json())
            self.assertTrue(created.get_json()["needs_verify"])
            self.assertEqual(created.get_json()["email"], "negar2@gmail.com")
            self.assertIsNone(created.get_json().get("preview_code"))
            self.assertEqual(inbox[-1]["to"], "negar2@gmail.com")
            code = "".join(ch for ch in inbox[-1]["text"] if ch.isdigit())[:6]
            self.assertRegex(code, r"\d{6}")

            self.client.post("/api/auth/logout")
            blocked = self.client.post("/api/auth/login", json={"ident": "negar2@gmail.com", "password": "secret1"})
            self.assertEqual(blocked.status_code, 403, blocked.get_json())
            self.assertTrue(blocked.get_json()["needs_verify"])
            blocked_phone = self.client.post("/api/auth/login", json={"ident": "09123334455", "password": "secret1"})
            self.assertEqual(blocked_phone.status_code, 403)
            wrong = self.client.post("/api/auth/verify", json={"ident": "negar2@gmail.com", "code": "000000"})
            self.assertEqual(wrong.status_code, 400)
            verified = self.client.post("/api/auth/verify", json={"ident": "negar2@gmail.com", "code": code})
            self.assertEqual(verified.status_code, 200, verified.get_json())
            self.login("negar2@gmail.com", "secret1")
            self.client.post("/api/auth/logout")
            forgot = self.client.post("/api/auth/forgot", json={"ident": "negar2@gmail.com"})
            self.assertEqual(forgot.status_code, 200, forgot.get_json())
            self.assertIsNone(forgot.get_json()["preview_code"])
            self.assertEqual(forgot.get_json()["delivery"], "email")
            reset_code = "".join(ch for ch in inbox[-1]["text"] if ch.isdigit())[:6]
            reset = self.client.post("/api/auth/reset", json={
                "ident": "negar2@gmail.com", "code": reset_code, "password": "secret2",
            })
            self.assertEqual(reset.status_code, 200, reset.get_json())
            self.login("negar2@gmail.com", "secret2")
        finally:
            appmod.http_request = original

    def test_signup_needs_host_mail(self):
        original = appmod.http_request
        appmod.http_request = lambda *args, **kwargs: (_ for _ in ()).throw(appmod.AppError("اتصال برقرار نشد", 502))
        try:
            created = self.client.post("/api/auth/register", json={
                "name": "محمد", "phone": "09373211344", "email": "mhm.worker@gmail.com", "password": "secret1",
            })
            self.assertEqual(created.status_code, 502, created.get_json())
            self.assertIn("هاست", created.get_json()["error"])
        finally:
            appmod.http_request = original
        inbox = []

        def host_mail(method, url, payload=None, headers=None, form=None, timeout=12):
            if url == appmod.HOST_MAIL_URL:
                if method == "GET":
                    return 200, {"ok": True, "service": "daftarchi-mail"}
                inbox.append(payload)
                return 200, {"ok": True, "service": "daftarchi-mail"}
            raise appmod.AppError("unexpected url", 502)

        original = appmod.http_request
        appmod.http_request = host_mail
        try:
            sent = self.client.post("/api/auth/register", json={
                "name": "محمد", "phone": "9373211344", "email": "mhm.worker@gmail.com", "password": "secret1",
            })
            self.assertEqual(sent.status_code, 200, sent.get_json())
            self.assertTrue(sent.get_json()["needs_verify"])
            self.assertEqual(inbox[-1]["to"], "mhm.worker@gmail.com")
            code = "".join(ch for ch in inbox[-1]["text"] if ch.isdigit())[:6]
            verified = self.client.post("/api/auth/verify", json={"ident": "mhm.worker@gmail.com", "code": code})
            self.assertEqual(verified.status_code, 200, verified.get_json())
            self.login("mhm.worker@gmail.com", "secret1")
            me = self.client.get("/api/auth/me").get_json()["user"]
            self.assertEqual(me["role"], "admin")
            self.assertEqual(me["phone"], "09373211344")
        finally:
            appmod.http_request = original

    def test_admin_attaches_gmail_without_losing_phone_login(self):
        inbox = []

        def host_mail(method, url, payload=None, headers=None, form=None, timeout=12):
            if url == appmod.HOST_MAIL_URL:
                inbox.append(payload or {})
                return 200, {"ok": True, "service": "daftarchi-mail"}
            raise appmod.AppError("unexpected url", 502)

        original = appmod.http_request
        appmod.http_request = host_mail
        try:
            attached = self.client.post("/api/auth/email", json={"email": "owner@gmail.com"})
            self.assertEqual(attached.status_code, 200, attached.get_json())
            self.assertTrue(attached.get_json()["needs_verify"])
            me = self.client.get("/api/auth/me").get_json()["user"]
            self.assertEqual(me["email"], "owner@gmail.com")
            self.assertEqual(me["email_verified"], 0)
            self.client.post("/api/auth/logout")
            still = self.client.post("/api/auth/login", json={"ident": "09120000000", "password": "daftarchi"})
            self.assertEqual(still.status_code, 403, still.get_json())
            self.assertTrue(still.get_json()["needs_verify"])
            gmail = self.client.post("/api/auth/login", json={"ident": "owner@gmail.com", "password": "daftarchi"})
            self.assertEqual(gmail.status_code, 403)
            self.assertTrue(gmail.get_json()["needs_verify"])
            code = "".join(ch for ch in inbox[-1]["text"] if ch.isdigit())[:6]
            verified = self.client.post("/api/auth/verify", json={"ident": "owner@gmail.com", "code": code})
            self.assertEqual(verified.status_code, 200, verified.get_json())
            self.client.post("/api/auth/logout")
            self.login("owner@gmail.com", "daftarchi")
        finally:
            appmod.http_request = original

    def test_update_manifest_from_webakery_folder(self):
        original = appmod.http_request

        def newer(method, url, payload=None, headers=None, form=None, timeout=12):
            self.assertEqual(url, "https://webakery.ir/daftarchi/version.json")
            self.assertLessEqual(timeout, 4)
            return 200, {
                "version": "1.2.0",
                "url": "https://webakery.ir/daftarchi/Daftarchi-Setup.exe",
                "notes": "رفع ورود",
            }

        def offline(method, url, payload=None, headers=None, form=None, timeout=12):
            raise appmod.AppError("اتصال برقرار نشد", 502)

        def current(method, url, payload=None, headers=None, form=None, timeout=12):
            return 200, {"version": appmod.APP_VERSION, "url": "https://webakery.ir/daftarchi/Daftarchi-Setup.exe"}

        try:
            appmod.http_request = newer
            body = self.client.get("/api/update").get_json()
            self.assertEqual(body["current"], appmod.APP_VERSION)
            self.assertTrue(body["update"])
            self.assertTrue(body["available"])
            self.assertEqual(body["url"], "https://webakery.ir/daftarchi/Daftarchi-Setup.exe")
            self.assertEqual(body["notes"], "رفع ورود")
            appmod.http_request = current
            same = self.client.get("/api/update").get_json()
            self.assertFalse(same["update"])
            self.assertTrue(same["available"])
            appmod.http_request = offline
            down = self.client.get("/api/update").get_json()
            self.assertFalse(down["available"])
            self.assertFalse(down["update"])
            self.assertEqual(down["manifest"], "https://webakery.ir/daftarchi/version.json")
        finally:
            appmod.http_request = original

    def test_installer_overlays_existing_install(self):
        self.assertEqual(appmod.APP_VERSION, "1.1.1")
        self.assertIn("--app=", Path("/workspace/windows/launcher.py").read_text(encoding="utf-8"))
        bat = Path("/workspace/windows/دفترچی.bat").read_text(encoding="utf-8")
        self.assertIn("pythonw.exe", bat)
        self.assertIn("DAFTARCHI_DATA", bat)
        self.assertNotIn("Daftarchi-Setup", bat)
        script = Path("/workspace/static/js/app.js").read_text(encoding="utf-8")
        self.assertIn("۷ روز رایگان فعال است", script)
        self.assertIn("async function buyLicense", script)
        self.assertIn('payment_method: "gateway"', script)
        self.assertIn("popup.location.href = url", script)
        text = Path("/workspace/windows/installer/installer.nsi").read_text(encoding="utf-8")
        self.assertNotIn("MUI_PAGE_DIRECTORY", text)
        self.assertIn("Call StopDaftarchi", text)
        self.assertIn('RMDir /r "$INSTDIR\\static"', text)
        self.assertIn('RMDir /r "$INSTDIR\\windows"', text)
        self.assertNotIn('RMDir /r "$INSTDIR\\data"', text)
        self.assertIn("پوشه data اگر فروش داشته باشد خالی نیست و پاک نمی‌شود", text)
        self.assertIn("همان نسخه را به‌روز می‌کند", text)
        run = Path("/workspace/windows/installer/run.nsi").read_text(encoding="utf-8")
        self.assertIn('OutFile "Daftarchi.exe"', run)
        self.assertIn("SilentInstall silent", run)
        self.assertNotIn("MUI_PAGE", run)
        self.assertNotIn('RMDir /r "$INSTDIR\\data"', run)
        self.assertIn("Call LaunchApp", run)
        self.assertIn("1.1.1", run)
        self.assertIn("invoice-edge", script)
        self.assertIn("نوع متغیر را انتخاب کنید", script)
        self.assertIn("همین مقدارهای نوشته‌شده", script)
        self.assertIn("کادر Consumer key خالی است", script)
        self.assertIn("class=\"webapp\"", script)
        self.assertIn("data-act=\"more\"", script)
        self.assertIn("data-act=\"commit-import\"", script)
        self.assertIn("نام کالا", script)
        self.assertIn("با نام یا کد قبلی", script)
        self.assertIn("ارسال به تلگرام", script)
        self.assertIn("گزارش این خطا", script)
        self.assertIn("data-act=\"check-update\"", script)
        self.assertIn("data-act=\"catalog-filter\"", script)
        self.assertIn("تصفیه هوا", script)
        page = Path("/workspace/templates/index.html").read_text(encoding="utf-8")
        self.assertIn("/manifest.webmanifest", page)
        self.assertIn("/sw.js", page)
        self.assertIn("var-line", script)
        self.assertIn("لوگوی سایت", script)
        self.assertIn("buyer-first", script)
        self.assertIn("خرید حضوری بدون نام", script)
        self.assertIn("ارسال به سامانه مودیان", script)
        self.assertIn("moadian_sandbox", script)
        stop = Path("/workspace/windows/installer/stop-daftarchi.ps1").read_text(encoding="utf-8")
        self.assertIn("Stop-Process", stop)
        mail = Path("/workspace/site-updates/daftarchi/mail.php").read_text(encoding="utf-8")
        self.assertIn("daftarchi-mail", mail)
        self.assertIn("wp_mail", mail)
        original = appmod.http_request
        appmod.http_request = lambda *args, **kwargs: (200, {"ok": True, "service": "daftarchi-mail"})
        try:
            boot = self.client.get("/api/auth/bootstrap").get_json()
        finally:
            appmod.http_request = original
        self.assertEqual(boot["version"], "1.1.1")
        home = self.client.get("/")
        self.assertIn("manifest.webmanifest", home.get_data(as_text=True))
        manifest = json.loads(self.client.get("/manifest.webmanifest").get_data(as_text=True))
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["dir"], "rtl")
        self.assertEqual(manifest["name"], "دفترچی")
        worker = self.client.get("/sw.js")
        self.assertEqual(worker.status_code, 200)
        self.assertIn("daftarchi-1.1.1", worker.get_data(as_text=True))
        relay = Path("/workspace/site-updates/daftarchi/telegram.php").read_text(encoding="utf-8")
        self.assertIn("daftarchi-telegram", relay)
        self.assertIn("telegram.json", relay)
        pay = Path("/workspace/site-updates/daftarchi/pay.php").read_text(encoding="utf-8")
        self.assertIn("daftarchi-pay", pay)
        self.assertIn("gateway.zibal.ir/v1/request", pay)
        self.assertTrue(boot["host_mail"])

    def test_moadian_sends_encrypted_invoice_without_touching_books(self):
        import base64
        import json
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import moadian

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        public_pem = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        public_body = "".join(line for line in public_pem.splitlines() if "-----" not in line)
        saved = self.client.put("/api/settings", json={
            "moadian_fiscal_id": "A1B2C3",
            "moadian_economic_code": "12345678901",
            "moadian_private_key": private_pem,
            "moadian_enabled": "1",
            "moadian_sandbox": "1",
            "moadian_vat": "10",
        })
        self.assertEqual(saved.status_code, 200, saved.get_json())
        hidden = saved.get_json()["settings"]
        self.assertEqual(hidden["moadian_private_key"], "")
        self.assertEqual(hidden["moadian_key_saved"], "1")
        self.assertNotIn("PRIVATE KEY", json.dumps(hidden))
        bad_fiscal = self.client.put("/api/settings", json={"moadian_fiscal_id": "ABC"})
        self.assertEqual(bad_fiscal.status_code, 400)
        bad_product = self.client.post("/api/products", json={"name": "خراب", "price": 1000, "stock": 1, "tax_code": "123"})
        self.assertEqual(bad_product.status_code, 400)

        when = appmod.datetime(2026, 10, 13, 0, 30, tzinfo=appmod.TEHRAN)
        taxid = moadian.generate_tax_id("A1B2C3", when, 7)
        self.assertEqual(len(taxid), 22)
        self.assertTrue(taxid.startswith("A1B2C3"))
        self.assertEqual(taxid[11:21], moadian.invoice_serial_hex(7))
        decimal = moadian.fiscal_to_number("A1B2C3") + f"{(when.date() - appmod.datetime(1970, 1, 1).date()).days:06d}" + f"{7:012d}"
        self.assertTrue(moadian.verhoeff_valid(decimal + taxid[-1]))
        self.assertEqual(moadian.normalize_json({"a": None, "b": ""}), "###")

        self.open_register(0)
        plain = self.add_product(name="بدون شناسه", barcode="222", price=5000)
        coded = self.add_product(name="چای", barcode="333", price=10000, tax_code="2902230386252")
        skipped = self.client.post("/api/sales", json={
            "items": [{"product_id": plain["id"], "qty": 1}],
            "payment_method": "cash",
            "customer_name": "علی رضایی",
            "customer_phone": "09120001122",
        })
        self.assertEqual(skipped.status_code, 200, skipped.get_json())
        self.assertEqual(skipped.get_json()["sale"]["status"], "paid")
        self.assertEqual(skipped.get_json()["sale"]["moadian_status"], "skipped")
        self.assertIn("شناسه کالا", skipped.get_json()["sale"]["moadian_error"])

        calls = []
        original = appmod.http_request
        real_random = moadian.os.urandom

        def fixed_random(size):
            if size == 32:
                return b"\x11" * 32
            if size == 16:
                return b"\x22" * 16
            return real_random(size)

        def fake(method, url, payload=None, headers=None, form=None, timeout=12):
            calls.append((url, payload, headers))
            self.assertTrue(url.startswith("https://sandboxrc.tax.gov.ir/req/api/self-tsp/"))
            if url.endswith("/sync/GET_SERVER_INFORMATION"):
                self.assertEqual(payload["signature"], "")
                self.assertNotIn("Authorization", headers or {})
                return 200, {"result": {"data": {"publicKeys": [{"id": "org-key", "key": public_body}]}}}
            if url.endswith("/sync/GET_TOKEN"):
                self.assertTrue(payload["signature"])
                self.assertNotIn("Authorization", headers or {})
                return 200, {"result": {"data": {"token": "session-token"}}}
            if url.endswith("/async/normal-enqueue"):
                self.assertEqual(headers.get("Authorization"), "Bearer session-token")
                packet = payload["packets"][0]
                self.assertEqual(packet["packetType"], "INVOICE.V01")
                self.assertEqual(packet["fiscalId"], "A1B2C3")
                self.assertEqual(packet["encryptionKeyId"], "org-key")
                self.assertTrue(packet["dataSignature"])
                wrapped = base64.b64decode(packet["symmetricKey"])
                key_hex = key.decrypt(
                    wrapped,
                    padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
                ).decode()
                raw_key = bytes.fromhex(key_hex)
                blob = base64.b64decode(packet["data"])
                xored = AESGCM(raw_key).decrypt(bytes.fromhex(packet["iv"]), blob, None)
                plain_text = bytes(byte ^ raw_key[index % len(raw_key)] for index, byte in enumerate(xored))
                invoice = json.loads(plain_text)
                self.assertEqual(invoice["header"]["inty"], 2)
                self.assertEqual(invoice["header"]["inp"], 1)
                self.assertEqual(invoice["body"][0]["sstid"], "2902230386252")
                self.assertEqual(invoice["body"][0]["fee"], 100000)
                self.assertEqual(invoice["body"][0]["vra"], 10)
                self.assertEqual(invoice["body"][0]["vam"], 10000)
                self.assertEqual(invoice["header"]["tbill"], 110000)
                self.assertEqual(invoice["payments"][0]["pmt"], 3)
                self.assertEqual(len(invoice["header"]["taxid"]), 22)
                self.assertEqual(invoice["header"]["inno"], invoice["header"]["taxid"][11:21])
                return 200, {"result": [{"uid": packet["uid"], "referenceNumber": "ref-100", "errorCode": None}]}
            if url.endswith("/sync/INQUIRY_BY_REFERENCE_NUMBER"):
                return 200, {"result": {"data": [{"status": "SUCCESS", "data": {"success": True, "error": []}}]}}
            self.fail(url)

        moadian.os.urandom = fixed_random
        appmod.http_request = fake
        try:
            sent = self.client.post("/api/sales", json={
                "items": [{"product_id": coded["id"], "qty": 1}],
                "payment_method": "cash",
                "customer_name": "علی رضایی",
                "customer_phone": "09120001122",
            })
            self.assertEqual(sent.status_code, 200, sent.get_json())
            sale = sent.get_json()["sale"]
            self.assertEqual(sale["status"], "paid")
            self.assertEqual(sale["payable"], 10000)
            self.assertEqual(sale["moadian_status"], "sent")
            self.assertEqual(sale["moadian_reference"], "ref-100")
            self.assertEqual(len(sale["moadian_taxid"]), 22)
            books = self.accounts()
            self.assertEqual(books["1000"]["amount"], 15000)
            asked = self.client.post(f"/api/sales/{sale['id']}/moadian/inquiry", json={})
            self.assertEqual(asked.status_code, 200, asked.get_json())
            self.assertEqual(asked.get_json()["sale"]["moadian_status"], "success")
            again = self.client.post(f"/api/sales/{sale['id']}/moadian", json={})
            self.assertEqual(again.status_code, 200, again.get_json())
            self.assertIn("قبلاً", again.get_json()["message"])
            enqueue_count = sum(1 for url, _payload, _headers in calls if url.endswith("/async/normal-enqueue"))
            self.assertEqual(enqueue_count, 1)
        finally:
            appmod.http_request = original
            moadian.os.urandom = real_random


if __name__ == "__main__":
    unittest.main()
