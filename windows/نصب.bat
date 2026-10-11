@echo off
chcp 65001 >nul
cd /d "%~dp0"
title نصب آفلاین دفترچی
set "QUIET=%~1"

if not exist "runtime\python.exe" (
  echo فایل runtime\python.exe پیدا نشد.
  if not "%QUIET%"=="quiet" pause
  exit /b 1
)

echo نصب کتابخانه‌ها از پوشه wheels بدون اینترنت...
runtime\python.exe get-pip.py --no-index --find-links=wheels --no-warn-script-location
if errorlevel 1 (
  echo نصب pip ناموفق بود.
  if not "%QUIET%"=="quiet" pause
  exit /b 1
)

runtime\python.exe -m pip install --no-index --find-links=wheels --no-warn-script-location flask openpyxl jdatetime waitress colorama
if errorlevel 1 (
  echo نصب کتابخانه‌ها ناموفق بود.
  if not "%QUIET%"=="quiet" pause
  exit /b 1
)

> installed.flag echo ok
echo نصب تمام شد.
if not "%QUIET%"=="quiet" (
  echo حالا فایل «اجرا.bat» را بزنید.
  pause
)
