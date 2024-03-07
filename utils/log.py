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
import datetime
from loguru import logger

try:
    from .requests import post
except:
    from requests import post


def get_ver():
    from .config import ConfigurationManager
    cfg = ConfigurationManager()
    VER = cfg.CONFIG.get("version", "")
    if VER == "":
        month, day, hour, minute = get_folder_modified_time('map')
        VER = f"{month:02d}{day:02d}{hour:02d}{minute:02d}"
    return VER

log = logger
dir_log = "logs"
path_log = os.path.join(dir_log, '日志文件.log')

def update_extra(record):
    module = record["module"]
    function = record["function"]
    line = record["line"]
    version = get_ver()
    # 将额外信息更新到记录字典中
    record["new_module"] = f"{module}.{function}:{line}"
    record["VER"] = f"{version}"

log = logger.patch(update_extra)
    
logger.remove()
logger.add(sys.stdout, level='INFO', colorize=True,
            format="<cyan>{module}</cyan>.<cyan>{function}</cyan>"
                    ":<cyan>{line}</cyan> - "+"<cyan>{VER}</cyan> - "
                    "<level>{message}</level>"
            )

log.add(path_log,
            format="{time:HH:mm:ss} - "
                    "{level:<6} \t| "
                    "<cyan>{new_module:<40}</cyan> \t- "+"<cyan>{VER}</cyan> - "+"{message}",
            rotation='0:00', enqueue=True, serialize=False, encoding="utf-8", retention="10 days")

def webhook_and_log(message):
    log.info(message)
    from .config import ConfigurationManager # Circular import
    cfg = ConfigurationManager()
    url = cfg.read_json_file(filename=cfg.CONFIG_FILE_NAME, path=False).get("webhook_url")
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

def get_folder_modified_time(folder_path):
    """
    获取文件夹的修改时间
    :param folder_path: 文件夹路径
    :return: 修改时间的月日时分
    """
    try:
        modified_time = os.path.getmtime(folder_path)
        modified_datetime = datetime.datetime.fromtimestamp(modified_time)
        
        # 提取月、日、时、分
        month = modified_datetime.month
        day = modified_datetime.day
        hour = modified_datetime.hour
        minute = modified_datetime.minute
        
        return month, day, hour, minute
    except Exception as e:
        print(f"Error: {e}")
        return None