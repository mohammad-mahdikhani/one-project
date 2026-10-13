@echo off
cd /d "%~dp0"
if not exist runtime\python.exe (
  echo runtime\python.exe not found.
  pause
  exit /b 1
)
echo Starting STE...
runtime\python.exe launch.py
echo.
if exist ste-error.log (
  echo --- ste-error.log ---
  type ste-error.log
)
pause
