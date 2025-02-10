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
import re
from utils.log import log, webhook_and_log, fetch_php_file_content
from get_width import get_width, check_mult_screen
from utils.config import ConfigurationManager
from utils.map import Map
from utils.time_utils import TimeUtils
from utils.switch_window import switch_window
from utils.exceptions import Exception

cfg = ConfigurationManager()
time_mgr = TimeUtils()


def choose_map(map_instance: Map):
    map_version = cfg.CONFIG.get("map_version", "default")
    map_instance.read_maps(map_version=map_version)
    main_map = cfg.read_json_file(cfg.CONFIG_FILE_NAME).get("main_map", None)
    if main_map is None:
        main_map = min(list(map_instance.map_list_map.keys()))
    side_map = list(map_instance.map_list_map.get(main_map).keys())[0]
    return (f"{main_map}-{side_map}", True)


def choose_map_debug(map_instance: Map):
    map_version = cfg.CONFIG.get("map_version", "default")
    map_instance.read_maps(map_version=map_version)
    main_map = None

    while True:
        if not main_map:
            result = _h_main_map(map_instance)
            if result == "back":
                continue
            if isinstance(result, tuple):
                return result
            main_map = result
        else:
            result = _h_side_map(map_instance, main_map)
            if result == "back":
                main_map = None
            else:
                return result


def _h_main_map(map_instance: Map):
    title = "请选择起始星球："
    opts = {
        "1 空间站「黑塔」": "1",
        "2 雅利洛-VI": "2",
        "3 仙舟「罗浮」": "3",
        "4 匹诺康尼": "4",
        "5 翁法罗斯": "5",
        "优先星球": "first_map",
        "[设置]": "option",
        "[定时]": "scheduled",
    }

    choice = questionary.select(title, list(opts.keys())).ask()
    if not choice:
        return None

    if choice == "优先星球":
        return _h_priority(map_instance)
    elif choice == "[设置]":
        main_start_rewrite()
        log.info("设置完成")
        return "back"
    elif choice == "[定时]":
        time_mgr.wait_and_run()
        return ("1-1_0", False)
    return opts[choice]


def _h_priority(map_instance: Map):
    title = "优先星球选择"
    opts = {
        "1 空间站「黑塔」": "1",
        "2 雅利洛-VI": "2",
        "3 仙舟「罗浮」": "3",
        "4 匹诺康尼": "4",
        "5 翁法罗斯": "5",
        "【返回】": "back",
    }
    choice = questionary.select(title, list(opts.keys())).ask()

    if choice == "【返回】" or not choice:
        return "back"

    main = opts[choice]
    side = list(map_instance.map_list_map.get(main).keys())[0]
    cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "main_map", main)
    return (f"{main}-{side}", True)


def _h_side_map(map_instance: Map, main):
    title = "请选择起始地图："
    opts = map_instance.map_list_map.get(main)
    if not opts:
        return None

    keys = list(opts.keys())
    values = list(opts.values())

    # 二级选项
    sec_opts = list(
        dict.fromkeys(
            [v[1] for v in values if isinstance(v, list) and len(v) >= 2] + ["【返回】"]
        )
    )
    sec_choice = questionary.select(title, sec_opts).ask()

    if sec_choice == "【返回】":
        return "back"

    # 三级选项
    tri_opts = [
        v[0]
        for v in values
        if isinstance(v, list) and len(v) >= 2 and v[1] == sec_choice
    ] + ["【返回】"]
    tri_choice = questionary.select(title, tri_opts).ask()

    if tri_choice == "【返回】":
        return "back"

    idx = next(i for i, v in enumerate(values) if v[0] == tri_choice)
    side = keys[idx]
    log.info(f"{main}-{side}")
    return (f"{main}-{side}", False)


def filter_content(content, keyword):
    # 将包含指定关键词的部分替换为空字符串
    return content.replace(keyword, "")


def print_version():
    try:
        with open("version.txt", "r", encoding="utf-8") as file:
            version = file.read().strip()
            log.info(f"当前版本：{version}")
        log.info(f"{cfg.CONFIG_FILE_NAME}")
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
    log.info(f"=" * 60)
    log.info(f"开始运行")
    print_version()


def print_end():
    log.info(f"结束运行")
    log.info(f"=" * 60)


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
        log.info("切换至游戏窗口，请确保1号位角色普攻为远程，黄泉地图1号位为黄泉")
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
        allow_run_again = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
            "allow_run_again", False
        )
        if allow_run_again:
            map_instance.auto_map(start_map, start_in_mid, dev=dev)
        end_time = datetime.datetime.now()
        shutdown_type = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
            "auto_shutdown", 0
        )
        shutdown_computer(shutdown_type)
        if cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
            "allow_run_next_day", False
        ):
            log.info(f"开始执行跨日连锄")
            if time_mgr.has_crossed_4am(start=start_time, end=end_time):
                log.info(f"检测到换日，即将从头开锄")
                map_instance.auto_map(start_map, start_in_mid, dev=dev)
            else:
                map_instance.calculated.back_to_main(delay=2.0)
                now = datetime.datetime.now()
                refresh_hour = cfg.CONFIG.get("refresh_hour", 4)
                refresh_minute = cfg.CONFIG.get("refresh_minute", 0)
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
    """写入未找到的默认配置"""
    cfg.ensure_config_complete()


