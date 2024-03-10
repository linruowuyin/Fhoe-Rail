import os
import sys
import traceback
import time
import ctypes
import questionary
import pyuac
import json
from utils.log import log, webhook_and_log, fetch_php_file_content
from get_width import get_width, check_mult_screen
from utils.config import ConfigurationManager
from utils.map import Map
from utils.switch_window import switch_window
from utils.exceptions import Exception

cfg = ConfigurationManager()

def choose_map(map_instance: Map):
    main_map = "1-1"  # 选择第一张地图
    side_map = "0"  # 选择第一张地图的第一个子地图
    return f"{main_map}_{side_map}"

def choose_map_debug(map_instance: Map):
    is_selecting_main_map = True
    main_map = None
    side_map = None

    while True:
        if is_selecting_main_map:
            title_ = "请选择起始星球："
            options_map = {"空间站「黑塔」": "1", "雅利洛-VI": "2", "仙舟「罗浮」": "3", "匹诺康尼": "4", "螺丝星": "5", "其他地图": "9", "优先地图（默认匹诺康尼）": "first_map"}
            option_ = questionary.select(title_, list(options_map.keys())).ask()
            if option_ is None:
                return None  # 用户选择了返回上一级菜单
            if option_ == "优先地图（默认匹诺康尼）":
                default = "4"
                options_map_first = {"默认": default, "空间站「黑塔」": "1", "雅利洛-VI": "2", "仙舟「罗浮」": "3", "匹诺康尼": "4"}
                option_ = questionary.select(title_, list(options_map_first.keys())).ask()
                main_map = options_map_first.get(option_)
                side_map = list(map_instance.map_list_map.get(main_map).keys())[0]
                return (f"{main_map}-{side_map}", True)
            main_map = options_map.get(option_)
            is_selecting_main_map = False
        else:
            title_ = "请选择起始地图："
            options_map = map_instance.map_list_map.get(main_map)
            if not options_map:
                return None
            keys = list(options_map.keys())
            values = list(options_map.values()) + ["【返回】"]
            option_ = questionary.select(title_, values).ask()
            if option_ == "【返回】":
                is_selecting_main_map = True  # 返回上一级菜单，重新选择起始星球
            else:
                side_map = keys[values.index(option_)]
                log.info(f"{main_map}-{side_map}")
                return f"{main_map}-{side_map}"


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
        start = choose_map_debug(map_instance)
        if isinstance(start, tuple):
            start_in_mid = start[1]
            start = start[0]
    elif len(sys.argv) > 1 and sys.argv[1] == "--config":
        main_start_rewrite()  
        start = choose_map_debug(map_instance) 
    else:
        main_start()
        start = choose_map(map_instance)
    
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
        map_instance.auto_map(start, start_in_mid)  # 读取配置
    else:
        log.info("前面的区域，以后再来探索吧")
        return choose_map_debug(map_instance)

def main_start():
    if not cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get('start'):
        #title = "开启连续自动战斗了吗喵？："
        #options = ['打开了', '没打开', '我啷个晓得嘛']
        #option = questionary.select(title, options).ask()
        #is_auto_battle_open = options.index(option) == 0  # 判断用户选择是否是打开了
        #modify_json_file(CONFIG_FILE_NAME, "auto_battle_persistence", int(is_auto_battle_open))
        cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "start", True)
        set_config()


def main_start_rewrite():
    set_config(slot='start_rewrite')

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
    default_questions = [
        {
            "title": "想要跑完自动关机吗？",
            "choices": {'不想': False, '↑↑↓↓←→←→BABA': True},
            "config_key": "auto_shutdown"
        },
        {
            "title": "map最后一次攻击自动转换为秘技攻击？默认为不转换",
            "choices": {'不转换': False, '转换': True},
            "config_key": "auto_final_fight_e"
        },
        {
            "title": "跑图时使用疾跑模式？（实验性功能，默认关闭，未测试过不同角色的影响，请自行斟酌打开）",
            "choices": {'关闭疾跑': False, '开启疾跑': True},
            "config_key": "auto_run_in_map"
        },
        {
            "title": "设置识别怪物超时时间，默认为15秒。需要自定义设置可以直接修改config.json中的detect_fight_status_time为指定的秒数",
            "choices": {'较短识别时间（5秒）': 5, '较长识别时间（15秒）': 15},
            "config_key": "detect_fight_status_time"
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
