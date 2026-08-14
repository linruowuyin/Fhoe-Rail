# -*- coding: utf-8 -*-
"""
Fhoe-Rail WebUI 本地服务（零依赖，仅标准库）

用法（在项目根目录）:
    python webui/server.py

然后浏览器访问 http://127.0.0.1:8666
按 Ctrl+C 停止服务。

端点:
    GET  /                  -> WebUI 页面
    GET  /api/config        -> 读取 config.json
    POST /api/config        -> 保存 config.json（请求体为完整 JSON 对象）
    GET  /api/maps          -> 地图树（按版本 -> 星球 -> 地图）
    GET  /api/logs?lines=N  -> 日志文件尾部 N 行（默认 200）
    GET  /api/stats         -> 汇总统计（配置概览 + 日志解析）
"""

import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# 系统语言兼容：日文系统 cp932 下中文 print 会崩，强制 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, OSError):
        pass

if getattr(sys, 'frozen', False):
    # PyInstaller 打包环境: exe 位于 <项目根>/webui/webui-server/ 下,向上三级到项目根
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(sys.executable))))
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)  # 使 utils.* 可直接 import（用于通知测试等）
WEBUI_DIR = os.path.join(BASE_DIR, 'webui')
NOTES_DIR = os.path.join(BASE_DIR, '新图注意事项')
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
LOG_PATH = os.path.join(BASE_DIR, 'logs', '日志文件.log')
PORT = 8666


def find_user_python():
    """优先使用用户安装的完整版 Python。
    AutoClaw 自带的 Python 是 embeddable 精简配置（python313._pth），
    脚本目录不在 sys.path 且缺少 tkinter，不适合运行本项目。
    """
    candidates = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Python', 'bin', 'python.exe'),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return sys.executable


PYTHON_BIN = find_user_python()

PLANET_NAMES = {
    '1': '空间站「黑塔」', '2': '雅利洛-VI', '3': '仙舟「罗浮」',
    '4': '匹诺康尼', '5': '翁法罗斯', '6': '二相乐园',
}

# logo 缓存：{(类型): bytes}
_logo_cache = {}


