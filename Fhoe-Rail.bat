@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
CD /D "%~dp0"
TITLE Fhoe-Rail

>nul 2>&1 REG.exe query "HKU\S-1-5-19" || (
    ECHO Set UAC = CreateObject^("Shell.Application"^) > "%TEMP%\Getadmin.vbs"
    ECHO UAC.ShellExecute "%~f0", "%1", "", "runas", 1 >> "%TEMP%\Getadmin.vbs"
    "%TEMP%\Getadmin.vbs"
    DEL /f /q "%TEMP%\Getadmin.vbs" 2>NUL
    Exit /b
)

:continue

REM Prefer the user's full Python (embeddable python lacks tkinter & script dir in path)
set "PYTHON_BIN=python"
if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "PYTHON_BIN=%LOCALAPPDATA%\Python\bin\python.exe"

set "OPTION="

type menu.txt
echo.

choice /C 123456 /T 30 /D 2 /N >nul

if errorlevel 6 (
    %PYTHON_BIN% -i -X utf8 webui\launch.py --white
    echo.
    pause
    goto :end
) else if errorlevel 5 (
    %PYTHON_BIN% -i -X utf8 webui\launch.py --dev
    echo.
    pause
    goto :end
) else if errorlevel 4 (
    %PYTHON_BIN% -i -X utf8 webui\launch.py --record
    echo.
    pause
    goto :end
) else if errorlevel 3 (
    %PYTHON_BIN% -i -X utf8 webui\launch.py --debug
    echo.
    pause
    goto :end
) else if errorlevel 2 (
    %PYTHON_BIN% -i -X utf8 webui\launch.py
    echo.
    pause
    goto :end
) else (
    %PYTHON_BIN% utils/install_requirements.py
    echo.
    goto :start_script
)

:start_script
%PYTHON_BIN% -i -X utf8 webui\launch.py --debug
echo.
pause
goto :end

:end
