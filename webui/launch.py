# -*- coding: utf-8 -*-
"""
Fhoe-Rail 通用启动器

本机 Python 为 embeddable 配置（python313._pth），运行脚本时脚本所在目录不会
加入 sys.path，直接 `python fhoe.py` 会报 ModuleNotFoundError。
本文件将项目根目录注入 sys.path 后，以主模块方式执行 fhoe.py，命令行参数原样透传。

用法（在项目根目录）:
    python webui/launch.py [--debug|--white|--dev|--record|--test|...]
"""
import os
import runpy
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

runpy.run_path(os.path.join(PROJECT_ROOT, 'fhoe.py'), run_name='__main__')
