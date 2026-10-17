دانلود این فایل‌ها از گیت‌هاب است، نه از خود هاست:

https://raw.githubusercontent.com/mohammad-mahdikhani/one-project/cursor/accounting-ledger-56dd/Daftarchi-Host.zip
https://raw.githubusercontent.com/mohammad-mahdikhani/one-project/cursor/accounting-ledger-56dd/Daftarchi.exe

فایل‌های آپدیت و نامه جیمیل دفترچی بعد از دانلود، همین‌جا روی سایت قرار می‌گیرند.

روی هاست webakery.ir، کنار پوشه wp-admin، این پوشه را بسازید:

  public_html/daftarchi/

و این فایل‌ها را داخلش کپی کنید:

  version.json
  mail.php
  pay.php
  accounts.php

بعد از آپلود، این آدرس‌ها باید در مرورگر باز شوند:

  https://webakery.ir/daftarchi/version.json
  https://webakery.ir/daftarchi/mail.php

mail.php کد تأیید حساب و بازیابی رمز را از هاست به جیمیل می‌فرستد.
accounts.php نام، موبایل و طرح خریدار لایسنس را در accounts.json روی همین هاست نگه می‌دارد. رمز عبور ذخیره نمی‌شود.
اگر وردپرس یک پوشه بالاتر باشد، از wp_mail استفاده می‌کند. وگرنه نامه با mail هاست می‌رود.

هر نسخه جدید:
  1. عدد version را در version.json بالاتر ببرید، مثلاً 1.0.4
  2. لینک url را به فایل Daftarchi.exe همان نسخه بدهید
  3. notes را یک جمله فارسی کوتاه بنویسید

دفترچی هنگام باز شدن version.json را می‌خواند. ساخت حساب و ریست رمز به mail.php وصل می‌شود.
فایل Daftarchi.exe را بزنید. اگر دفترچی از قبل بوده، فروش و حساب‌ها سر جایشان می‌مانند.
اگر اینترنت قطع باشد فروشگاه مثل قبل کار می‌کند، ولی کد جیمیل نمی‌رود.
