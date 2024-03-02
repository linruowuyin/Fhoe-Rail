'''
Author: Night-stars-1 nujj1042633805@gmail.com
Date: 2023-05-12 23:22:54
LastEditors: Night-stars-1 nujj1042633805@gmail.com
LastEditTime: 2023-05-14 01:22:36
FilePath: \Honkai-Star-Rail-beta-2.4h:\Download\Zip\Honkai-Star-Rail-beta-2.7\tools\log.py
Description: 

Copyright (c) 2023 by ${git_name_email}, All Rights Reserved. 
'''
import os
import sys
import requests
from loguru import logger

try:
    from .requests import post
except:
    from requests import post

VER = "2.061"
log = logger
dir_log = "logs"
path_log = os.path.join(dir_log, '日志文件.log')

def update_extra(record):
    module = record["module"]
    function = record["function"]
    line = record["line"]

    # 将额外信息更新到记录字典中
    record["new_module"] = f"{module}.{function}:{line}"

log = logger.patch(update_extra)
    
logger.remove()
logger.add(sys.stdout, level='INFO', colorize=True,
            format="<cyan>{module}</cyan>.<cyan>{function}</cyan>"
                    ":<cyan>{line}</cyan> - "+f"<cyan>{VER}</cyan> - "
                    "<level>{message}</level>"
            )

log.add(path_log,
            format="{time:HH:mm:ss} - "
                    "{level:<6} \t| "
                    "{new_module:<40} \t- "+f"<cyan>{VER}</cyan> - "+"{message}",
            rotation='0:00', enqueue=True, serialize=False, encoding="utf-8", retention="10 days")

def webhook_and_log(message):
    log.info(message)
    from .config import read_json_file # Circular import
    url = read_json_file("config.json", False).get("webhook_url")
    if url == "" or url == None:
        return
    try:
        post(url, json={"content": message})
    except Exception as e:
        log.error(f"Webhook发送失败: {e}")

def fetch_php_file_content():
    php_urls = [
        "https://wanghun.top/api/tgrj.php",
        "http://api.ay15.cn/api/tiangou/api.php?charset=utf-8"
    ]

    for url in php_urls:
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.text
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError):
            pass

    return ""
