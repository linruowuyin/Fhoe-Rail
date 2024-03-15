import os
import sys
import traceback
import time
import ctypes
import questionary
import pyuac
import json
import datetime
import subprocess
from utils.log import log, webhook_and_log, fetch_php_file_content
from get_width import get_width, check_mult_screen
from utils.config import ConfigurationManager
from utils.map import Map
from utils.switch_window import switch_window
from utils.exceptions import Exception

cfg = ConfigurationManager()

def choose_map(map_instance: Map):
    map_version = cfg.CONFIG.get("map_version", "default")
    map_instance.read_maps(map_version=map_version)
    main_map = cfg.read_json_file(cfg.CONFIG_FILE_NAME).get("main_map", None)
    if main_map is None:
        main_map = min(list(map_instance.map_list_map.keys()))
    side_map = list(map_instance.map_list_map.get(main_map).keys())[0]
    return (f"{main_map}-{side_map}", True)

def choose_map_debug(map_instance: Map):
    is_selecting_main_map = True
    main_map = None
    side_map = None
    map_version = cfg.CONFIG.get("map_version", "default")
    map_instance.read_maps(map_version=map_version)
    while True:
        if is_selecting_main_map:
            title_ = "请选择起始星球："
            options_map = {"空间站「黑塔」": "1", "雅利洛-VI": "2", "仙舟「罗浮」": "3", "匹诺康尼": "4", "螺丝星": "5", "优先星球": "first_map", "定时锄大地": "scheduled"}
            option_ = questionary.select(title_, list(options_map.keys())).ask()
            if option_ is None:
                return None  # 用户选择了返回上一级菜单
            if option_ == "优先星球":
                options_map_first = {"空间站「黑塔」": "1", "雅利洛-VI": "2", "仙舟「罗浮」": "3", "匹诺康尼": "4"}
                option_ = questionary.select(title_, list(options_map_first.keys())).ask()
                main_map = options_map_first.get(option_)
                side_map = list(map_instance.map_list_map.get(main_map).keys())[0]
                cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "main_map", main_map)
                return (f"{main_map}-{side_map}", True)
            elif option_ == "定时锄大地":
                map_instance.wait_and_run()
                return f"1-1_0"
            main_map = options_map.get(option_)
            is_selecting_main_map = False
        else:
            title_ = "请选择起始地图："
            options_map = map_instance.map_list_map.get(main_map)
            if not options_map:
                return None
            keys = list(options_map.keys())
            second_values = list(dict.fromkeys([value[1] for value in options_map.values() if isinstance(value, list) and len(value) >= 2] + ["【返回】"]))
            second_option_ = questionary.select(title_, second_values).ask()
            if second_option_ == "【返回】":
                is_selecting_main_map = True  # 返回上一级菜单，重新选择起始星球
                continue
            values = [value[0] for value in options_map.values() if isinstance(value, list) and len(value) >= 2 and value[1] == second_option_] + ["【返回】"]
            # values = list(options_map.values()) + ["【返回】"]
            option_ = questionary.select(title_, values).ask()
            if option_ == "【返回】":
                is_selecting_main_map = True  # 返回上一级菜单，重新选择起始星球
            else:
                side_map = keys[values.index(option_)]
                log.info(f"{main_map}-{side_map}")
                return (f"{main_map}-{side_map}", True)


def filter_content(content, keyword):
    # 将包含指定关键词的部分替换为空字符串
    return content.replace(keyword, "")

def print_version():
    try:
        with open("version.txt", "r", encoding="utf-8") as file:
            version = file.read().strip()
            log.info(f"当前版本：{version}")
        log.info(f'{cfg.CONFIG_FILE_NAME}')
        cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "version", version)
        from utils.calculated import Calculated
        Calculated.CONFIG.get("version", "")
    except:
        pass

