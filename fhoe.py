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
            options_map = {"1 空间站「黑塔」": "1", "2 雅利洛-VI": "2", "3 仙舟「罗浮」": "3", "4 匹诺康尼": "4", "优先星球": "first_map", "[设置]":"option", "[定时]": "scheduled"}
            option_ = questionary.select(title_, list(options_map.keys())).ask()
            if option_ is None:
                return None  # 用户选择了返回上一级菜单
            if option_ == "优先星球":
                options_map_first = {"1 空间站「黑塔」": "1", "2 雅利洛-VI": "2", "3 仙舟「罗浮」": "3", "4 匹诺康尼": "4"}
                option_ = questionary.select(title_, list(options_map_first.keys())).ask()
                main_map = options_map_first.get(option_)
                side_map = list(map_instance.map_list_map.get(main_map).keys())[0]
                cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "main_map", main_map)
                return (f"{main_map}-{side_map}", True)
            elif option_ == "[设置]":
                main_start_rewrite()
                log.info(f"设置完成")
                return choose_map_debug(map_instance)
            elif option_ == "[定时]":
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
            index_values = list(options_map.values())
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
                index = next((i for i, sublist in enumerate(index_values) if sublist[0] == option_), 0)
                side_map = keys[index]
                log.info(f"{side_map}")
                log.info(f"{main_map}-{side_map}")
                return (f"{main_map}-{side_map}", False)


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

def print_info():
    log.info("")  # 添加一行空行
    php_content = fetch_php_file_content()  # 获取PHP文件的内容
    filtered_content = filter_content(php_content, "舔狗日记")  # 过滤关键词
    log.info("\n" + filtered_content)  # 将过滤后的内容输出到日志
    log.info("")  # 添加一行空行
    log.info(f"============================================================")
    log.info(f"开始运行")
    print_version()
    
def print_end():
    log.info(f"结束运行")
    log.info(f"============================================================")

def main():
    map_instance = Map()
    start_in_mid = False  # 是否为优先地图，优先地图完成后自动从1-1_0开始
    dev = False  # 初始开发者模式，为否

    if len(sys.argv) > 1:
        if sys.argv[1] == "--debug":
            main_start()
            start = choose_map_debug(map_instance)
        elif sys.argv[1] == "--config":
            main_start_rewrite()
            start = choose_map_debug(map_instance)
        elif sys.argv[1] == "--dev":
            main_start()
            start = choose_map_debug(map_instance)
            dev = True  # 设置开发者模式
        else:
            main_start()
            start = choose_map(map_instance)
    else:
        main_start()
        start = choose_map(map_instance)

    if isinstance(start, tuple):
        start_in_mid, start = start[1], start[0]
    
    if start:
        config_fix()
        log.info(f"config.json:{load_config()}")
        log.info("切换至游戏窗口，请确保跑图角色普攻为远程")
        check_mult_screen()
        switch_window()
        time.sleep(0.5)
        log.info("开始运行，请勿移动鼠标和键盘.向着星...呃串台了")
        log.info("黑塔：7128；雅利洛：19440；罗浮：42596；匹诺康尼：30996")
        log.info("2.0版本单角色锄满100160经验（fhoe当前做不到）")
        log.info("免费软件，倒卖的曱甴冚家铲，请尊重他人的劳动成果")
        start_time = datetime.datetime.now()
        map_instance.auto_map(start, start_in_mid, dev=dev)  # 读取配置
        start_map = f"1-1_0"
        allow_run_again = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get("allow_run_again", False)
        if allow_run_again:
            map_instance.auto_map(start_map, start_in_mid, dev=dev)
        end_time = datetime.datetime.now()
        shutdown_type = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get('auto_shutdown', 0)
        shutdown_computer(shutdown_type)
        if cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get('allow_run_next_day', False):
            log.info(f"开始执行跨日连锄")
            if map_instance.has_crossed_4am(start=start_time, end=end_time):
                log.info(f"检测到换日，即将从头开锄")
                map_instance.auto_map(start_map, start_in_mid, dev=dev)
            else:
                now = datetime.datetime.now()
                next_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)
                if now.hour >= 4:
                    next_4am += datetime.timedelta(days=1)
                wait_time = (next_4am - now).total_seconds()
                wait_time += 60
                if wait_time <= 14400:
                    log.info(f"等待 {wait_time:.0f} 秒后游戏换日重锄")
                    time.sleep(wait_time)
                    map_instance.auto_map(start_map, start_in_mid, dev=dev)
                else:
                    log.info(f"等待时间过久，结束跨日连锄，等待时间需要 < 4小时")
        # shutdown_type = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get('auto_shutdown', 0)
        # shutdown_computer(shutdown_type)
        if dev:  # 开发者模式自动重选地图
            main()
    else:
        log.info("前面的区域，以后再来探索吧")
        main()