_LOGO_B64 = (
    'AAABAAEAQEAgAAAAAAAoQgAAFgAAACgAAABAAAAAgAAAAAEAIAAAAAAAAEAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAEA0gW9rW6///////ubux/7K0rP/d3tn/1tbO/8nJvP+kppP/'
    'sbGq///////GxNv/sK3K/8LB1/+2stL/9vby/3x8Wv9pbEH/x8nB//T8/P+rwsD/t8vK/8bRzf+e'
    'p5b/ZGpB/3VzUv/8/fj/vLzZ/zw+SHEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAMCBAAAAAAAAAAACAYFHQwKBiw7NEax'
    'nJa0/Obj8P/k5OD/sLCq/7Czrf+3t7P/paSg/////v+7uM//ZF57/6uroPBuaoTj/////4eHcP9e'
    'YDr/1NbP/+bu8P+3xcb/xtfW/7fKyf+itbX/ucnK/7vIxP9qblf/qqye/+rp9v9XWnS5AAAAAAAA'
    'AAAZFRI5Jh0YWB4VEEwaEQxDIBcRTRkSDEQSDgk7JSAZazMvLYEvKSWHLicgkDApIJo4NCmeXFlT'
    'omNdVqhnYlmtamNdr25pZLNmYlyyNjMysj07QLctKSS4OzgqvpqXkchPTEfJJCAixzAuNMQzMDXM'
    'Mi03yRkWFFCMh4Wenp6YuyAbGkETDws6FxYNOAMACSs3NU+5pqLB/9nU4//q6ej/z87H//////+7'
    't9P/WFBz/zg9Pf9Yk8L4cXik8f79+/+Min3/ys7K/93n6v+5ysr/4ujq////////////6vP1/7vN'
    'z/+pvr//r8LC/6Wqn//08Pf/Z2eO5goKCgoAAAAACwkHFw8LCR0LCAYVCQYEEBoUEDoOCggcBQMC'
    'CBkYHJFYZYX/SFN3/yUlMv8TExL/eXl8///////z8/v/8/T8//L2/v/19////////3N1gP85RGz/'
    'LzdU/zk7Jf+Xn5H/6PDw/z9DT/8jJ0b/ISdD/yApSf8tMkHp9v/+//////+Tm5enBwkGEQAAAAAA'
    'AAAGTlRY45yitv+AgJz/joqs/8PA0/+koL7/U09z/yUoK/8SFRT/MUph/4CDrP/5+fn/s7Wv/83Y'
    '2v+3x8b/wcjB//b89//x9vT/4ujk/9nc1f/N0Mj/v8rH/6i9u/+Llor/8/Hw/3h5m/gaGx0hAAAA'
    'AAAAAAAAAAAGAAAACQAAAAoAAAASAAAAHwAAABUAAABQOUBb/05ejf8oLkf/BwcL/7i5wf/y8/z/'
    '5ebw/+bo8f/t8Pn/9PX+//////+sraT/Jy8//zpGcv8xNjX/KzEX/25zcv9ydnj/EBYp/x4pPv8a'
    'Izv/JChH/15ncP/j6+n/3enZ/52jk9ouMDAwAAAAK2tyfP+cprP/nKay/5edrv+GiJ//j4+s/0lO'
    'Uv8PEhX/JSku/yMiIf9sY4b//////52fl/+xvLr/vsW6/3+CbP+2u6n/q6+h/42Te/96f2T/iIhy'
    '/4WJdf/Y3tr/hYqA//T08P+Hiqv/HB4hKwAAAAAUFiCDIyc55SIkNegiJTXpISY37CMqOvQjKTny'
    'Iyo4+iUpPP9SXon/MDti/0JBSf/y8/n/7e74//b2/v/r7PH/x8jN/5qbov9ydH//Sk9Z/yszRf89'
    'SnD/NEBk/y83Vf8mLU7/KzZV/zA8W/8tOFj/MDpb/zM9Xv8dI0X/PEVO/97r5//l8OX/1t3c3hUW'
    'GVtveIT/maKy/5Sbq/+Tm6r/mKCu/6Ost/88QUj/HB4i/xwdIP8AAAC/GBEskuvq9f7m5t//lpaQ'
    '/7m6tv/Z29P/ra+g/9LTy//MzsX/u7yw/9TWzP/Iyr//o6OY/87Qx//t7fb/bGyQ8g8QERQAAAAA'
    'IiU3oDtDYf82PVr/Nj5Z/zY9Wf81PFj/NTxY/zc+Wv8iKDf/QUhq/0VTgP89QVX/ysrP/8/R1/+P'
    'kJj/UVRj/zI5Uf8rNlX/KTRU/y03Wv81QGP/Mj1b/y05VP8sNU3/JCpB/xsgNP8sM0L/LDND/xsj'
    'O/8kLUj/KTFO/xIYLv+vu7n//v////////+Um5znaXB//Zagsv+Tm6v/k5yr/5OdrP+YoK7/Ki0y'
    '/wQGBv8iJCL/U1ZS6GVmbcd7dpn47u33//////+3uLT/qKik/7KzrP/f4dv/5urm/+vu6v/DxsH/'
    'oaKb/+Pj3f/o5vP/eXOg/zIxPl0AAAAAAAAAAB8pP5o5THL/NUdr/zVFbf81Rm7/Nklu/zdJcP85'
    'S3L/OEtz/y02VP9NXof/NEJk/zhAU/82QFb/LTle/zpEbP82Plz/JCs//x0gLf8eHyj/HB4n/xUX'
    'Hv8TFhL/GBwX/xYXHP8WFxv/MDM0/73CwP8mKzP/Fx44/xEaK/8VGST/ydTU//n////8////vcfF'
    '/2Jndf+YpLj/kp2s/5Ocqf+Unq3/i5Oe/ycrLP9nbWb/ub63//D28f//////ycvT9D44W8GfnLj6'
    '//////r79f+7urb/pKSg/8nKx/+2ubT/pqmk//7/+//T0ub/b2uP9TAvOVUAAAAAAAAAAAAAAAAu'
    'P2SaWHm6/1R2sv9WdbD/VHWs/1Jyqf9Rcqr/Vnmz/01noP8tLjz/P0ts/0pZh/87S3H/NkRl/zA6'
    'WP8eIzD/HBwk/yIlKv8nKjP/Jikz/yotNf8rLDf/Jyky/yElLP8ZGyP/HiMs/w0RGf9/hIb/rLK0'
    '/xIZLf8eJD//CQ4f/3qEhf///////////9zo5/9NVmL/eYmg/4mVqP+UnK3/l6Cw/3R8iP+AhX//'
    'z9bL/9ng1//r8Ov/4+jm/vz8/PyRkZKWSkReqE9IcM2/vtf//////////f/Fxr3/19fP//////+O'
    'iafwKCNBjR4dIjAAAAAAAAAAAAAAAAAAAAAAOT9Nnkxaff86SnD/TmOL/196rP9oh7z/Zoi9/1l7'
    'rP9NVGP/v7+5/3R2gv0wNEz8LjNH/0BDSP8bHCD/Jyou/ysuNf8qKzj/JCYq/ysuLP8jJS//IiYn'
    '/ygtK/8rLTb/JSgy/yMqMv8mKzP/EhYc/7/Exf9PVGD/GyI9/xQcL/8fJy//aW1x/5egov/+////'
    'bXh+/1Bhdf9pe5T/e4id/5igtf9tc4D/k5qQ/8rPxP+0uLD/PUBD/1tcXNX7+/v7//////b29vYk'
    'IyiVAAAQTUxIacCfl7T04Nvo/8O80fk+OVSkAAAAIwAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAFBW'
    'Xoqir7r8gImW/yoqLoIKDRaASl+C+mSFuv8/TmP/yMnI//////+srK/9NTU1/Ghlb/9tbHn/HSEm'
    '/x0gKP8oLDf/Iyow/zxBLf8rLCX/Jyoo/zxEK/8lJyn/Kywt/zY9L/8oKi//KjA4/xYdI/8+Q0b/'
    'hoyR/x4jPP8lKUL/Fhov/woOIP8ABRP/lp+i/9nh4P9HVF//boGc/2Z5kf90h53/XGVu/6iqn//I'
    'zcD/VVte/0pZcP9HTlb49vb0/v//////////hoaF/QAAACgAAAAAFCM6YktnkNZEX4jNAAYHGAAA'
    'AAAAAAAAAQAAJgAAAAIAAAAAAAAAAAAAAAAKDA0Oq7fAxLHB0P8WFRUiAAAAJj5TcfZIV3L/w8DB'
    '//r7///3+Pz/aGlv/2dnbf9XV03/VFI6/2htOv9BRyj/ISAu/ysxLf8qLST/ISAu/y42JP8lJiv/'
    'LS8t/0tVM/84PS7/JSct/yMqMf8nLzT/FRof/x4kJ/8pLUb/KS9L/yYuSP8ZHzT/ERgr/zxETf//'
    '////oa6s/1JfdP9zhaD/boKZ/1JbZP/Axbf/pque/0VRXP9xhZ3/VWJz/36Agv///////////8XF'
    'xP8AAABGAAAAAClISEhSnqenbL3c3BonKDsAAAAAAAAAAQEAADAAAAACAAAAAAAAAAAAAAAAXmVp'
    'g6O0wv94iJz/NENk9EVbhP83SGP/trW2/+Xl6f/m5+z/8/T5/2xsdP9aWF3/XWQx/4iPRf+OlU3/'
    'cHc9/yIgKv8mKTD/PkUt/yMiJv84PSr/LS8q/zM2Kf8pLCv/Jio4/yInLf8fJSv/HiQp/yUpLv8q'
    'LTj/HyY+/ycuSf8nME3/IilD/wkMHf9HS073x8rJ/ZugoP8tMjj/UF9y/1Zmfv9BSVD/mqCT/4uP'
    'gv9KWGT/bYGY/3eEm/9haXf/f4OJ//////+oqar7AAAAXg0NCG8eHgqYIx8HozY/LLcRExNkAAAA'
    'BAAAAAACAAEqAAAAAgAAAAAAAAAAAAAAAAwOEZESFRrLGh8uwR8qQq8WHS3moqKk/+jp6v/a3N7/'
    '7e7z//j5/v94eX7/YV9o/1hZSP93gEL/ho5N/3mASP8lJSf/Jyg3/y80LP83Pi3/Jico/zhAKv8u'
    'Lyj/PkUs/yAjLP8bICj/JCgu/xgcIv/IzNH/pKiz/w0UK/8nL0r/KzJM/x4jOf8aHSf/SU9X+GZx'
    'fv1veor/hI6f/4eQpv+CjqP/d4GR/2Jqdf9PUVf/RE1a/19whv9kdIr/ipmt/2hvfv99gIP/eHhU'
    '/2ZmKf+XlTn/oZ80/5+cKP+Nixf/c3ER/z47CtEFAwNdAAACMQAAAAAAAAAAAAAAAAAAAAAAAAAS'
    'AAAAAAAAAAAAAAAshISF6v/////l5un/6+zw/+rr8P/6+///pqis/1JUW/9zcn7/VllI/2t1Pv95'
    'f0T/NDYo/yUlNP8oKTP/Jiwx/x4gJ/8aHCP/JSgt/zU5Mf8kKCz/ICYt/xAVG/94fYT//////52k'
    'sP8OEyv/KDBP/wsOIv8eJCz/aXiO/5Kkwv+Oor3/ip22/42guP+Worr/m6W6/5ynvP+aprv/lJ+0'
    '/4uUp/9yfZD/WWh7/2R0h/+bprr/aXGB/z49IP+AfS7/o6E3/6imM/+mpC//npwk/5qVGP+Wkg7/'
    'bGkR/xgZCa8AAAAVAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAATWVpc4/v9///m5+z/7O3y/+rr8P/q'
    '6/D/9Pb6/4yNn/84OEX/e3yE/3Nvfv9cW1L/gItN/2NoPP8gHSL/Jyk1/yUmMv8mKCb/Ojww/yEi'
    'Jv8eIij/HyUr/yQrMf8iJSv/5Ovz//j///9UWmr/Bwsl/xYcM/9mbXX/wcHB/3F4e/8rMz3/Tl5x'
    '/3GEof98k67/epGq/4SWsP+QnrT/laK0/5GesP+TnbD/lp+y/46Yqv9xfY//d4OV/52ou/99h5v/'
    'KC8+/zk7Ov9eXzz/ZWQi/29sF/+DgBP/fXsB/4iIAP+FgQ7/MTEK1AEBARoAAAAAAAAAAAAAAAAA'
    'AAAAKCgps+jq7f/a297/4OHm/+np8f/p6u//7Ozy/9XY3/+Wm7D/gYWO/19eZv+Af4r/aWdr/2Ns'
    'Ov+AiUr/eH5L/yYoJv8fICL/cHZT/46TaP9tc1L/GRoY/wkKDv8YGyH/JSYt/3l6gv9JTlT/CAoS'
    '/0xRXP+Pk5X/pqyr/4uRkP+MlZb/j5eh/5ynvv9bZ4z/R1V3/2l7lv9mfJP/bX+X/3uKov+Om6//'
    'k5uv/5CarP+Qmqz/lJ6x/4mTpv+Kk6b/nKW5/5Wftf9aZn//VGJ+/15shP81PEr/HR8W/3p1XP9z'
    'b0L/amol/1BTDv8PEQi+AAAABQAAAAAAAAAAAgMFcLu9wv/z9fn/4OTk//Hy9v/y8vb/8vT1//b3'
    '+P/e4OP/lJyx/9ji7/9OTlj/iIWS/2lpaP98hUr/iJJQ/5KgWP9nc0D/R0o1/4uPZ/+FiGH/gIdc'
    '/xwdGP8TFRr/EREW/zxXZf82YnX/AAAA/xMVFf+Dh4X/kJOV/6mutv/R3ez/5vX//97t//+Ekb7/'
    'ZHCU/1pmgP98iJ7/gY+j/32Mof9ygJX/e4ic/5KcsP+Smq3/kJqt/5Kbrv+Vn7L/kZuu/42Xqv+b'
    'pbj/mqS3/2hzhv9ba37/fY+o/0ZXcP96foT8wsDFxVFPWLYAAAAtAgIBLgAAAAMAAAAAAAAALnJ0'
    'd/r+////8vT2//v8+//6+vr/+vr6//r6+v/7+/r//f39/4SLnv/T3/f/pq67/1ZVYv9kYmj/ZW88'
    '/4iUVP9qc0D/TFIw/1pdQP+FiWP/hopj/3N5Vf8aGxz/IyUt/w8RE/8qNEP/W3aO/2Rnc/+OkJT/'
    '09fb//T9///t+f//2+n//9jo///I2fD/W2mF/15rh/+Tobj/o7LE/5mmuf+Xpbn/l6a3/5Gfsf+R'
    'nbD/kZyv/5Ocr/+TnK//k52w/5Wgsv+Rna//j5qt/5ijtv+gqbz/dH6R/1Jgdf9whqL/OURZ/QAA'
    'AU0AAABlAQEBDQAAAAAAAAAAAAAAACssLJby8fP/5eTk//j4+f/6+vr/+fn5//n5+f/5+fn/+fn5'
    '//7+/v/W2Nv/e4Ca/5+nvP9hYnP/bWxy/1lbTP9OUzP/XWBC/3B0U/+FimD/gYVe/4aMYv9makz/'
    'FBUb/w8QF/9MUnP/s7nd/9Xd6v/8//////////T6///h7f3/2Of+/9Tl///P4v7/y+L//83m//+o'
    'vd3/Ym+R/2d1j/+Yprr/mae5/5Oktf+Uo7T/k5+y/5KesP+UnbD/lJ2w/5WesP+Wn7H/laGz/5Od'
    'r/+Wn7L/l6G0/6Krvv91f5L/T150/2x9mf8tNkDgAAAAaAAAARAAAAAAAAAAAAAAAACSk5Od+vr6'
    '/+vr6//8/Pz/+fn5//n5+f/5+fn/+fn5//n5+f/5+fn//////+Hi5P/Av8r/7/D2//38//+rrZ7/'
    'eH1Y/4mNZv+EiWH/gYVe/4GFXv+JkGX/VFk/8QAAALoOER3+t7vS///////y/P//8fj///H2///n'
    '8P7/2+j+/9Xm/v/R5P//x97+/8jh///G4///l6rS/zQ0c/8REEf/YmyG/4qXr/+cq73/lKK0/5Sg'
    'sv+Tn7H/lZ6x/5Wesf+VnrH/lZ6x/5Wesf+Wn7L/lqCz/5ehtP+ao7b/pK3A/2l0h/9OXnP/XGl8'
    '/wIBBXsAAAAAAAAAAAAAAAAAAAAAmpqamv7+/v/6+vr/+fn5//n5+f/5+fn/+fn5//n5+f/5+fn/'
    '+fn5//n5+f/+/v3//////+Tk4/+KiXr/bXFQ/4aKZ/+Eh2L/gYVe/4GFXv+BhV7/jJJn/ycqGeAj'
    'JCejvcHE/vv////w9f//8fb//9zo9//b6Pb/6PD//9jl/v/U5f3/zOH9/9Hp//+7zfD/U1eH/wAA'
    'NP8MBkb/mJi4/9Xb4P9kbof/e4Od/6Csv/+UobP/lKCx/5Wesf+VnrH/lZ6x/5afsv+WoLP/l6G0'
    '/5iitf+Zo7b/m6S3/56muf+hqr3/U19z/3WFn/8xNj/lAAAAJwAAAAAAAAAAAAAAAIqKi5r/////'
    '+fn5//n5+f/5+fn/+fn5//n5+f/5+fn/+fn5//n5+f/5+fn//Pz8/+/v7f+io5j/tLSe/3J1U/+F'
    'h2b/g4hi/4GFXv+ChV//iI1i/19jRf9RU1b/5+nt///////w9f//+P3///r+///R4fP/0OHz/+ry'
    '/v/Y5/3/1OP//93v//+wv+H/JSdc/wAALf85N2b/x8nY//7////7////6PDy/3N7j/9xepL/nqm9'
    '/5Sgsv+VnrH/lZ6x/5Wesf+WoLP/l6G0/5iitf+ZorX/mqO2/5ukt/+dprn/pa/C/4qVqP9kc4v/'
    'jJ66/zA3P+AAAAAZAAAAAAAAAACSkpKa//////n5+f/5+fn/+fn5//n5+f/5+fn/+fn5//n5+f/5'
    '+fn/+fn5//////+3t7D/4+Pf/9XXyf9qbkz/iI1q/4OJZv+ChV//h4xh/2BkSf9vcX3/9Pf9//r+'
    '///u9v7/7vb6/8XN6//I0uz/7fL7//P4///p8v7/3On+/+Ty///BzOf/GRtS/wAAMf9jZYv/19zw'
    '//z////v9P//7vT///X7///1+/z/fIaX/3B4j/+eqbr/lJ6w/5Wfsf+XoLP/l6G0/5iitf+YorX/'
    'maO2/5ukt/+cpbn/n6m8/6Krvf+ps8P/a3eJ/3qPqf+KoLb/HiElsAAAAAAAAAAAmJiYmv/////5'
    '+fn/+fn5//n5+f/5+fn/+fn5//n5+f/6+vr//Pv8//39/v/w8e//tber//////+UlYL/en1Y/4eM'
    'af+FiWX/iYxi/2VrT/9uboD/8/f+//f8///u9P3/9////7O86/9sfOP/maLZ/+zw9//x9/7/7vT/'
    '/+v0///e6vX/MDJh/wYFOP+KjrD/1Nn2/+ju/P/v9v//7/T//+/0///u8///8/r///j9/v91fJD/'
    'cn2U/5ymuf+XobL/mKK1/5iitf+Zo7T/mqS2/5ymuP+dprn/nqi7/5+qvP+irL3/p7HC/5CZqv9k'
    'dIn/l67H/1lmdv8AAAArAAAAAJeXl5r/////+fn5//n5+f/5+fn/+fn5//z9/P//////8/Tx/+jp'
    '5f/r7Or/7+/u/+/x7P/Hxr7/fH5i/4yObf+Eimf/h41o/3Z8VP9aYGj/5Ov5//H4///q8v//8fn+'
    '/9vh8f93g9b/p7Pn//P6/f/z+P//7/T//+/0///9////parC/xwcTf+jqcP/3+b5/+3z/f/y+P//'
    '7/T//+/0///v9P//7/T//+/2///7////fIOm/0FOZv+Om63/nKa4/5iitf+ZorX/m6S1/5ymtv+e'
    'qLn/nqe6/56ou/+gqr3/oqu+/6SuwP+ps8X/a3eK/4aasP96jaH/BggLhAAAAACXl5ea//////n5'
    '+f/5+fn/+fn5//v7+//o6eb/v8C7/7Cxp/+ytqn/sLSq/7O1qv+srJz/h4lr/5acef+OkXH/hopp'
    '/4iOZv9UVVX/vsng/+n4///e6v//4uz//+nz/v/L0+n/0Nnu//L5///v9v//6fL///T7///8////'
    '/P///+fv+f/f6vb/8v////P+///6////9vz///T5/v/w9v//7/X+/+/0///0+f//3er8/1Jgh/9o'
    'd4v/X26C/5Oesf+dpbj/m6S3/52muf+ep7n/nqi7/56pvP+gqr3/oay+/6Gtv/+jr8H/rrjL/4OM'
    'n/9xg5f/lq7E/zc/SNMAAAACl5eXmv/////5+fn/+fn5//n5+f/7+/v/5OXj/+Tm4v/8/Pr/////'
    '///////a29D/io1r/3d5Wf+Iimz/k5h4/4yPa/9pblP/goqi/+z5///X5///1+b//9ro///g7P//'
    '7fX///X5///v9f//6fL+/97q9/+7xNT/lp+w/4OMnv97g5r/dX2d/3B5oP9/iK7/oKnR/8fQ9P/j'
    '7f//6/P///P3/v/z+f//+P3//7/H7v9FVnv/doqb/2h4jf9rd4v/nqm7/56ovP+fqb3/n6i7/56q'
    'u/+fqrz/oKy+/6KuwP+irsD/pLDD/6m1yP+ZobT/a32R/5atxf9WZHH5AAAAHpeXl5r/////+fn5'
    '//n5+f/5+fn/+fn5//39/v/9/f7/+fn5//39/f/09fP/rbGZ/6iqiv+mqIb/entc/4mMbf+Nk2v/'
    'XWBd/77K5v/d7f//1OX//9Tm/v/W5f7/2uf+/+Tv/f/u9f//7/X///r////W4Ov/Q0pp/1ligv+K'
    'la//kJyy/42Zr/+CjqX/dICX/2BsjP9TX4j/aHGn/6Wr5f/L1P//3+n7//j+//+Gib7/P0xu/3GG'
    'mf93iaP/Z3aQ/3uIm/+Woa//mqW4/6awx/+kscX/p7HI/6i1yv+jsML/pLDD/6Sww/+ns8b/pLDC'
    '/2h3jP+HmrL/WGd2/wAAADKXl5ea//////n5+f/5+fn/+fn5//n5+f/5+fn/+fn5//n5+v//////'
    'xMe4/6Gnif+nqo3/qaqJ/5mbeP95elz/iItm/2VsdP/g7v//1eb//9Di///P4///0eT//+Dv///u'
    '/f//8/7///H4/v+0u8n/e4Oc/1tjiP83QV//cX2W/42bsP+Vo7j/l6W6/5inuv+cqrz/k6Cy/3J/'
    'k/9VYYL/a3iu/6mw7/+YoNP/YGeQ/1JYQ/9qb0z/ZWxb/11mVv9SVDv/aGlK/2hqTv9xc2P/cHVk'
    '/2dsWP+AhoL/pbHD/6Wyxv+lscT/p7PF/625y/9tfI//b4OZ/1djcv8AAAA0l5eXmv/////5+fn/'
    '+fn5//n5+f/5+fn/+fn5//n5+f//////2tzU/6aplv+qr5b/qKuQ/6eniP+nqIb/fX5d/4OFYP9f'
    'ZnD/pbPR/8Xb+v/H3///0un//9Hm//+uvNn/bHGZ/2BfiP90fI//VV94/4qWsf+Rnbf/mKW7/5Ge'
    's/+Jl6v/k6C1/5WjuP+TobT/k6G0/5Whs/+aprf/mKW0/2l3iv9BSXX/jJTZ/2FohP+SkGL/0s6x'
    '/66sif+jonr/0tO+/+rr5//W1Mv/l5V5/5WTdP+RkGr/QkQV/5Sdqv+qt8v/prLE/6ezxv+xvc//'
    'cX+R/2x+k/9HUV3/AAAAJ5eXl5r/////+fn5//n5+f/5+fn/+fn5//n5+f/+/f7/7vDr/660o/+r'
    'spz/r7Oc/6qukv+nqIn/q6uI/4KCYv+HiWb/QEhO/yo3XP+61/3/yeP//4+gx/88QXP/AQA7/wcE'
    'O/9kZI7/xcvV/214iv9+iqL/oKrC/5ekuf+Xpbr/mKa7/5WkuP+Uorb/laG0/5ShtP+WobT/lKCz'
    '/5Wgsv+dpbf/hpCh/1pji/96hL3/XGNn/4OIef9+gnb/dnhk/39/X/+IiWn/d3pg/3F2Zf94fXD/'
    'aW5b/3qCfP+mssX/qLTH/6i0xv+qtsj/sr7R/3aClP+QnbP/PEJM5QAAAA2Xl5ea//////n5+f/5'
    '+fn/+fn5//n5+f/7+/z/+vv4/73EuP+cpI//mKCE/5qfhf+qrZH/qaqM/6urif+EhGL/bHFY/0xb'
    'cf9Zao3/kKHO/0ZMgv8AADL/DAs//19ijP+qsNL/1932//b9///q8fT/XGR7/4OPp/+Zp7z/laO4'
    '/5WjuP+Vo7b/laS1/5ajtf+WorX/laG0/5Shs/+VoLP/maG0/6Grvf+NmKr/Oj9p/2Fqi/+rtsv/'
    'o63E/6Gswv+Qnar/bn2G/2FvfP+otsz/q7jO/6u4zf+sutD/qLTG/6i0xv+qtsj/q7fK/7K+0f96'
    'hpj/navB/01TXeUAAAAMl5eXmv/////5+fn/+fn5//n5+f/5+vv//f/9/8rQxv+TnIf/tLin/+Hj'
    '3P/O0MH/lpx9/6ytj/+nqIn/f4Bf/1JVT/9yiaf/X3SS/yopXv8fFVb/cGqY/9Xa5v/q8///7fX/'
    '//P6///v9f//+v///3V7nP9ndo//kJ6z/5imuv+Uo7b/l6O2/5ektv+Xo7b/mKO2/5WhtP+VobT/'
    'lqK1/5mlt/+apbj/pLHC/3uHmv9SXXT/pLDD/5ypvP+eq73/o6/D/6m3y/97ip3/i5qt/6q3yv+m'
    's8b/p7TG/6m1x/+qtsn/qrbJ/6y4yv+zv9L/c3+R/5uswP9rdYH/AAAAL5eXl5r/////+fn5//n5'
    '+f/6+vr//////9fd1P+ZoY7/xMm8////////////5uXg/5KZe/+1uJn/nqB8/2NlRf9HU1f/haC/'
    '/2Z8mP97h53/wcvW/7zC0v/Gzdj/3eTu//L6///1/v//9fr///j///97gKr/fIuk/32Ln/+ToLP/'
    'mKa4/5aktv+Yo7b/mKO2/5ijtv+Xo7b/maW3/5qmuf+bqLr/m6i7/5unuv+ksMP/hpKl/5Ccr/+j'
    'r8H/oa2//6Ktw/+kssb/m6q8/3uKnP+ot8j/prXH/6i1x/+qtsj/q7fK/6u3yv+suMv/sb3Q/3J+'
    'kP+hsMT/eIKQ/wAAAEiXl5ea//////z8/P///////////9bc1P+lrp//p6ua///////KzsD/uLyo'
    '/7O2n/+iqIj/hIVz/0dJRP8sMDP/U2R1/4ahvf+AmLH/WWuM/1xmjP9EUGj/eoid/2t1kP9scpX/'
    'k57F/83V+//q8///g4m2/3SCm/+Wpbj/foyd/5unuf+Zpbf/maW3/5ikt/+YpLf/maW4/5unuf+c'
    'qLv/nai7/52pvP+dqbz/oKy+/5upu/+Il6n/orDC/6Gvwf+isML/orHE/6m3yf+DkqT/nKq8/6m3'
    'yv+qtsn/q7fK/6y4y/+suMv/rbnM/6y5y/9wfpD/qLfL/3mFkv8AAABFmpqamv/////7/Pv/o6ih'
    '5oSLfuqyvq//nKeS/83Sxv/c3tD/XGUz/1pkOP+dpIL/jY13/zQ5RP92i6b/Z3iU/2t/mP+Enbj/'
    'iqK6/2J1k/90ebX/dHuw/3mHof+uu9H/kZ20/2Zxjv9XYY3/lZzZ/5uh3/9pdJH/qLfD/4iWp/+I'
    'lKb/nai6/5mlt/+aprn/m6e5/5youv+dqLz/nqq9/56rvf+eq73/n6y+/6Ctv/+grsD/nau+/6Gw'
    'wv+jscP/pbLE/6azxf+ptsj/nau9/5+uwP+quMv/qrfK/6u3yv+tucv/rbnL/6+7zf+ns8X/cH+R'
    '/7DA1P9lbXj7AAAAJXR0dKaRk5L2MTEx02Zzc912g3Pts72v/5+pl//Cxrb/srWb/2FqO/+apIP/'
    'wsmv/3l8bf8SFBa+TFtp72+Bmv9rfpb/e5Kq/2t+lv9sfJL/VmOC/2t1nf8zO1//aHOO/6i3yf+n'
    'tsf/jp2u/1pmhf9rdKj/WmKJ/56qu/+dqb3/hJCi/5ahtP+cqLv/nKi7/5you/+dqbz/n6q9/6Cs'
    'vv+frb//nqy//5+tv/+grsD/oa/C/6OyxP+kssX/pbPF/6Cyw/+ltMb/qbbI/6m3yf+puMr/qbjK'
    '/6u4yv+suMv/rrrM/666zP+yvtD/maW4/3SBlP+0xNn/QEZQ0wAAAAIAAAAzAAAAIAAAAE6Yq63/'
    'i5uJ/7K6rv+vuKv/n6iS/6Gokv+0vaj/q7Cf/1RXTvEFBgV9AAAAAAAAAEc4QVDyWWt+/3mJnP+M'
    'ma3/m6i8/6Gwwf+cqbz/kJ2z/3B9lP+Lmaz/n67A/6Gxwv+frb//Y3CH/x0oSP+Ej6f/pK/C/5ik'
    'tv+XorX/nam8/52ou/+eqrz/nqu9/5+tv/+hrsD/oK7A/6Cvwf+hsML/orDD/6OyxP+ls8X/prTG'
    '/5+1xf+oxdX/obnK/6a1x/+pt8r/qbjK/6m5y/+sucv/rbnM/666zP+uusz/tcHT/4uYq/+Gk6f/'
    'm6zC/x8lLrQAAAAAAAAAAAAAAAAAAQEwdYN//5mnmP+6xrr/u8W3/7nDtP+Zopb/XGJZ7xUVFJMA'
    'AAAiAAAAAAAAAAAAAAAAERQV2pOgrv+pt8r/obDB/5+tv/+erL7/nqy+/6Kwwv+isML/jpyv/5Wj'
    'tv+Rn7H/kaCy/6W0xv9jb4f/WWZ8/6e0xf+eqbz/nKm8/52pvP+eqbz/oKy+/6CuwP+hsML/orHD'
    '/6Kxw/+jscP/pbPF/6Wzxf+mtMb/p7XH/6e1x/+gtsf/yNrs/7TL3P+is8X/qrjK/6m4yv+qucv/'
    'rLrM/666zP+uusz/rrrM/7bC1P+BjaD/jJyy/3eJnf8VFxuHAAAAAAAAAAAAAAAAAAAADDlCPO+c'
    'pZj/kpqQ/2VrZPQyNjK7BgYGbAAAABoAAAAAAAAAAAAAAAAAAAAAAAAABAcHB19ESFLxkp+1/6Ox'
    'w/+drLz/nKu9/5yrvf+cq73/nay+/5mnuv+Xo7X/m6a5/5+rvv+eqr3/o6/D/3F/kv+VorT/oay/'
    '/5urvf+cq73/nqy+/6CuwP+isMP/pLHD/6Sxxf+jscX/prPG/6e1x/+ntcf/qLbJ/6i2yf+otsn/'
    'orXG/7PI2f+syNf/prXH/6u5y/+rucv/rbrM/666zP+uusz/rrrM/6+7zf+tu87/fIic/4GSp/9k'
    'dYf/AwMEQQAAAAAAAAAAAAAAAAAAAAADBANOEBAPcwEAAEwAAAAdAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAABQYJl2Jwhf99jKP/oq/C/6Cvvv+erL7/nqy+/56svv+frb//n62/'
    '/56rvf+dqrz/nqq9/6KuwP+Pnq//eIaY/6Kwwv+erL7/nqy+/5+uwP+isMP/orHC/5yuwP+ftMX/'
    'nLTF/6S0yP+quMr/qbfK/6i2yf+otsn/qLbJ/6m3yf+itcf/pLbI/6q5y/+qucv/rLnL/666zP+u'
    'usz/rrrM/666zP+yvtD/oK7B/2Bvhf+Glqz/PUJM0QAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADBVYXD+e4+n'
    '/3aDmP+isML/orHC/5+tv/+frb//n62//56svv+erL7/nqy+/56svv+drL7/pLLE/4CPof+Lmaz/'
    'pbTG/6Cvwf+iscP/orHD/564yP+mxNP/vNHi/7/S4/+jusv/qLbI/6m4yv+puMr/qbfK/6i3yf+p'
    'uMr/qrjK/6u5y/+qucv/rrrM/666zP+uusz/r7vN/6+7zf+vu83/t8PU/4eUpv95jKD/YGt8/wQD'
    'BUUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAQEBHgAAAC4AAAAAGR0hv5qtv/+QnrH/c4CV/56rvv+kssT/oK7A/6Cuwf+grsD/'
    'oK7A/6CuwP+grsD/oK7A/6Kww/+isML/eYea/5uqvP+ntsj/prTG/6OyxP+ivs7/ydzt/87Z6//L'
    '2Or/qMHS/6S0xv+quMr/qbjK/6m4yv+puMr/qrjK/6y4y/+sucv/rLnL/666zP+uusz/rrrM/6+7'
    'zf+vu83/sLzN/6+7zv+Ej6X/lZ2s/wUGCIwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAICAlMuMDPsAAAAGgAAADJkbnr/'
    't8ba/5Ggsv9xf5L/nqy+/6e1x/+iscP/o7LE/6Oxw/+iscP/orHD/6Kxw/+iscP/pbTG/5mouv+A'
    'jqD/qLXH/6m3yf+otsj/oLXG/6zB0v/B1ej/p8PV/521xf+puMr/qbjK/6q5y/+qucv/qbnL/6q4'
    'yv+ruMv/rrrM/666zP+rt8n/rrrM/6+7zf+vu83/r7vN/7XA0v+YpLj/lKCz/3V7hPwAAAAbAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAkeICI/2ZveOAAAAAbEBIUlJ+tv/+ywNT/mKa4/3KBkv+frr//qbfJ/6Wzxf+k'
    's8X/pLLE/6Szxf+ls8X/o7LE/6OyxP+ot8n/mai6/4+fsf+pusv/qbnL/6q4yv+itcf/nrfI/6G3'
    'yf+qt8r/qbjK/6m4yv+qucv/q7nL/6y6zP+rusz/q7rM/6y6zP+sucv/prTH/6+7zf+vu87/r7vN'
    '/6+7zf+zwdP/foug/7K8zv9GSk/WAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADA2PMLT6Pr/a3Z/5gAAAF07'
    'PkXLuMXX/6680f+ap7v/eYeZ/6Gvwf+quMn/prTG/6a0xv+mtMb/prTG/6Szxf+ls8X/p7PF/6q4'
    'yv+gscP/na7B/6a3yf+puMr/qbjK/6q4yv+rucv/qbjK/6m4yv+puMr/qrnL/6u5y/+susz/rLrM'
    '/6y6zP+tu83/rLfK/6i0x/+wvc//r7vO/6+7zf+zv9H/n63A/4WTqP+0vc//FRYYjAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAFSiJWg/9/1//+Mmqf2DhIXzE9UXP63w9X/r73R/6KwxP+Hlar/mai8/6y5'
    'zv+ntsj/prXG/6a0xv+ktcb/n7TF/522x/+cs8T/pbfJ/6a0yf+js8b/qrnL/6q5y/+qucv/qrnL'
    '/6q5y/+qucv/qrnL/6q5y/+susz/rLrM/6y6zP+tusz/r7zO/6Gwwv+ptsj/r73P/6+7zf+vu83/'
    'tcPV/4GOpP+0wNP/e4GN/gAAAC4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB8gJLO1x9f/0On+/6C9'
    '1P88RFH/YGp4/6i2yf+zwNT/p7fL/4iXrf+PnLL/qrjM/6u5zP+ptsr/o7PF/6fE0v/G2On/uM/g'
    '/567y/+mt8n/q7nL/6q5y/+qucv/qrnL/6q5y/+qucv/qrnL/6q5y/+qucv/rLrM/6y6zP+susz/'
    'sb3P/6Kxw/+Vp7f/sb3O/7C7zv+uusz/t8TV/5mou/+Qn7P/v8fZ/yIjJ6gAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAYS1BW6b/T5f/E3fP/sMzl/3uNoP9pd4r/j5yx/6m4y/+su83/kJ6z'
    '/4WSp/+cq8H/rLvQ/6m4y/+lv87/xNjp/9Lf8f+80+P/n7XG/6u5y/+qucv/qrnL/6q5y/+qucv/'
    'qrnL/6y6zP+susz/rLrM/6y6zP+uusz/sLzP/5+wwf+JnK//pLTG/7G9zv+vuc3/t8TX/668z/+S'
    'n7T/wMzc/1RXYOQAAAAYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABkZGE5jaG//uc/i'
    '/8TZ8P+yy+L/n7LH/36Mnv+WpLf/rbvO/628zv+gr8L/h5Wr/4SVrP+cq7//p7fL/6O+0P+tyNr/'
    'psHS/6S3yf+rucv/qrnL/6u5y/+rusz/q7nL/6u6zP+susz/rLrM/627zf+uvM7/rbnM/5mnuf+I'
    'mqz/nq7C/7G+0/+0wNT/tMHV/56swf+VpLr/r7rL/1NVXOYAAAAyAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAALywsbmFmbf+vwdH/xt/z/6rJ3/+pvtT/qbfK/6m3yv+puMr/'
    'q7rM/669z/+drMD/iJmt/4eWrP+Qn7b/mazA/6i1yv+tus3/qrnL/6q5y/+rucv/rLrM/6y6zP+s'
    'usz/rbvN/668zv+mtcf/nq2//6y6zP+ktMX/rLrM/7W/0/+ksMb/lKG4/5Gdtf+Rna7/h4+Z/zQ2'
    'PMAAAAAiAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA6OTdi'
    'XmFk+pChsP/H3fL/tdLp/6e+1P+mtsv/qbfL/6q5y/+qucv/rbzN/6690P+ltMf/l6W5/4+csf+R'
    'nrP/m6m7/6u6zP+susz/rLrM/6y6zP+rucv/q7nL/6i2yP+cq73/jZ6w/5urvf+wvtD/rbnN/4WR'
    'pv9+jKH/ipes/4SPn/96go3/WFxj4CcmJ3kBAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADIyMkBcW1/YcnqD/6zC1P/H3/b/tM7j/6e70f+o'
    't8z/qbbK/6q4yv+rucv/q7rM/669zv+uvM//qbjK/6e2yP+susz/rLrM/6y6zP+susz/qbfJ/6a0'
    'xv+isML/orDC/6q3yf+xvM7/tcHT/4KOov+Zo7n/r7zR/2BodPcYGRl+ExUTSAwMDA4AAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAADQ0NDUZGRYFNUlPhe4WO/6/B0f/G3/T/wNjv/6/G3P+oucz/qrfK/6m4yv+quMr/q7nK/6q5'
    'y/+ru8z/rLrM/666zP+uusz/rrrM/666zP+vusz/r7vN/7G9zv+wu83/tsPV/4uarP+Nmaz/ytTl'
    '/2hudvIAAABBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADg4ODi4tLHAmJyiuTFJa6IaR'
    'of+tv9H/wNXp/8XY6//A0+b/u8zg/7nJ3f+4yNz/u8nd/7vJ3P+8yNz/vMnb/7zJ2/+7ydz/u8rb'
    '/7zK3P+/y9//wM/i/6Oxxf+TobT/sb3N/1RZYNoAAAA2AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABIAAABKDg8PjjE1OJpZYGiadoCKmnN+iZpweoaabXaD'
    'mmx1gJppc32aaXJ9mmhzfJppc3yaaHN+mmp0f5pud4OaZ3B9mk9ZZZpYYGuaYWVtmhscHoQAAAAR'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
)