def main():
    map_instance = Map()
    start_in_mid = False  # 是否为优先地图，优先地图完成后自动从1-1_0开始
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        main_start()
        start = choose_map_debug(map_instance)
        if isinstance(start, tuple):
            start_in_mid = start[1]
            start = start[0]
    elif len(sys.argv) > 1 and sys.argv[1] == "--config":
        main_start_rewrite()  
        start = choose_map_debug(map_instance)
        if isinstance(start, tuple):
            start_in_mid = start[1]
            start = start[0]
    else:
        main_start()
        start = choose_map(map_instance)
        if isinstance(start, tuple):
            start_in_mid = start[1]
            start = start[0]
    
    if start:
        php_content = fetch_php_file_content()  # 获取PHP文件的内容
        filtered_content = filter_content(php_content, "舔狗日记")  # 过滤关键词
        log.info("\n" + filtered_content)  # 将过滤后的内容输出到日志
        log.info("")  # 添加一行空行
        log.info("切换至游戏窗口，请确保跑图角色普攻为远程")
        check_mult_screen()
        switch_window()
        time.sleep(0.5)
        log.info("开始运行，请勿移动鼠标和键盘.向着星...呃串台了")
        log.info("黑塔：7128；雅利洛：19440；罗浮：42596；匹诺康尼：30996")
        log.info("2.0版本单角色锄满100160经验（fhoe当前做不到）")
        log.info("免费软件，倒卖的曱甴冚家铲，请尊重他人的劳动成果")
        start_time = datetime.datetime.now()
        map_instance.auto_map(start, start_in_mid)  # 读取配置
        allow_run_again = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get("allow_run_again", False)
        if allow_run_again:
            map_instance.auto_map(start, start_in_mid)
        end_time = datetime.datetime.now()
        shutdown_type = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get('auto_shutdown', 0)
        shutdown_computer(shutdown_type)
        log.info(f"开始执行跨天自动锄大地")
        if map_instance.has_crossed_4am(start=start_time, end=end_time):
            log.info(f"跨越了凌晨4点，立即重新开始运行")
            map_instance.auto_map(start, start_in_mid)
        else:
            now = datetime.datetime.now()
            next_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)
            if now.hour >= 4:
                next_4am += datetime.timedelta(days=1)
            wait_time = (next_4am - now).total_seconds()
            log.info(f"等待 {wait_time:.0f} 秒到下一个凌晨4点，将继续重新开始运行")
            time.sleep(wait_time)
            map_instance.auto_map(start, start_in_mid)
        # shutdown_type = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get('auto_shutdown', 0)
        # shutdown_computer(shutdown_type)
    else:
        log.info("前面的区域，以后再来探索吧")
        main()

def main_start():
    if cfg.config_issubset():
        if not cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get('start'):
            cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "start", True)
            set_config()
    else:
        log.info(f"检测到需要进行必要的配置，请配置")
        cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "start", True)
        set_config()
        cfg.ensure_config_complete()

def main_start_rewrite():
    set_config(slot='start_rewrite')
    cfg.ensure_config_complete()

def set_config(slot: str = 'start'):
    questions = get_questions_for_slot(slot)
    if not questions:
        log.info(f"错误的set_config参数: {slot}")
        return

    config = load_config()

    for question in questions:
        option = ask_question(question)
        config[question["config_key"]] = question["choices"][option]

    save_config(config)

def get_questions_for_slot(slot: str) -> list:
    map_instance = Map()
    map_versions = map_instance.read_maps_versions()
    default_questions = [
        {
            "title": "选择地图版本，default：正常走路/疾跑，technique：过程中会大量使用秘技",
            "choices": {version: version for version in map_versions},
            "config_key": "map_version"
        },
        {
            "title": "想要跑完自动关机吗？",
            "choices": {'不想': 0, '关机↑↑↓↓←→←→BABA': 1, '注销': 2},
            "config_key": "auto_shutdown"
        },
        {
            "title": "map最后一次攻击自动转换为秘技攻击？默认为不转换",
            "choices": {'不转换': False, '转换': True},
            "config_key": "auto_final_fight_e"
        },
        {
            "title": "设置识别怪物超时时间，默认为15秒。需要自定义设置可以直接修改config.json中的detect_fight_status_time为指定的秒数",
            "choices": {'较短识别时间（5秒）': 5, '较长识别时间（15秒）': 15},
            "config_key": "detect_fight_status_time"
        },
        {
            "title": "优先星球",
            "choices": {"空间站「黑塔」": "1", "雅利洛-VI": "2", "仙舟「罗浮」": "3", "匹诺康尼": "4"},
            "config_key": "main_map"
        },
        {
            "title": "连续锄两次，避免漏怪，需要约7小时",
            "choices": {"只锄一次": False, "连锄两次": True},
            "config_key": "allow_run_again"
        },
        {
            "title": "是否结束后等待游戏换日后继续锄地",
            "choices": {"否": False, "是": True},
            "config_key": "allow_run_next_day"
        }
    ]

    slot_questions = {
        'start': default_questions,
        'start_rewrite': default_questions
    }

    return slot_questions.get(slot, [])

def load_config() -> dict:
    try:
        with open(cfg.CONFIG_FILE_NAME, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_config(config: dict):
    with open(cfg.CONFIG_FILE_NAME, 'w') as file:
        json.dump(config, file, indent=4)

def ask_question(question: dict):
    return questionary.select(question["title"], list(question["choices"].keys())).ask()

def shutdown_computer(shutdown_type):
    if shutdown_type == 0:
        pass
    elif shutdown_type == 1:
        log.info("下班喽！I'm free!")
        os.system("shutdown /s /f /t 10")
    elif shutdown_type == 2:
        log.info("十秒后注销")
        time.sleep(10)
        os.system("shutdown /l /f")
    elif shutdown_type == 3:
        log.info("关闭指定进程")
        taskkill_name = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get('taskkill_name', None)
        if taskkill_name:
            subprocess.call(["taskkill", "/im", taskkill_name, "/f"])
    else:
        log.info("shutdown_type参数不正确")

if __name__ == "__main__":
    try:
        if not pyuac.isUserAdmin():
            pyuac.runAsAdmin()
        else:
            print_version()
            main()
    except ModuleNotFoundError as e:
        print(traceback.format_exc())
        print("请重新运行")
    except NameError as e:
        print(traceback.format_exc())
        print("请重新运行")
    except:
        log.error(traceback.format_exc())
