@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Fhoe-Rail WebUI

REM Prefer the user's full Python
set "PYTHON_BIN=python"
if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "PYTHON_BIN=%LOCALAPPDATA%\Python\bin\python.exe"

echo ================================================
echo   Fhoe-Rail WebUI - Star Rail Control Panel
echo   Browser will open automatically.
echo   Press ENTER in this window to stop the service.
echo ================================================
echo.
%PYTHON_BIN% webui/server.py
if errorlevel 1 (
    echo.
    echo [ERROR] WebUI failed to start. Check:
    echo   - Python 3 installed and runnable
    echo   - Port 8666 not occupied by another program
    echo.
    pause
)
