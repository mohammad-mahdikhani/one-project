@echo off
setlocal
title STE
cd /d "%~dp0"
echo STE
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0' -Recurse -File | Unblock-File" >nul 2>nul
if exist make-shortcut.vbs cscript //nologo make-shortcut.vbs >nul 2>nul
if not exist runtime\python.exe (
  echo ERROR: runtime\python.exe not found.
  echo Unzip the whole STE folder first.
  pause
  exit /b 1
)
runtime\python.exe -c "print(1)" >nul
if errorlevel 1 (
  echo ERROR: Python did not run. Use 64-bit Windows.
  pause
  exit /b 1
)
echo Starting STE. Keep this window open.
echo.
runtime\python.exe launch.py
echo.
echo STE stopped.
if exist ste-error.log (
  echo --- ste-error.log ---
  type ste-error.log
)
pause
