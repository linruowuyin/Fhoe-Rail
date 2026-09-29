# -*- coding: utf-8 -*-
import os
import sys

# 强制控制台使用UTF-8编码，防止cp932等非中文编码导致UnicodeEncodeError
os.environ["PYTHONIOENCODING"] = "utf-8"
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name)
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import datetime
import subprocess
import time
import traceback

import pyuac

# 日文系统(cp932)下中文输出会崩,统一把 stdout/stderr 改成 UTF-8
# 要在 import utils.core.log 之前执行
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass  # 部分环境（如某些重定向场景）不支持 reconfigure，忽略即可

from get_width import check_mult_screen
from utils.config.config import ConfigurationManager
from utils.core.log import fetch_php_file_content, log
from utils.flows.map_operations import MapOperations
from utils.core.map_info import MapInfo
from utils.ui.map_selector import choose_map, choose_map_debug
from utils.core.notify import Notify, get_error_summary
from utils.ui.setting import Setting
from utils.core.time_utils import TimeUtils
from utils.drivers.window import Window

cfg = ConfigurationManager()
time_mgr = TimeUtils()
map_info_instance = MapInfo()
setting = Setting()
notify = Notify()


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
            ConfigurationManager.CONFIG_FILE_NAME, "version", version
        )
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
    # 清理 keyboard 全局监听（Pause 注册的 F7-F10 监听线程非 daemon，
    # 不清理会导致进程结束后无法退出）
    try:
        import keyboard

        keyboard.unhook_all()
    except Exception:
        pass


def parse_map_arg():
    """解析 --map <地图ID> 参数：非交互指定起始地图（供 WebUI 选图运行/开发者选图使用）
    例如: fhoe.py --dev --map 3-5_1
    """
    if "--map" in sys.argv:
        idx = sys.argv.index("--map")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


def parse_map_version_arg():
    """解析 --map-version <版本名> 参数：临时覆盖地图版本（供 WebUI 选图运行使用）"""
    if "--map-version" in sys.argv:
        idx = sys.argv.index("--map-version")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


def main():

    start_in_mid = False  # 是否为优先地图，优先地图完成后自动从1-1_0开始
    dev = False  # 初始开发者模式，为否
    map_arg = parse_map_arg()  # --map 参数：非交互指定起始地图（WebUI 选图运行）
    single_map_mode = map_arg is not None

    # WebUI 选图运行：若指定了 --map-version，临时切换地图版本（单图运行完后进程即退出）
    map_version_arg = parse_map_version_arg()
    if map_version_arg and map_arg:
        cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "map_version", map_version_arg)
        # 直接同步 MapInfo 单例缓存，避免 property 延迟检测
        map_info_instance._map_version = map_version_arg
        log.info(f"[单图运行] 临时切换地图版本: {map_version_arg}")

    if len(sys.argv) > 1:
        if sys.argv[1] == "--map":
            cfg.main_start()
            start = (map_arg, False)
        elif sys.argv[1] == "--debug":
            cfg.main_start()
            start = (
                choose_map_debug(map_info_instance) if not map_arg else (map_arg, False)
            )
        elif sys.argv[1] == "--config":
            cfg.main_start_rewrite(setting)
            start = choose_map_debug(map_info_instance)
        elif sys.argv[1] == "--dev":
            cfg.main_start()
            start = (
                choose_map_debug(map_info_instance) if not map_arg else (map_arg, False)
            )
            dev = True  # 设置开发者模式
        elif sys.argv[1] == "--white":
            cfg.main_start()
            start = choose_map(map_info_instance)
            cfg.modify_json_file(
                cfg.CONFIG_FILE_NAME, "allowlist_mode_once", True
            )  # 启用一次白名单模式
        elif sys.argv[1] == "--record":
            from utils.ui.record import record_main

            record_main()
            return
        elif sys.argv[1] == "--test":
            # 测试模式：单独测试某个功能
            cfg.main_start()
            Window().switch_window()
            # from utils.flows.handle import Handle
            # handle = Handle()
            # handle.auto_use_technique_consumable()
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
        # 保存原始地图版本（单图运行可能临时切换版本）
        old_map_version = None
        if map_version_arg:
            old_map_version = cfg.load_config().get("map_version", "default")
            cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "map_version", map_version_arg)
            map_info_instance._map_version = map_version_arg
            cfg._config = None  # 让 config_file property 重新加载新值
            log.info(f"[单图运行] 临时切换地图版本: {map_version_arg}")

        try:
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
            notify.send_start(start)
            map_instance.process_map(
                start, start_in_mid, dev=dev, single_map=single_map_mode
            )  # 读取配置
            start_map = "1-1_0"
            allow_run_again = not single_map_mode and cfg.read_json_file(
                cfg.CONFIG_FILE_NAME, False
            ).get("allow_run_again", False)
            if allow_run_again:
                map_instance.process_map(start_map, start_in_mid, dev=dev)
            end_time = datetime.datetime.now()

            # 结束通知（含统计摘要）
            try:
                summary = {
                    "总计用时": map_instance.map_statu.total_time
                    if hasattr(map_instance, "map_statu")
                    else None,
                    "战斗次数": map_instance.handle.total_fight_cnt
                    if hasattr(map_instance, "handle")
                    else None,
                    "未战斗次数": map_instance.handle.total_no_fight_cnt
                    if hasattr(map_instance, "handle")
                    else None,
                    "疾跑节约": map_instance.handle.tatol_save_time
                    if hasattr(map_instance, "handle")
                    else None,
                    "系统卡顿": map_instance.handle.time_error_cnt
                    if hasattr(map_instance, "handle")
                    else None,
                }
                summary = {k: v for k, v in summary.items() if v is not None}
                notify.send_end(summary)
            except Exception as e:
                log.warning(f"结束通知发送失败: {e}")
            shutdown_type = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
                "auto_shutdown", 0
            )
            shutdown_computer(shutdown_type)
            if not single_map_mode and cfg.read_json_file(
                cfg.CONFIG_FILE_NAME, False
            ).get("allow_run_next_day", False):
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
                        hour=refresh_hour,
                        minute=refresh_minute,
                        second=0,
                        microsecond=0,
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
        finally:
            if old_map_version is not None:
                try:
                    cfg.modify_json_file(
                        cfg.CONFIG_FILE_NAME, "map_version", old_map_version
                    )
                    map_info_instance._map_version = old_map_version
                    cfg._config = None
                    log.info(f"[单图运行] 恢复地图版本: {old_map_version}")
                except Exception:
                    pass
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
    except BaseException:
        print(traceback.format_exc())
        log.error(traceback.format_exc())
        # 出错通知
        try:
            notify.send_error(get_error_summary(sys.exc_info()[1]))
        except Exception:
            pass
        print("请重新运行")
        try:
            input("按回车键退出")
        except EOFError:
            pass  # WebUI 等无 stdin 环境下不阻塞退出