def main_start_rewrite():
    """写入需要询问的配置"""
    set_config(slot="start_rewrite")
    cfg.ensure_config_complete()


def config_fix():
    """运行前检查并修复配置"""
    config = load_config()
    if config["map_version"] == "HuangQuan":
        config["allow_fight_e_buy_prop"] = True
    save_config(config)


def set_config(slot: str = "start"):
    while True:
        questions = get_questions_for_slot(slot)
        if not questions:
            log.info(f"错误的set_config参数: {slot}")
            return

        config = load_config()
        map_instance = Map()

        choices = []
        for question in questions:
            # 处理动态标题
            title = question.get('dynamic_title', lambda _: question['title'])(config)
            
            # 处理动态选项
            choices_dict = question['choices'](config, map_instance) if callable(question['choices']) else question['choices']
            
            # 获取当前值
            current_value = config.get(question['config_key'])
            
            # 特殊处理
            if question['config_key'] == 'forbid_map':
                display_value = ', '.join(current_value) if current_value else '无'
            else:
                # 正常配置
                inverted_choices = {v: k for k, v in choices_dict.items()}
                display_value = inverted_choices.get(current_value, "未设置" if current_value is None else "未知值")

            choices.append(f"{title}------({display_value})")

        choices.append("【返回】")

        answer = questionary.select(
            "请选择要修改的设置:",
            choices=choices
        ).ask()

        if answer == "【返回】":
            return

        selected_title = answer.split("------")[0]
        selected_question = next(q for q in questions if 
            q.get('dynamic_title', lambda _: q['title'])(config) == selected_title)

        if selected_question.get('config_key') == 'forbid_map':
            handle_special_config(selected_question, config, map_instance)
            config = load_config()
        else:
            handle_normal_config(selected_question, config)
            log.info(f"4{config}")
        save_config(config)

def handle_normal_config(question, config):
    choices_dict = question['choices'](config, Map()) if callable(question['choices']) else question['choices']
    
    answer = questionary.select(
        question['title'],
        choices=list(choices_dict.keys())
    ).ask()
    
    if answer:
        config[question['config_key']] = choices_dict[answer]

def handle_special_config(question, config, map_instance):
    while True:
        current_choices = question['choices'](config, map_instance)
        answer = questionary.select(
            question['dynamic_title'](config),
            choices=list(current_choices.keys())
        ).ask()

        if answer in ["【返回】", "back"]:
            break
            
        action = current_choices[answer]

        if action == "add":
            add_forbidden_map_flow(map_instance)
            config = load_config()
        elif action == "remove":
            handler = question['handler']['remove']
            target_choices = handler['choices'](config, map_instance)
            selected = questionary.select(
                handler['title'],
                choices=list(target_choices.keys())+["【返回】"]
            ).ask()
            
            if selected and selected != "【返回】":
                config["forbid_map"].remove(selected)
                cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "forbid_map", config["forbid_map"])
        

def get_pure_map_name(raw_name: str) -> str:
    """提取地图名"""
    cleaned = re.sub(r'^[\d-]+\s*', '', raw_name)
    match = re.match(r'^([^\s\-—–]+.*?)(?=\s*[-—–]|$)', cleaned)
    return match.group(1).strip() if match else cleaned.strip()

