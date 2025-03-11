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
import datetime
import requests
from loguru import logger
from utils.requests import post

# 日志配置
log = logger
LOG_DIR = "logs"
PATH_LOG = os.path.join(LOG_DIR, '日志文件.log')

def get_folder_modified_time(folder_path):
    """获取文件夹的修改时间

    Args:
        folder_path (str): 文件夹路径

    Returns:
        tuple: 修改时间的月日时分，如果获取失败则返回None
    """
    try:
        modified_time = os.path.getmtime(folder_path)
        modified_datetime = datetime.datetime.fromtimestamp(modified_time)

        month = modified_datetime.month
        day = modified_datetime.day
        hour = modified_datetime.hour
        minute = modified_datetime.minute

        return month, day, hour, minute
    except Exception as e:
        log.error(f"获取文件夹修改时间失败: {e}")
        return None

def get_ver() -> str:
    """获取当前版本号

    首先尝试从version.txt文件读取版本号，如果读取失败或版本号为空，
    则根据map文件夹的最后修改时间生成版本号。

    Returns:
        str: 版本号字符串，格式为MMDDHHMM（月日时分）
    """
    try:
        with open("version.txt", "r", encoding="utf-8") as file:
            version = file.read().strip()
            if version:  # 只在version不为空时返回
                return version
    except (FileNotFoundError, IOError):
        pass

    # 如果version.txt不存在或为空，使用map文件夹修改时间作为版本号
    try:
        result = get_folder_modified_time('map')
        if result:
            month, day, hour, minute = result
            return f"{month:02d}{day:02d}{hour:02d}{minute:02d}"
    except Exception as e:
        log.error(f"获取map文件夹修改时间失败: {e}")

    return "00000000"  # 当所有获取版本号的方式都失败时返回默认值

def update_extra(record):
    """更新日志记录的额外信息

    Args:
        record (dict): 日志记录字典
    """
    module = record["module"]
    function = record["function"]
    line = record["line"]
    version = get_ver()
    record["new_module"] = f"{module}.{function}:{line}"
    record["VER"] = f"{version}"

def webhook_and_log(message):
    """发送webhook消息并记录日志

    Args:
        message (str): 要发送的消息
    """
    log.info(message)
    from utils.config.config import ConfigurationManager  # Circular import
    cfg = ConfigurationManager()
    url = cfg.read_json_file(
        filename=cfg.CONFIG_FILE_NAME, path=False).get("webhook_url")
    if url == "" or url is None:
        return
    try:
        post(url, json={"content": message})
    except Exception as e:
        log.error(f"Webhook发送失败: {e}")

def fetch_php_file_content():
    """获取PHP接口内容

    Returns:
        str: 接口返回的文本内容，如果获取失败则返回空字符串
    """
    php_urls = [
        "https://wanghun.top/api/tgrj.php",
        "http://api.ay15.cn/api/tiangou/api.php?charset=utf-8"
    ]

    for url in php_urls:
        try:
            response = requests.get(url, timeout=1)
            response.raise_for_status()
            return response.text
        except requests.exceptions.Timeout:
            return ""
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError):
            pass

    return ""

# 配置日志记录器
log = logger.patch(update_extra)

logger.remove()
log.add(sys.stdout, level='INFO', colorize=True,
        format="{time:HH:mm:ss.SSS} - "
        "<cyan>{module}.{function}:{line}</cyan> - "+"<cyan>{VER}</cyan> - "
        "<level>{message}</level>"
        )

log.add(PATH_LOG,
        format="{time:HH:mm:ss.SSS} - "
        "{level:<6} \t| "
        "<cyan>{new_module:<40}</cyan> \t- " +
        "<cyan>{VER}</cyan> - "+"{message}",
        rotation='0:00', enqueue=True, serialize=False, encoding="utf-8", retention="7 days")

log.info("=" * 60)
