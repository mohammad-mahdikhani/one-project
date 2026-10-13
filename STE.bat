@echo off
cd /d "%~dp0"
title STE
if not exist runtime\python.exe (
  echo runtime\python.exe not found.
  pause
  exit /b 1
)
echo STE is starting...
runtime\python.exe ste_boot.py 1>>ste-log.txt 2>&1
echo.
echo If the browser did not open, open http://127.0.0.1:5055
echo Log file: ste-log.txt
pause
