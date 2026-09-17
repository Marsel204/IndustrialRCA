@echo off
setlocal
cd /d "%~dp0"
title Industrial RCA System Launcher
color 0B

echo ======================================================================
echo    Starting Industrial Root Cause Analysis (RCA) System...
echo ======================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo [ERROR] Python 3 is not installed or not in PATH!
    echo Please install Python 3.10+ and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

python -u scripts/launcher.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [INFO] Launcher closed or exited.
    pause
)
