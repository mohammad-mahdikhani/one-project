دانلود این فایل‌ها از گیت‌هاب است، نه از خود هاست:

https://raw.githubusercontent.com/mohammad-mahdikhani/one-project/cursor/accounting-ledger-56dd/Daftarchi-Host.zip
https://raw.githubusercontent.com/mohammad-mahdikhani/one-project/cursor/accounting-ledger-56dd/Daftarchi.exe

روی هاست، mail.php الان اینجاست:

  public_html/license-server/mail.php

همین فایل‌های تازه را کنار همان mail.php بگذارید:

  version.json
  releases.php
  releases/.htaccess

پوشه releases را هم همان‌جا بسازید. فایل نصب اپ داخل releases قرار می‌گیرد.

دفترچی به ترتیب این آدرس‌ها را می‌خواند و اولین version.json موجود را قبول می‌کند:

  https://webakery.ir/daftarchi/version.json
  https://webakery.ir/license-server/version.json
  https://webakery.ir/version.json

الان فقط سومی روی هاست هست و نسخه‌اش 1.0.3 است. چون از برنامه مشتری پایین‌تر است، نوار به‌روزرسانی نمی‌آید.
بعد از گذاشتن version.json در license-server، همان فایل خوانده می‌شود.
اگر عدد version از نسخه نصب‌شده مشتری بالاتر باشد، بالای برنامه نوار به‌روزرسانی و ویژگی‌های نوشته‌شده نشان داده می‌شود. فروش و حساب‌ها پاک نمی‌شوند.

انتشار نسخه جدید:

  https://webakery.ir/license-server/releases.php

کلید همان عبارت داخل mail.php است. شماره نسخه را بالاتر از نسخه فعلی بنویسید، ویژگی‌های تازه را هر کدام در یک خط بنویسید و فایل exe را انتخاب کنید.
صفحه، فایل را در releases ذخیره می‌کند و version.json را خودش به‌روز می‌کند.
پلاگین فقط فایل zip است و در بخش پایینی همان صفحه منتشر می‌شود.

mail.php کد تأیید حساب را به جیمیل می‌فرستد.
accounts.php نام و موبایل خریدار لایسنس را بدون رمز عبور نگه می‌دارد.
pay.php درخواست پرداخت زیبال را می‌سازد.
