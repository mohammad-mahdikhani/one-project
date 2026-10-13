@echo off
cd /d "%~dp0"
if not exist runtime\python.exe (
  echo runtime\python.exe not found.
  pause
  exit /b 1
)
runtime\python.exe launch.py
if errorlevel 1 (
  echo.
  echo STE failed. Open ste-error.log
  if exist ste-error.log type ste-error.log
  pause
)
