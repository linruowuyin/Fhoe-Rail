@echo off
setlocal enabledelayedexpansion

CD /D "%~dp0"
TITLE 【Fhoe-Rail】

>nul 2>&1 REG.exe query "HKU\S-1-5-19" || (
    ECHO Set UAC = CreateObject^("Shell.Application"^) > "%TEMP%\Getadmin.vbs"
    ECHO UAC.ShellExecute "%~f0", "%1", "", "runas", 1 >> "%TEMP%\Getadmin.vbs"
    "%TEMP%\Getadmin.vbs"
    DEL /f /q "%TEMP%\Getadmin.vbs" 2>NUL
    Exit /b
)

:continue

REM 初始化变量
set "OPTION="

echo.
echo   本程序为开源项目魔改分支，与远程桌面教程相同作者
echo.
echo   本程序禁止在闲鱼、转转等二手平台贩售（包括以安装技术费等名义）如有发现后果自负
echo.
echo   想卖东西自己写啊，拿别人的东西说是自己写的合适吗？
echo.
echo   使用本程序有50%的概率被封号，如您执意运行，代表您同意相关风险由您自己承担
echo.
echo   请输入选项：
echo.
echo   [1] 首次运行
echo.
echo   [2] 速启（默认1-1，无操作会自动选择）
echo.
echo   [3] 地图（选择具体地图）
echo.
echo   [4] 录制
echo.
echo   [5] 测试（测试代码与地图，F8暂停）
echo.
echo   [6] 仅运行白名单地图
echo.

REM 等待用户输入或超时
choice /C 123456 /T 30 /D 2 /N >nul

REM 处理用户输入
if errorlevel 6 (
    echo.
    echo   正在启动...
    python -i -X utf8 fhoe.py --white
    echo.
    pause
    goto :end
) else if errorlevel 5 (
    echo.
    echo   Tips：按F8暂停，暂停后按F8继续，按F9重新运行当前地图
    python -i -X utf8 fhoe.py --dev
    echo.
    pause
    goto :end
) else if errorlevel 4 (
    echo.
    python -i -X utf8 fhoe.py --record
    echo.
    pause
    goto :end
) else if errorlevel 3 (
    echo.
    echo   正在启动程序...
    echo.
    python -i -X utf8 fhoe.py --debug
    echo.
    pause
    goto :end
) else if errorlevel 2 (
    echo.
    echo   正在极速启动...
    echo.
    python -i -X utf8 fhoe.py
    echo.
    pause
    goto :end
) else (
    echo.
    echo   正在检查并安装依赖...
    echo.
    python utils/install_requirements.py
    echo.
    goto :start_script
)

:start_script
echo.
echo   正在启动地图选项...
echo.
python -i -X utf8 fhoe.py --debug
echo.
pause
goto :end

:end