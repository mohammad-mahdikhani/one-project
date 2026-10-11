@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Daftarchi

if not exist "runtime\python.exe" (
  echo runtime\python.exe not found.
  echo Extract the full Daftarchi-Windows.zip first.
  pause
  exit /b 1
)

if not exist "runtime\Lib\site-packages\flask" (
  echo Flask is missing from runtime\Lib\site-packages
  echo Re-download Daftarchi-Windows.zip
  pause
  exit /b 1
)

set "DAFTARCHI_DATA=%~dp0..\data"
set "PORT=8080"
set "PYTHONPATH=%~dp0.."
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo Starting Daftarchi...
echo Open: http://127.0.0.1:8080
echo Login: 09120000000 / daftarchi
echo.
"runtime\python.exe" -c "import flask,openpyxl,jdatetime,waitress; print('deps-ok')" > "%TEMP%\daftarchi-check.txt" 2>&1
if errorlevel 1 (
  echo Dependency check failed. See %TEMP%\daftarchi-check.txt
  type "%TEMP%\daftarchi-check.txt"
  pause
  exit /b 1
)

"runtime\python.exe" "%~dp0launcher.py"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo.
  echo Daftarchi stopped with error %ERR%
  pause
)
exit /b %ERR%
