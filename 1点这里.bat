@echo off
setlocal enabledelayedexpansion

CD /D "%~dp0"
TITLE &#8203;``【oaicite:0】``&#8203;
mode con cols=80 lines=40

REM 检查并获取管理员权限
>nul 2>&1 REG.exe query "HKU\S-1-5-19" || (
    ECHO Set UAC = CreateObject^("Shell.Application"^) > "%TEMP%\Getadmin.vbs"
    ECHO UAC.ShellExecute "%~f0", "%1", "", "runas", 1 >> "%TEMP%\Getadmin.vbs"
    "%TEMP%\Getadmin.vbs"
    DEL /f /q "%TEMP%\Getadmin.vbs" 2>NUL
    Exit /b
)

:continue

setlocal

set "OPTION="

echo.
echo 本程序为开源项目魔改分支，与远程桌面教程相同作者
echo.
echo 本程序禁止在闲鱼、转转等二手平台贩售（包括以安装技术费等名义）如有发现后果自负
echo.
echo 想卖东西自己写啊，拿别人的东西说是自己写的合适吗？
echo.
echo 使用本程序有50%的概率被封号，如您执意运行，代表您同意相关风险由您自己承担
echo.
echo 请输入选项：
echo.
echo   [1] 首次运行
echo.
echo   [2] 速启（默认1-1，无操作会自动选择）
echo.
echo   [3] 地图（选择具体地图）
echo.
echo   [4] 配置（配置后选地图）
echo.
echo   [5] 录制
echo.

REM 等待用户输入或超时
choice /C 12345 /T 15 /D 2 /N >nul

REM 检查用户输入
if errorlevel 5 (
    echo.
    python -i -X utf8 utils/record.py
    echo.
    pause
    goto :end
) else if errorlevel 4 (
    echo.
    python -i -X utf8 Honkai_Star_Rail.py --config
    echo.
    pause
    goto :end
) else if errorlevel 3 (
    echo.
    echo 正在启动程式...
    echo.
    python -i -X utf8 Honkai_Star_Rail.py --debug
    echo.
    pause
    goto :end
) else if errorlevel 2 (
    echo.
    echo 正在极速启动...
    echo.
    python -i -X utf8 Honkai_Star_Rail.py
    echo.
    pause
    goto :end
) else (
    echo.
    echo 正在检查依赖...
    echo.
    python utils/install_requirements.py
    echo.
    goto :start_script
)

:start_script
echo 正在启动程式...
echo.
python -i -X utf8 Honkai_Star_Rail.py --debug
echo.
pause
goto :end

:end
