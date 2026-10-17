@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist "%~dp0Daftarchi\windows\run.bat" (
  call "%~dp0Daftarchi\windows\run.bat"
  exit /b %ERRORLEVEL%
)
if exist "%~dp0windows\run.bat" (
  call "%~dp0windows\run.bat"
  exit /b %ERRORLEVEL%
)

echo run.bat not found.
echo Open the extracted folder and run Start-Daftarchi.bat from inside it.
pause
exit /b 1
