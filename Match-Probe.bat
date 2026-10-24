@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Fhoe-Rail match probe

REM Self-elevate (same trick as Fhoe-Rail.bat).
REM Reading the game window requires the SAME integrity level as the game: Windows UIPI
REM blocks PrintWindow from a lower-integrity process, and the game client runs elevated.
>nul 2>&1 REG.exe query "HKU\S-1-5-19" || (
    ECHO Set UAC = CreateObject^("Shell.Application"^) > "%TEMP%\Getadmin.vbs"
    ECHO UAC.ShellExecute "%~f0", "%1", "", "runas", 1 >> "%TEMP%\Getadmin.vbs"
    "%TEMP%\Getadmin.vbs"
    DEL /f /q "%TEMP%\Getadmin.vbs" 2>NUL
    Exit /b
)

REM Prefer the user's full Python (embeddable python lacks tkinter & script dir in path)
set "PYTHON_BIN=python"
if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "PYTHON_BIN=%LOCALAPPDATA%\Python\bin\python.exe"

echo ================================================
echo   Match probe - measure one template against the live screen
echo.
echo   Type a template name from picture\ - e.g. transfer, no extension
echo   ENTER = measure the same one again
echo   ?name = list templates containing name
echo   q     = quit
echo.
echo   The game window must be open. It only reads the screen: no
echo   clicking, no key presses, no file changes.
echo   If it reports the window is not found, close this window and
echo   run the .bat as administrator.
echo ================================================
echo.

%PYTHON_BIN% tools\match_probe.py

echo.
pause
