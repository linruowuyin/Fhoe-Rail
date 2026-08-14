# -*- coding: utf-8 -*-
"""
Fhoe-Rail WebUI 启动器（打包为 Start-WebUI.exe，替代 Start-WebUI.bat）

用法: 双击 Start-WebUI.exe（或 python webui/start_webui.py）
- 启动 webui/webui-server/webui-server.exe（同一控制台窗口）
- 服务窗口内按 Enter 结束服务（webui-server 自带）
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


def find_server():
    """兼容两种布局: 启动器在发布包根 / 启动器在 webui/ 下"""
    cands = [
        os.path.join(BASE, 'webui', 'webui-server', 'webui-server.exe'),
        os.path.join(BASE, 'webui-server.exe'),
        os.path.join(os.path.dirname(BASE), 'webui', 'webui-server', 'webui-server.exe'),
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def main():
    print('=' * 50)
    print('  Fhoe-Rail WebUI - Star Rail Control Panel')
    print('  Browser will open automatically.')
    print('  Press ENTER in this window to stop the service.')
    print('=' * 50)
    server = find_server()
    if not server:
        print()
        print('[ERROR] webui-server.exe not found next to this launcher.')
        print('        Please keep the launcher inside the package folder.')
        input('Press any key to close...')
        return 1
    rc = subprocess.call([server])
    if rc != 0:
        print()
        print(f'[ERROR] WebUI exited with code {rc}. Check the message above.')
        input('Press any key to close...')
    return rc


if __name__ == '__main__':
    sys.exit(main())
