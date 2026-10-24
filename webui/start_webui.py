# -*- coding: utf-8 -*-
"""
Fhoe-Rail WebUI 启动器（打包为 Start-WebUI.exe，替代 Start-WebUI.bat）

用法: 双击 Start-WebUI.exe（或 python webui/start_webui.py）
- 打包版启动同目录的 `Fhoe-Rail.exe --webui-server`（单入口，共享主程序那一套
  PyInstaller 库；不再额外打一个 webui-server 包）
- 源码模式直接启动 `python webui/server.py`
- 服务窗口内按 Enter 结束服务（server 自带）
- 服务异常退出时暂停显示错误，正常退出自动关闭
"""
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE = os.path.dirname(os.path.abspath(__file__))


def server_command():
    """返回启动 WebUI 服务的命令行。

    打包版优先用同一个 `Fhoe-Rail.exe --webui-server`（单入口，库只打一份）；
    旧版发布包里的独立 `webui-server.exe` 仍然兼容。源码模式直接跑 server.py。
    """
    if getattr(sys, "frozen", False):
        candidates = [
            (os.path.join(BASE, "Fhoe-Rail.exe"), ["--webui-server"]),
            (
                os.path.join(os.path.dirname(BASE), "Fhoe-Rail.exe"),
                ["--webui-server"],
            ),
            (
                os.path.join(BASE, "webui", "webui-server", "webui-server.exe"),
                [],
            ),
            (os.path.join(BASE, "webui-server.exe"), []),
            (
                os.path.join(
                    os.path.dirname(BASE),
                    "webui",
                    "webui-server",
                    "webui-server.exe",
                ),
                [],
            ),
        ]
        for executable, extra in candidates:
            if os.path.exists(executable):
                return [executable] + extra
        return None
    project_root = os.path.dirname(BASE)  # BASE 是 webui/
    return [sys.executable, os.path.join(project_root, "webui", "server.py")]


def ensure_admin():
    """双击 exe / 脚本时也自动提权。

    游戏以管理员权限运行，Windows UIPI 会挡住低权限进程的 PrintWindow 和前台切换；
    Start-WebUI.bat 已经自己提权，但打包后的 Start-WebUI.exe 之前没有，导致从
    WebUI 启动的锄地进程切不到游戏窗口。这里补齐同一条路径。
    """
    if sys.platform != "win32":
        return
    import ctypes

    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    if getattr(sys, "frozen", False):
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        params = subprocess.list2cmdline(sys.argv)
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if rc <= 32:
        print("[ERROR] 需要管理员权限：请右键选择「以管理员身份运行」。")
        input("Press Enter to close...")
    sys.exit(0)


def main():
    ensure_admin()
    print('=' * 50)
    print('  Fhoe-Rail WebUI - Star Rail Control Panel')
    print('  Browser will open automatically.')
    print('  Press ENTER in this window to stop the service.')
    print('=' * 50)
    server = server_command()
    if not server:
        print()
        print('[ERROR] Fhoe-Rail.exe not found next to this launcher.')
        print('        Please keep the launcher inside the package folder.')
        input('Press any key to close...')
        return 1
    rc = subprocess.call(server)
    if rc != 0:
        print()
        print(f'[ERROR] WebUI exited with code {rc}. Check the message above.')
        input('Press any key to close...')
    return rc


if __name__ == '__main__':
    sys.exit(main())
