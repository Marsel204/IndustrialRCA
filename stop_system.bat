@echo off
setlocal
cd /d "%~dp0"
title Industrial RCA System - Stop All Services
color 0E

echo ======================================================================
echo    Stopping Industrial RCA Services (Ports 8000, 5173, 1883, 8883)...
echo ======================================================================
echo.

python -u scripts/stop_services.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to execute stop script.
    pause
    exit /b 1
)

echo.
echo [DONE] All services have been stopped.
ping 127.0.0.1 -n 3 >nul
