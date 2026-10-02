@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Fhoe-Rail WebUI

REM Self-elevate (same trick as Fhoe-Rail.bat).
REM Needed for the image probe: reading the game window requires the SAME integrity
REM level as the game - Windows UIPI blocks PrintWindow from a lower-integrity process,
REM and the game client runs elevated. Without this, PrintWindow returns 0 and the only
REM fallback is copying screen pixels, which is not the game at all.
>nul 2>&1 REG.exe query "HKU\S-1-5-19" || (
    ECHO Set UAC = CreateObject^("Shell.Application"^) > "%TEMP%\Getadmin.vbs"
    ECHO UAC.ShellExecute "%~f0", "%1", "", "runas", 1 >> "%TEMP%\Getadmin.vbs"
    "%TEMP%\Getadmin.vbs"
    DEL /f /q "%TEMP%\Getadmin.vbs" 2>NUL
    Exit /b
)

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
    echo   - Port 8666 held by another program (a running Fhoe-Rail WebUI is taken over automatically)
    echo   - If held by an older WebUI build: press ENTER in its window to quit, then retry
    echo.
    pause
)
