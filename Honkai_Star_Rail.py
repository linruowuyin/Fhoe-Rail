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
from utils.config import read_json_file, modify_json_file, init_config_file, CONFIG_FILE_NAME
from utils.map import Map
from utils.switch_window import switch_window
from utils.exceptions import Exception

CONFIG_FILE_NAME = "config.json"  # 你的配置文件名

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
            options_map = {"空间站「黑塔」": "1", "雅利洛-VI": "2", "仙舟「罗浮」": "3", "匹诺康尼": "4", "螺丝星": "5", "其他地图": "9"}
            option_ = questionary.select(title_, list(options_map.keys())).ask()
            if option_ is None:
                return None  # 用户选择了返回上一级菜单
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
                return f"{main_map}-{side_map}"


def filter_content(content, keyword):
    # 将包含指定关键词的部分替换为空字符串
    return content.replace(keyword, "")

def main():
    main_start()
    map_instance = Map()
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        start = choose_map_debug(map_instance)
    elif len(sys.argv) > 1 and sys.argv[1] == "--config":
        main_start_rewrite()  
        start = choose_map_debug(map_instance) 
    else:
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
        map_instance.auto_map(start)  # 读取配置
    else:
        log.info("前面的区域，以后再来探索吧")
        return choose_map_debug(map_instance)

def main_start():
    if not read_json_file(CONFIG_FILE_NAME, False).get('start'):
        title = "开启连续自动战斗了吗喵？："
        options = ['打开了', '没打开', '我啷个晓得嘛']
        option = questionary.select(title, options).ask()
        is_auto_battle_open = options.index(option) == 0  # 判断用户选择是否是打开了
        modify_json_file(CONFIG_FILE_NAME, "auto_battle_persistence", int(is_auto_battle_open))
        modify_json_file(CONFIG_FILE_NAME, "start", True)
        new_option_title = "想要跑完自动关机吗？"
        new_option_choices = ['不想', '↑↑↓↓←→←→BABA']
        new_option_choice = questionary.select(new_option_title, new_option_choices).ask()
        is_auto_shutdown_enabled = new_option_choice == '↑↑↓↓←→←→BABA'
        modify_json_file(CONFIG_FILE_NAME, "auto_shutdown", is_auto_shutdown_enabled)


def main_start_rewrite():
    title = "开启连续自动战斗了吗喵？："
    options = ['没打开', '打开了', '我啷个晓得嘛']
    option = questionary.select(title, options).ask()

    new_option_title = "想要跑完自动关机吗？"
    new_option_choices = ['不想', '↑↑↓↓←→←→BABA']
    new_option_choice = questionary.select(new_option_title, new_option_choices).ask()
    new_option_value = new_option_choice == '↑↑↓↓←→←→BABA'

    # 读取配置文件（如果存在）
    try:
        with open(CONFIG_FILE_NAME, 'r') as file:
            config = json.load(file)
    except FileNotFoundError:
        config = {}

    # 更新配置文件
    config['auto_battle_persistence'] = options.index(option)
    config['auto_shutdown'] = new_option_value

    # 写入配置文件
    with open(CONFIG_FILE_NAME, 'w') as file:
        json.dump(config, file, indent=4)

if __name__ == "__main__":
    try:
        if not pyuac.isUserAdmin():
            pyuac.runAsAdmin()
        else:
            main()
    except ModuleNotFoundError as e:
        print(traceback.format_exc())
        os.system("pip install -r requirements.txt")
        print("请重新运行")
    except NameError as e:
        print(traceback.format_exc())
        os.system("pip install -r requirements.txt")
        print("请重新运行")
    except:
        log.error(traceback.format_exc())