def get_questions_for_slot(slot: str) -> list:
    map_instance = Map()
    map_versions = map_instance.read_maps_versions()
    try:
        map_instance.read_maps_versions()
    except Exception as e:
        log.error(f"地图数据加载失败: {e}")
    default_questions = [
        {
            "title": "选择地图版本，default：疾跑，HuangQuan：黄泉专用",
            "choices": {version: version for version in map_versions},
            "config_key": "map_version",
        },
        {
            "title": "锄后系统设置",
            "choices": {"无操作": 0, "关机": 1, "注销": 2},
            "config_key": "auto_shutdown",
        },
        {
            "title": "地图最后一击自动秘技（不建议龙丹、驭空开启",
            "choices": {"关闭": False, "开启": True},
            "config_key": "auto_final_fight_e",
        },
        {
            "title": "优先星球",
            "choices": {
                "空间站": "1",
                "雅利洛": "2",
                "仙舟": "3",
                "匹诺康尼": "4",
                "翁法罗斯": "5",
            },
            "config_key": "main_map",
        },
        {
            "title": "购买代币与过期邮包",
            "choices": {"不购买": False, "购买": True},
            "config_key": "allow_map_buy",
        },
        {
            "title": "购买秘技零食并合成零食",
            "choices": {"不购买": False, "购买": True},
            "config_key": "allow_snack_buy",
        },
        {
            "title": "几点月卡刷新，默认4",
            "choices": {str(refresh_hour): refresh_hour for refresh_hour in range(24)},
            "config_key": "refresh_hour",
        },
        {
            "title": "几分月卡刷新，默认0",
            "choices": {
                str(refresh_minute): refresh_minute
                for refresh_minute in [0, 15, 30, 45]
            },
            "config_key": "refresh_minute",
        },
        {
            "title": "跳过对应地图（当前已跳过：{}）",
            "choices": lambda config, map_instance: {
                **{map: map for map in config.get("forbid_map", [])},
                "【新增】": "add",
                "【删除】": "remove",
                "【返回】": "back"
            },
            "dynamic_title": lambda config: f"跳过对应地图（当前已跳过：{len(config.get('forbid_map', []))}个）",
            "config_key": "forbid_map",
            "handler": {
                "add": {
                    "title": "新增跳过地图",
                    "choices": add_forbidden_map_flow
                },
                "remove": {
                    "title": "移除已跳过的地图",
                    "choices": lambda config, _: {
                        map: map for map in config.get("forbid_map", [])
                    }
                },
                "back":{
                    "choices": set_config
                }
            }
        },
        {
            "title": "[仅该次运行有效]运行前重新校准视角",
            "choices": {"否": True, "是": False},
            "config_key": "angle_set",
        },
    ]

    slot_questions = {"start": default_questions, "start_rewrite": default_questions}

    return slot_questions.get(slot, [])

def add_forbidden_map_flow(map_instance: Map):
    """添加跳过地图的两级菜单流程"""
    # 第一级：选择星球
    planet_choice = _h_select_planet()
    log.info(f"planet_choice{planet_choice}")
    if planet_choice in (None, "back"):
        return
    # 第二级：选择地图名称
    map_choice = _h_select_clean_map(map_instance, planet_choice)
    if map_choice in (None, "back"):
        return
    log.info(f"map_choice{map_choice}")
    # 执行添加操作
    _add_to_forbidden(map_instance, planet_choice, map_choice)

def _h_select_planet():
    """星球选择菜单 (第一级)"""
    title = "选择要跳过的星球区域："
    opts = {
        "1 空间站「黑塔」": "1",
        "2 雅利洛-VI": "2", 
        "3 仙舟「罗浮」": "3",
        "4 匹诺康尼": "4",
        "5 翁法罗斯": "5",
        "返回": "back"
    }
    choice = questionary.select(title, choices=list(opts.keys())).ask()
    log.info(f"choice{opts.get(choice)}")
    return opts.get(choice) if choice else None

def _h_select_clean_map(map_instance: Map, main: str):
    """地图选择菜单 (第二级)"""
    # 获取当前星球的所有地图项
    map_version = cfg.CONFIG.get("map_version", "default")
    map_instance.read_maps(map_version=map_version)
    raw_maps = map_instance.map_list_map.get(main, {})
    log.info(f"{map_instance.map_list_map}")
    if not raw_maps:
        log.warning(f"未找到 {main} 号星球的地图数据")
        return "back"

    # 生成选项
    unique_maps = {}
    for map_id, map_names in raw_maps.items():
        log.info(map_names[-1])
        clean_name = get_pure_map_name(map_names[-1])
        unique_maps[clean_name] = unique_maps.get(clean_name, []) + [map_id]

    choices = [
        f"{name} ({len(ids)}个子地图)" 
        for name, ids in unique_maps.items()
    ] + ["返回上级"]

    # 显示选择菜单
    selected = questionary.select(
        "请选择要跳过的区域：",
        choices=choices
    ).ask()

    # 处理返回/退出
    if not selected or "返回" in selected:
        return "back"
    
    # 提取原始地图名称
    return selected.split(' ')[0] if ' ' in selected else selected

def _add_to_forbidden(map_instance: Map, main: str, map_name: str):
    """将选择的地图添加到跳过列表"""
    target = [map_name]

    # 更新配置文件
    current_forbid = load_config().get("forbid_map", [])
    updated_forbid = list(set(current_forbid + target))

    cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "forbid_map", updated_forbid)

    log.info(f"已添加子地图 {map_name} 到跳过列表")

def load_config() -> dict:
    try:
        with open(cfg.CONFIG_FILE_NAME, "r", encoding="utf-8") as file:
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
    with open(cfg.CONFIG_FILE_NAME, "w") as file:
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
        print("请重新运行")
    except NameError as e:
        print(traceback.format_exc())
        print("请重新运行")
    except:
        log.error(traceback.format_exc())
