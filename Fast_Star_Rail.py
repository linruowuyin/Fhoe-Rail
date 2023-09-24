import traceback
import time
import ctypes
import pyuac
from utils.log import log, webhook_and_log, fetch_php_file_content
from get_width import get_width, check_mult_screen
from utils.config import read_json_file, modify_json_file, init_config_file, CONFIG_FILE_NAME
from utils.map import Map
from utils.switch_window import switch_window
from utils.exceptions import Exception


def choose_map(map_instance: Map):
    title_ = "请选择起始星球："
    options_map = {"空间站「黑塔」": "1", "雅利洛-VI": "2", "仙舟「罗浮」": "3"}
    option_ = list(options_map.keys())[0]
    main_map = options_map.get(option_)
    title_ = "请选择起始地图："
    options_map = map_instance.map_list_map.get(main_map)
    if not options_map:
        return
    keys = list(options_map.keys())
    values = list(options_map.values())
    option_ = list(options_map.values())[0]
    side_map = keys[values.index(option_)]
    return f"{main_map}-{side_map}"


def filter_content(content, keyword):
    # 将包含指定关键词的部分替换为空字符串
    return content.replace(keyword, "")

def main():
    main_start()
    map_instance = Map()
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
        log.info("1.2版本，均衡6锄满单角色收益62900经验")
        log.info("免费软件，倒卖的曱甴冚家铲，请尊重他人的劳动成果")
        map_instance.auto_map(start)  # 读取配置
    else:
        log.info("错误编号，请尝试检查更新")
        webhook_and_log("运行完成")



def main_start():
    if not read_json_file(CONFIG_FILE_NAME, False).get('start'):
        title = "你游戏里开启了连续自动战斗吗？："
        options = ['没打开', '打开了', '李在说神魔']
        option = options[1]
        modify_json_file(CONFIG_FILE_NAME, "auto_battle_persistence", options.index(option))
        modify_json_file(CONFIG_FILE_NAME, "start", True)


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
