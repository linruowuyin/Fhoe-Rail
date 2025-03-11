import datetime
import os
import subprocess
import sys
import time
import traceback

import pyuac

from get_width import check_mult_screen
from utils.config.config import ConfigurationManager
from utils.log import fetch_php_file_content, log
from utils.map_utils.map_operations import MapOperations
from utils.map_utils.map_info import MapInfo
from utils.map_utils.map_selector import choose_map, choose_map_debug
from utils.setting import Setting
from utils.time_utils import TimeUtils
from utils.window import Window

cfg = ConfigurationManager()
time_mgr = TimeUtils()
map_info_instance = MapInfo()
setting = Setting()

def filter_content(content, keyword):
    # 将包含指定关键词的部分替换为空字符串
    return content.replace(keyword, "")


def print_version():
    try:
        with open("version.txt", "r", encoding="utf-8") as file:
            version = file.read().strip()
            log.info(f"当前版本：{version}")
        log.info(f"{cfg.CONFIG_FILE_NAME}")
        ConfigurationManager.modify_json_file(
            ConfigurationManager.CONFIG_FILE_NAME, "version", version)
        cfg.config_file.get("version", "")
    except (FileNotFoundError, IOError) as e:
        log.error(f"版本文件读取错误: {e}")


def print_info():
    log.info("")  # 添加一行空行
    php_content = fetch_php_file_content()  # 获取PHP文件的内容
    filtered_content = filter_content(php_content, "舔狗日记")  # 过滤关键词
    log.info("\n" + filtered_content)  # 将过滤后的内容输出到日志
    log.info("")  # 添加一行空行
    log.info("=" * 60)
    log.info("开始运行")
    print_version()


def print_end():
    log.info("结束运行")
    log.info("=" * 60)


def main():

    start_in_mid = False  # 是否为优先地图，优先地图完成后自动从1-1_0开始
    dev = False  # 初始开发者模式，为否

    if len(sys.argv) > 1:
        if sys.argv[1] == "--debug":
            cfg.main_start()
            start = choose_map_debug(map_info_instance)
        elif sys.argv[1] == "--config":
            cfg.main_start_rewrite(setting)
            start = choose_map_debug(map_info_instance)
        elif sys.argv[1] == "--dev":
            cfg.main_start()
            start = choose_map_debug(map_info_instance)
            dev = True  # 设置开发者模式
        elif sys.argv[1] == "--white":
            cfg.main_start()
            start = choose_map(map_info_instance)
            cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "allowlist_mode_once", True)  # 启用一次白名单模式
        elif sys.argv[1] == "--record":
            from utils.record import record_main
            record_main()
            return
        else:
            cfg.main_start()
            start = choose_map(map_info_instance)
    else:
        cfg.main_start()
        start = choose_map(map_info_instance)

    if isinstance(start, tuple):
        start_in_mid, start = start[1], start[0]

    if start:
        cfg.config_fix()
        log.info(f"config.json:{cfg.load_config()}")
        log.info("切换至游戏窗口，请确保1号位角色普攻为远程，黄泉地图1号位为黄泉")
        check_mult_screen()
        Window().switch_window()
        map_instance = MapOperations()
        time.sleep(0.5)
        log.info("开始运行，请勿移动鼠标和键盘.向着星...呃串台了")
        log.info("黑塔：7128；雅利洛：19440；罗浮：42596；匹诺康尼：30996")
        log.info("2.0版本单角色锄满100160经验（fhoe当前做不到）")
        log.info("免费软件，倒卖的曱甴冚家铲，请尊重他人的劳动成果")
        start_time = datetime.datetime.now()
        map_instance.process_map(start, start_in_mid, dev=dev)  # 读取配置
        start_map = "1-1_0"
        allow_run_again = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
            "allow_run_again", False
        )
        if allow_run_again:
            map_instance.process_map(start_map, start_in_mid, dev=dev)
        end_time = datetime.datetime.now()
        shutdown_type = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
            "auto_shutdown", 0
        )
        shutdown_computer(shutdown_type)
        if cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
            "allow_run_next_day", False
        ):
            log.info("开始执行跨日连锄")
            if time_mgr.has_crossed_4am(start=start_time, end=end_time):
                log.info("检测到换日，即将从头开锄")
                map_instance.process_map(start_map, start_in_mid, dev=dev)
            else:
                map_instance.handle.back_to_main(delay=2.0)
                now = datetime.datetime.now()
                refresh_hour = cfg.config_file.get("refresh_hour", 4)
                refresh_minute = cfg.config_file.get("refresh_minute", 0)
                next_4am = now.replace(
                    hour=refresh_hour, minute=refresh_minute, second=0, microsecond=0
                )
                if now.hour >= refresh_hour and now.minute >= refresh_minute:
                    next_4am += datetime.timedelta(days=1)
                wait_time = (next_4am - now).total_seconds()
                wait_time += 60
                if wait_time <= 14400:
                    log.info(f"等待 {wait_time:.0f} 秒后游戏换日重锄")
                    time.sleep(wait_time)
                    map_instance.process_map(start_map, start_in_mid, dev=dev)
                else:
                    log.info("等待时间过久，结束跨日连锄，等待时间需要 < 4小时")
        # shutdown_type = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get('auto_shutdown', 0)
        # shutdown_computer(shutdown_type)
        if dev:  # 开发者模式自动重选地图
            main()
    else:
        log.info("前面的区域，以后再来探索吧")
        main()


def shutdown_computer(shutdown_type):
    if shutdown_type == 0:
        pass
    elif shutdown_type == 1:
        log.info("下班喽！I'm free!")
        os.system("shutdown /s /f /t 10")
    elif shutdown_type == 2:
        log.info("10秒后注销")
        time.sleep(10)
        os.system("shutdown /l /f")
    elif shutdown_type == 3:
        log.info("关闭指定进程")
        taskkill_name = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
            "taskkill_name", None
        )
        if taskkill_name:
            subprocess.call(["taskkill", "/im", taskkill_name, "/f"])
    else:
        log.info("shutdown_type参数不正确")


if __name__ == "__main__":
    try:
        if not pyuac.isUserAdmin():
            pyuac.runAsAdmin()
        else:
            print_info()
            main()
            print_end()
    except ModuleNotFoundError as e:
        print(traceback.format_exc())
        log.error(traceback.format_exc())
        print("请重新运行")
        input("按回车键退出")
    except NameError as e:
        print(traceback.format_exc())
        log.error(traceback.format_exc())
        print("请重新运行")
        input("按回车键退出")
    except Exception as e:
        print(traceback.format_exc())
        log.error(traceback.format_exc())
        print("请重新运行")
        input("按回车键退出")
    except BaseException as e:
        print(traceback.format_exc())
        log.error(traceback.format_exc())
        print("请重新运行")
        input("按回车键退出")
