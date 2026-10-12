@echo off
chcp 65001 >nul
cd /d "%~dp0"
title استی
echo در حال باز کردن اپ استی...
python -m pip install -r requirements.txt -q
start "" "http://127.0.0.1:5055"
python -m ste
pause
