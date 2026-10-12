import io
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
        response = self.client.post("/api/sales", json={
            "items": [{"product_id": product["id"], "qty": 2}],
            "discount_type": "percent",
            "discount_value": 10,
            "payment_method": "cash",
            "customer_name": "علی",
            "customer_phone": "۰۹۱۲۱۱۱۱۱۱۱",
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        sale = response.get_json()["sale"]
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
            "customer_name": "مریم",
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
        sold = cashier.post("/api/sales", json={"items": [{"product_id": product["id"], "qty": 1}], "payment_method": "cash"})
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
            })
            self.assertEqual(pending.status_code, 200, pending.get_json())
            sale = pending.get_json()["sale"]
            self.assertEqual(sale["status"], "pending")
            self.assertIn("AUTH123", sale["pay_url"])
            self.assertEqual(self.client.get("/api/products").get_json()["products"][0]["stock"], 2)
            confirmed = self.client.post(f"/api/sales/{sale['id']}/confirm", json={"mode": "verify"})
            self.assertEqual(confirmed.status_code, 200, confirmed.get_json())
            self.assertEqual(confirmed.get_json()["sale"]["status"], "paid")
            self.assertEqual(self.client.get("/api/products").get_json()["products"][0]["stock"], 1)
            pushed = self.client.post("/api/products/woo/push", json={})
            self.assertEqual(pushed.status_code, 200, pushed.get_json())
            self.assertEqual(pushed.get_json()["created"], 1)
            site = self.client.post("/api/settings/test/wp")
            self.assertEqual(site.status_code, 200, site.get_json())
            self.assertIn("فروشگاه تست", site.get_json()["message"])
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
        self.assertEqual(appmod.APP_VERSION, "1.0.6")
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
        self.assertEqual(boot["version"], "1.0.6")
        pay = Path("/workspace/site-updates/daftarchi/pay.php").read_text(encoding="utf-8")
        self.assertIn("daftarchi-pay", pay)
        self.assertIn("gateway.zibal.ir/v1/request", pay)
        self.assertTrue(boot["host_mail"])


if __name__ == "__main__":
    unittest.main()
