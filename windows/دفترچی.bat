@echo off
setlocal EnableExtensions
set "HERE=%~dp0"
if exist "%HERE%app.py" (
  set "ROOT=%HERE%"
) else (
  set "ROOT=%HERE%.."
)
cd /d "%ROOT%"
title دفترچی
if not exist "windows\runtime\pythonw.exe" (
  echo پرونده اجرای دفترچی کنار این فایل نیست.
  echo زیپ را کامل در یک پوشه باز کنید و فایل‌ها را جدا نکنید.
  pause
  exit /b 1
)
set "DAFTARCHI_DATA=%cd%\data"
set "PORT=8080"
set "PYTHONPATH=%cd%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if not exist "%DAFTARCHI_DATA%" mkdir "%DAFTARCHI_DATA%"
start "" "%cd%\windows\runtime\pythonw.exe" "%cd%\windows\launcher.py"
