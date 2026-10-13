@echo off
cd /d "%~dp0"
title STE
echo Starting STE...
start "" "http://127.0.0.1:5055"
python -m ste
pause
