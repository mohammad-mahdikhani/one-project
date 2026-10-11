@echo off
cd /d "%~dp0"
echo No install step is needed.
echo Just run Start-Daftarchi.bat or windows\run.bat
if not "%~1"=="quiet" pause
exit /b 0
