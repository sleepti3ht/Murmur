@echo off
setlocal

cd /d "%~dp0.."

call .venv\Scripts\activate.bat

set PYTHONPATH=%CD%

echo [Murmur] Starting Backend API...
start "Murmur API" /min python dashboard\api.py

timeout /t 2 /nobreak >nul

cd dashboard\tauri
echo [Murmur] Starting Dashboard UI...

cargo tauri dev

taskkill /FI "WINDOWTITLE eq Murmur API" /T /F >nul 2>&1

echo [Murmur] Shutdown complete.
pause