_LOGO_B64_DATA = base64.b64decode(_LOGO_B64)


def get_logo(kind='png'):
    """读取项目 logo.ico：'ico' 原样返回，'png' 转为 PNG（取最大帧，带缓存）。
    兼容多种部署布局：项目根 / webui 目录 / 当前工作目录。"""
    global _logo_cache
    if kind in _logo_cache:
        return _logo_cache[kind]
    data = None
    for cand in (os.path.join(BASE_DIR, 'logo.ico'),
                 os.path.join(WEBUI_DIR, 'logo.ico'),
                 os.path.join(os.getcwd(), 'logo.ico')):
        if os.path.exists(cand):
            with open(cand, 'rb') as f:
                data = f.read()
            break
    if data is None:
        # 发布包不再携带 logo.ico: 回退到内嵌数据
        data = _LOGO_B64_DATA
    if data is None:
        return None
    if kind == 'ico':
        _logo_cache[kind] = data
        return data
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        data = buf.getvalue()
        _logo_cache[kind] = data
        return data
    except Exception:
        return None

# 地图树缓存（目录 mtime 变化时失效）
_maps_cache = {}


def read_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(data):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def build_map_tree():
    map_dir = os.path.join(BASE_DIR, 'map')
    try:
        dir_mtime = os.path.getmtime(map_dir)
    except OSError:
        return {}
    cached = _maps_cache.get('tree')
    if cached and cached[0] == dir_mtime:
        return cached[1]

    tree = {}
    for version in sorted(os.listdir(map_dir)):
        vdir = os.path.join(map_dir, version)
        if not os.path.isdir(vdir):
            continue
        planets = {}
        files = sorted(f for f in os.listdir(vdir) if f.endswith('.json'))
        for fname in files:
            m = re.match(r'map_(\d+)-(\d+)_(\d+)\.json', fname)
            if not m:
                continue
            main, side, seq = m.group(1), m.group(2), m.group(3)
            name, author = '', ''
            try:
                with open(os.path.join(vdir, fname), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                name = data.get('name', '')
                author = data.get('author', '')
            except Exception:
                pass
            planets.setdefault(main, []).append({
                'file': fname,
                'id': f'{main}-{side}_{seq}',
                'label': f'{main}-{side}-{seq}',
                'name': name,
                'author': author,
            })
        tree[version] = planets

    _maps_cache['tree'] = (dir_mtime, tree)
    return tree


def read_log_tail(lines=200):
    """读取日志文件尾部 N 行（大文件时从文件末尾 seek，避免全量读入内存）"""
    try:
        limit = max(1, min(int(lines), 5000))
        with open(LOG_PATH, 'rb') as f:
            # 从末尾向前读最多 4MB，足够覆盖 5000 行
            f.seek(0, os.SEEK_END)
            size = f.tell()
            read_size = min(size, 4 * 1024 * 1024)
            f.seek(size - read_size)
            data = f.read().decode('utf-8', errors='replace')
        tail = data.splitlines()
        return tail[-limit:]
    except Exception:
        return []


# ============ 锄地进程运行控制（单例） ============
_RUN = {
    'proc': None,
    'mode': None,
    'started_at': None,
    'exited_at': None,
    'exit_code': None,
    'output': deque(maxlen=500),
    'lock': threading.Lock(),
}

RUN_MODES = {
    'normal': {
        # 用 launch.py 启动：embeddable Python 下直接跑 fhoe.py 会找不到同目录模块
        'args': ['webui/launch.py'],
        'desc': '默认锄地（按 config.json 的优先星球开始，无需交互）',
    },
    'white': {
        'args': ['webui/launch.py', '--white'],
        'desc': '白名单锄地（仅运行 allowlist_map 中的地图）',
    },
    'record': {
        'args': ['webui/launch.py', '--record'],
        'desc': '录制地图（F9 保存，录制中请操作游戏）',
    },
    'install': {
        'args': ['utils/install_requirements.py'],
        'desc': '安装/检查依赖（pip）',
    },
}

# 模式中文名（前端展示）
MODE_NAMES = {
    'normal': '默认锄地', 'white': '白名单锄地', 'record': '录制地图',
    'install': '安装依赖', 'map': '选图运行', 'devmap': '开发者选图运行',
}


def _decode_line(raw):
    """逐行容错解码：子进程输出可能是 UTF-8（Python 脚本）或 GBK（ping 等原生程序），
    先按 UTF-8 严格解码，失败回退 GBK，避免中文乱码。"""
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('gbk', errors='replace')


def _run_reader(proc):
    """后台线程：持续读取子进程输出到环形缓冲（清洗 loguru ANSI 颜色码）"""
    try:
        while True:
            raw = proc.stdout.readline()
            if not raw:
                break
            line = _decode_line(raw)
            # 主程序 loguru colorize=True，管道模式下也会输出 ANSI 颜色码（如 \x1b[36m），
            # 在 WebUI 里会显示为乱码，这里统一清洗
            line = re.sub(r'\x1b\[[0-9;]*m', '', line)
            _RUN['output'].append(line.rstrip('\r\n'))
    except Exception:
        pass


# 打包环境检测:同目录有 Fhoe-Rail.exe 时,WebUI 启动锄地直接用 exe(无需 Python)
FHOE_EXE = os.path.join(BASE_DIR, 'Fhoe-Rail.exe')


def run_start(mode, map_id=None):
    """启动锄地进程（单例：已有进程时拒绝）
    mode: normal/white/record/install/map/devmap
    map_id: 仅 map/devmap 模式需要，如 '3-5_1'
    打包环境（同目录有 Fhoe-Rail.exe）直接用 exe；源码环境用 python + launch.py
    """
    with _RUN['lock']:
        if _RUN['proc'] is not None and _RUN['proc'].poll() is None:
            return {'ok': False, 'error': '已有锄地进程在运行，请先停止'}

        if mode in ('map', 'devmap'):
            if not map_id:
                return {'ok': False, 'error': '选图模式需要提供地图 ID'}
            args = (['webui/launch.py', '--dev', '--map', map_id] if mode == 'devmap'
                    else ['webui/launch.py', '--map', map_id])
        elif mode in RUN_MODES:
            args = RUN_MODES[mode]['args']
        else:
            return {'ok': False, 'error': f'未知模式: {mode}'}

        if os.path.exists(FHOE_EXE):
            # 打包环境: 直接用 Fhoe-Rail.exe
            if mode == 'install':
                return {'ok': False, 'error': '打包版无需安装依赖，请直接双击 Fhoe-Rail.exe 运行'}
            exe_args = [FHOE_EXE]
            if mode == 'white':
                exe_args.append('--white')
            elif mode == 'record':
                exe_args.append('--record')
            elif mode == 'map':
                exe_args += ['--map', map_id]
            elif mode == 'devmap':
                exe_args += ['--dev', '--map', map_id]
            args = exe_args
        else:
            args = [PYTHON_BIN] + args

        try:
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'  # 强制子进程 stdout 无缓冲，输出实时可见
            proc = subprocess.Popen(
                args,
                cwd=BASE_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
        except OSError as e:
            if getattr(e, 'winerror', None) == 740:
                # 打包版 exe 若带 requireAdministrator 清单(旧版/自建),普通权限无法直接启动
                return {'ok': False, 'error': 'Fhoe-Rail.exe 需要管理员权限(旧版打包)。请重新下载不带提权的新版,或右键“以管理员身份运行”本窗口。'}
            return {'ok': False, 'error': f'启动失败: {e}'}
        except Exception as e:
            return {'ok': False, 'error': f'启动失败: {e}'}
        _RUN['proc'] = proc
        _RUN['mode'] = mode
        if map_id:
            _RUN['mode'] = f'{mode}:{map_id}'
        _RUN['started_at'] = time.time()
        _RUN['exited_at'] = None
        _RUN['exit_code'] = None
        _RUN['output'].clear()
        threading.Thread(target=_run_reader, args=(proc,), daemon=True).start()
        return {'ok': True, 'mode': mode, 'pid': proc.pid}


def run_status():
    """当前锄地进程状态 + 最近输出"""
    with _RUN['lock']:
        proc = _RUN['proc']
        if proc is None:
            return {'running': False, 'output': list(_RUN['output'])}
        code = proc.poll()
        if code is not None and _RUN['exit_code'] is None:
            _RUN['exit_code'] = code
            _RUN['exited_at'] = time.time()
        uptime = None
        if _RUN['started_at']:
            uptime = round(time.time() - _RUN['started_at'], 1)
        return {
            'running': code is None,
            'pid': proc.pid,
            'mode': _RUN['mode'],
            'exit_code': _RUN['exit_code'],
            'uptime': uptime,
            'output': list(_RUN['output']),
        }


def run_stop():
    """停止锄地进程"""
    with _RUN['lock']:
        proc = _RUN['proc']
        if proc is None or proc.poll() is not None:
            return {'ok': False, 'error': '没有正在运行的锄地进程'}
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
        _RUN['exit_code'] = proc.poll()
        _RUN['exited_at'] = time.time()
        return {'ok': True, 'exit_code': _RUN['exit_code']}


def parse_log_stats(tail_lines):
    """从日志尾部解析运行统计（尽力而为，解析不到显示为空）"""
    stats = {
        'fight_cnt': None, 'no_fight_cnt': None, 'fight_time': None,
        'save_time': None, 'stuck_cnt': None, 'error_fight': None,
        'snack_used': None, 'recent_maps': [], 'total_time': None,
    }
    text = ''.join(tail_lines)
    for line in tail_lines:
        if '准备开始路线' in line:
            m = re.search(r'准备开始路线：(.+)', line)
            if m:
                stats['recent_maps'].append(m.group(1).strip())
    stats['recent_maps'] = stats['recent_maps'][-8:]
    for key, pat in [
        ('fight_cnt', r'战斗次数：(\d+)'),
        ('no_fight_cnt', r'未战斗次数：(\d+)'),
        ('fight_time', r'总计战斗用时 ([\d.]+分[\d.]+秒|[\d.]+秒|[\d.]+小时[\d.]+分[\d.]+秒)'),
        ('save_time', r'疾跑节约的时间为 ([\d.]+分[\d.]+秒|[\d.]+秒|[\d.]+小时[\d.]+分[\d.]+秒)'),
        ('stuck_cnt', r'系统卡顿次数：(\d+)'),
        ('error_fight', r'异常战斗识别（战斗时间 < \d+ 秒）次数：(\d+)'),
        ('snack_used', r'奇巧零食使用次数：(\d+)'),
        ('total_time', r'总计用时 ([\d.]+分[\d.]+秒|[\d.]+秒|[\d.]+小时[\d.]+分[\d.]+秒)'),
    ]:
        m = re.search(pat, text)
        if m:
            stats[key] = m.group(1)
    return stats


class Handler(BaseHTTPRequestHandler):
    server_version = 'FhoeRailWebUI/1.0'
    # POST body 上限（1MB），防止恶意超大请求耗尽内存
    MAX_BODY = 1024 * 1024

    def _check_host_origin(self):
        """安全校验：防 DNS rebinding 与跨站请求。
        只允许本机来源（Host/Origin 为 127.0.0.1 / localhost / ::1）。
        """
        from urllib.parse import urlparse
        host = self.headers.get('Host', '')
        if host:
            hostname = host.split(':')[0].lower()
            if hostname not in ('127.0.0.1', 'localhost', '::1', '[::1]'):
                return False
        origin = self.headers.get('Origin', '')
        if origin:
            o = urlparse(origin)
            if o.hostname not in ('127.0.0.1', 'localhost', '::1'):
                return False
        return True

    def _send(self, code, body, content_type='application/json; charset=utf-8'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._check_host_origin():
            self._send(403, {'error': 'forbidden: 仅允许本机访问'})
            return
        try:
            if path == '/' or path == '/index.html':
                with open(os.path.join(WEBUI_DIR, 'index.html'), 'rb') as f:
                    html = f.read()
                self._send(200, html, 'text/html; charset=utf-8')
            elif path == '/favicon.ico':
                data = get_logo('ico')
                if data:
                    self._send(200, data, 'image/x-icon')
                else:
                    self._send(404, {'error': 'logo not found'})
            elif path == '/logo.png':
                data = get_logo('png')
                if data:
                    self._send(200, data, 'image/png')
                else:
                    self._send(404, {'error': 'logo not found'})
            elif path == '/api/config':
                _cfg = read_config()
                if not _cfg.get('version'):
                    # 兜底: 发布包 version.txt(CI 打 tag 构建时写入 tag 名);
                    # config.json 的 version 只有运行过锄地程序才会写入
                    try:
                        with open(os.path.join(BASE_DIR, 'version.txt'), 'r', encoding='utf-8') as _f:
                            _v = _f.read().strip()
                        if _v:
                            _cfg['version'] = _v
                    except Exception:
                        pass
                self._send(200, _cfg)
            elif path == '/api/maps':
                self._send(200, build_map_tree())
            elif path == '/api/map':
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                file = qs.get('file', [''])[0]
                version = qs.get('version', [''])[0]
                # 路径安全校验：只允许读取 map 目录下的合法地图 JSON
                if not re.match(r'^[A-Za-z0-9_]+$', version):
                    self._send(400, {'error': 'bad version'})
                    return
                if not re.match(r'^map_\d+-\d+_\d+\.json$', file):
                    self._send(400, {'error': 'bad file'})
                    return
                fpath = os.path.join(BASE_DIR, 'map', version, file)
                if not os.path.exists(fpath):
                    self._send(404, {'error': 'map not found'})
                    return
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._send(200, data)
            elif path == '/api/logs':
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                lines = int(qs.get('lines', ['200'])[0])
                self._send(200, read_log_tail(lines))
            elif path == '/api/notes':
                """新图注意事项图片列表"""
                try:
                    files = sorted(f for f in os.listdir(NOTES_DIR)
                                   if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')))
                except OSError:
                    files = []
                self._send(200, files)
            elif path == '/notes-img':
                """新图注意事项图片（文件名白名单校验，防路径穿越）"""
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                name = qs.get('name', [''])[0]
                if not re.match(r'^[\u4e00-\u9fff\w\-, ]+\.(png|jpg|jpeg|webp|gif)$', name, re.I):
                    self._send(400, {'error': 'bad name'})
                    return
                if '/' in name or '\\' in name or '..' in name:
                    self._send(400, {'error': 'bad name'})
                    return
                fpath = os.path.join(NOTES_DIR, name)
                if not os.path.exists(fpath):
                    self._send(404, {'error': 'not found'})
                    return
                with open(fpath, 'rb') as f:
                    data = f.read()
                ext = name.rsplit('.', 1)[-1].lower()
                ct = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                      'webp': 'image/webp', 'gif': 'image/gif'}.get(ext, 'application/octet-stream')
                self._send(200, data, ct)
            elif path == '/api/stats':
                cfg = read_config()
                tree = build_map_tree()
                total_maps = sum(len(v) for ver in tree.values() for v in ver.values())
                stats = parse_log_stats(read_log_tail(1500))
                self._send(200, {
                    'config': cfg,
                    'map_total': total_maps,
                    'map_versions': {k: sum(len(v) for v in ver.values()) for k, ver in tree.items()},
                    'log_stats': stats,
                    'planet_names': PLANET_NAMES,
                })
            elif path == '/api/run':
                self._send(200, run_status())
            else:
                self._send(404, {'error': 'not found'})
        except FileNotFoundError:
            self._send(404, {'error': f'file not found: {path}'})
        except Exception as e:
            self._send(500, {'error': str(e)})

    def do_POST(self):
        parsed = urlparse(self.path)
        if not self._check_host_origin():
            self._send(403, {'error': 'forbidden: 仅允许本机访问'})
            return
        if parsed.path == '/api/config':
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length > self.MAX_BODY:
                    self._send(413, {'ok': False, 'error': '请求体过大'})
                    return
                raw = self.rfile.read(length)
                data = json.loads(raw.decode('utf-8'))
                if not isinstance(data, dict):
                    raise ValueError('config 必须是 JSON 对象')
                save_config(data)
                self._send(200, {'ok': True, 'saved': True})
            except Exception as e:
                self._send(400, {'ok': False, 'error': str(e)})
        elif parsed.path == '/api/run':
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length > self.MAX_BODY:
                    self._send(413, {'ok': False, 'error': '请求体过大'})
                    return
                raw = self.rfile.read(length)
                data = json.loads(raw.decode('utf-8'))
                mode = data.get('mode', 'normal')
                self._send(200, run_start(mode, data.get('map')))
            except Exception as e:
                self._send(400, {'ok': False, 'error': str(e)})
        elif parsed.path == '/api/run/stop':
            self._send(200, run_stop())
        elif parsed.path == '/api/notify/test':
            try:
                from utils.notify import Notify
                ok = Notify().send_test()
                self._send(200, {'ok': ok, 'note': '通知已发送，请检查手机/客户端' if ok else '发送失败，请检查配置（总开关、渠道、密钥）'})
            except Exception as e:
                self._send(500, {'ok': False, 'error': str(e)})
        else:
            self._send(404, {'error': 'not found'})

    def log_message(self, fmt, *args):
        pass  # 静默访问日志，避免刷屏


class Server(ThreadingHTTPServer):
    # Windows 下默认 allow_reuse_address=True 会让两个实例绑定同一端口,
    # 导致端口占用检测失效;显式关闭以便重复启动时报错提示。
    allow_reuse_address = False


def main():
    print('=' * 50)
    print('  Fhoe-Rail WebUI')
    print('  项目目录:', BASE_DIR)
    print('  请用浏览器打开: http://127.0.0.1:%d' % PORT)
    print('  按 Enter 结束服务（或 Ctrl+C）')
    print('=' * 50)
    try:
        server = Server(('127.0.0.1', PORT), Handler)
    except OSError as e:
        print(f'[错误] 端口 {PORT} 已被占用: {e}')
        print('可能原因: WebUI 已在运行(请直接打开 http://127.0.0.1:%d)，或该端口被其他程序占用。' % PORT)
        print('解决: 关闭已运行的 WebUI 窗口后重试; 或修改 webui/server.py 中的 PORT 换一个端口。')
        sys.exit(1)
    threading.Timer(1.0, lambda: webbrowser.open(f'http://127.0.0.1:{PORT}')).start()

    def _enter_watcher():
        """监听控制台 Enter 触发优雅关闭。
        打包版(exe)下 Ctrl+C 不可靠; stdin 被重定向(后台运行)时
        readline() 返回 ''(EOF),此时继续等待,不退出。"""
        while True:
            try:
                line = sys.stdin.readline()
            except Exception:
                line = ''
            if line == '':
                time.sleep(0.5)
                continue
            break
        print('\n收到 Enter,正在关闭服务...')
        try:
            server.shutdown()  # 使 serve_forever 返回(须在其他线程调用)
        except Exception:
            pass

    threading.Thread(target=_enter_watcher, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n收到 Ctrl+C,正在关闭服务...')
    finally:
        try:
            server.server_close()
        except Exception:
            pass
        print('服务已关闭，窗口即将退出')


if __name__ == '__main__':
    main()
