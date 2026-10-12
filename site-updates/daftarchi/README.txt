دانلود این فایل‌ها از گیت‌هاب است، نه از خود هاست:

https://raw.githubusercontent.com/mohammad-mahdikhani/one-project/cursor/accounting-ledger-56dd/Daftarchi-Host.zip
https://raw.githubusercontent.com/mohammad-mahdikhani/one-project/cursor/accounting-ledger-56dd/Daftarchi-Setup.exe

فایل‌های آپدیت و نامه جیمیل دفترچی بعد از دانلود، همین‌جا روی سایت قرار می‌گیرند.

روی هاست webakery.ir، کنار پوشه wp-admin، این پوشه را بسازید:

  public_html/daftarchi/

و این سه فایل را داخلش کپی کنید:

  version.json
  Daftarchi-Setup.exe
  mail.php

بعد از آپلود، این آدرس‌ها باید در مرورگر باز شوند:

  https://webakery.ir/daftarchi/version.json
  https://webakery.ir/daftarchi/Daftarchi-Setup.exe
  https://webakery.ir/daftarchi/mail.php

mail.php کد تأیید حساب و بازیابی رمز را از هاست به جیمیل می‌فرستد.
اگر وردپرس یک پوشه بالاتر باشد، از wp_mail استفاده می‌کند. وگرنه نامه با mail هاست می‌رود.

هر نسخه جدید:
  1. عدد version را در version.json بالاتر ببرید، مثلاً 1.0.4
  2. فایل نصب جدید را با همان نام Daftarchi-Setup.exe جایگزین کنید
  3. notes را یک جمله فارسی کوتاه بنویسید

دفترچی هنگام باز شدن version.json را می‌خواند. ساخت حساب و ریست رمز به mail.php وصل می‌شود.
فایل نصب را روی همان دفترچی قبلی اجرا کنید؛ حذف لازم نیست و پوشه اطلاعات پاک نمی‌شود.
اگر اینترنت قطع باشد فروشگاه مثل قبل کار می‌کند، ولی کد جیمیل نمی‌رود.