def main_start():
    """写入未找到的默认配置
    """
    cfg.ensure_config_complete()

def main_start_rewrite():
    """写入需要询问的配置
    """
    set_config(slot='start_rewrite')
    cfg.ensure_config_complete()

def config_fix():
    """运行前检查并修复配置
    """
    config = load_config()
    if config["map_version"] == "HuangQuan":
        config["allow_fight_e_buy_prop"] = True
    save_config(config)

def set_config(slot: str = 'start'):
    while True:  # 循环直到用户选择返回
        questions = get_questions_for_slot(slot)
        if not questions:
            log.info(f"错误的set_config参数: {slot}")
            return

        config = load_config()

        # 从问题列表中生成初始设置值字典
        settings = {question["title"]: config.get(question["config_key"], "未设置") for question in questions}

        def modify_setting(setting_name, setting_key):
            question = next(q for q in questions if q["title"] == setting_name)
            option = ask_question(question)
            if option is not None:
                new_value = question["choices"][option]
                config[setting_key] = new_value
                settings[setting_name] = new_value

        # 创建一级菜单，并显示当前设置值
        answer = questionary.select(
            "请选择要修改的设置:",
            choices=[f"{question['title']}------({next(k for k, v in question['choices'].items() if v == settings[question['title']])})" for question in questions] + ["【返回】"]
        ).ask()
        
        if answer == "【返回】":
            return

        # 进入子菜单进行设置值的修改
        if answer:
            setting_name = answer.split('------')[0]
            setting_key = next(question["config_key"] for question in questions if question["title"] == setting_name)
            modify_setting(setting_name, setting_key)
        
        if config["map_version"] == "HuangQuan":
            config["allow_fight_e_buy_prop"] = True
        
        save_config(config)

def get_questions_for_slot(slot: str) -> list:
    map_instance = Map()
    map_versions = map_instance.read_maps_versions()
    default_questions = [
        {
            "title": "选择地图版本，default：疾跑，HuangQuan：黄泉专用",
            "choices": {version: version for version in map_versions},
            "config_key": "map_version"
        },
        {
            "title": "锄后系统设置",
            "choices": {'无操作': 0, '关机': 1, '注销': 2},
            "config_key": "auto_shutdown"
        },
        {
            "title": "地图最后一击自动秘技（不建议龙丹、驭空开启",
            "choices": {'关闭': False, '开启': True},
            "config_key": "auto_final_fight_e"
        },
        {
            "title": "优先星球",
            "choices": {"空间站": "1", "雅利洛": "2", "仙舟": "3", "匹诺康尼": "4"},
            "config_key": "main_map"
        },
        {
            "title": "购买代币与过期邮包",
            "choices": {"不购买": False, "购买": True},
            "config_key": "allow_map_buy"
        },
        {
            "title": "购买秘技零食并合成零食",
            "choices": {"不购买": False, "购买": True},
            "config_key": "allow_snack_buy"
        },
        {
            "title": "几点月卡刷新，默认4",
            "choices": {str(refresh_hour): refresh_hour for refresh_hour in range(24)},
            "config_key": "refresh_hour"
        },
        {
            "title": "几分月卡刷新，默认0",
            "choices": {str(refresh_minute): refresh_minute for refresh_minute in [0,15,30,45]},
            "config_key": "refresh_minute"
        },
        {
            "title": "[仅该次运行有效]运行前重新校准视角",
            "choices": {"否": True, "是": False},
            "config_key": "angle_set"
        }
    ]

    slot_questions = {
        'start': default_questions,
        'start_rewrite': default_questions
    }

    return slot_questions.get(slot, [])

def load_config() -> dict:
    try:
        with open(cfg.CONFIG_FILE_NAME, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print("配置文件格式有误，请检查 JSON 格式是否正确。")
        return {}
    except Exception as e:
        print(f"读取配置文件时出现未知错误: {e}")
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
        log.info("10秒后注销")
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
            print_info()
            main()
            print_end()
    except ModuleNotFoundError as e:
        print(traceback.format_exc())
        print("请重新运行")
    except NameError as e:
        print(traceback.format_exc())
        print("请重新运行")
    except:
        log.error(traceback.format_exc())
