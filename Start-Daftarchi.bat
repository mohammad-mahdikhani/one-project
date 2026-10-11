@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0Daftarchi\windows\اجرا.bat" (
  call "%~dp0Daftarchi\windows\اجرا.bat"
) else if exist "%~dp0windows\اجرا.bat" (
  call "%~dp0windows\اجرا.bat"
) else (
  echo فایل اجرا پیدا نشد.
  pause
)
