@echo off
chcp 65001 >nul
cd /d "%~dp0"
title دفترچی

if not exist "runtime\python.exe" (
  echo پوشه runtime پیدا نشد. کل پوشه windows را از پروژه کپی کنید.
  pause
  exit /b 1
)

if not exist "installed.flag" (
  echo اولین اجرا: نصب آفلاین...
  call "%~dp0نصب.bat" quiet
  if not exist "installed.flag" (
    echo نصب انجام نشد.
    pause
    exit /b 1
  )
)

set "DAFTARCHI_DATA=%~dp0..\data"
set "PORT=8080"
set "PYTHONPATH=%~dp0.."
set "PYTHONUTF8=1"

echo دفترچی در حال اجراست. مرورگر خودش باز می‌شود.
echo اگر باز نشد بروید به: http://127.0.0.1:8080
echo ورود اولیه: 09120000000 / daftarchi
echo.
runtime\python.exe "%~dp0launcher.py"
if errorlevel 1 (
  echo خطا در اجرا.
  pause
)
