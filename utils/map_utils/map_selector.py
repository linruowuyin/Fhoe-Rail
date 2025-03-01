import questionary
from utils.config.config import ConfigurationManager
from utils.log import log
from utils.time_utils import TimeUtils
from utils.map_utils.map_info import MapInfo
from utils.setting import Setting

cfg = ConfigurationManager()
setting = Setting()

def choose_map(map_info: MapInfo):
    map_version = cfg.config_file.get("map_version", "default")
    MapInfo.read_maps(map_version=map_version)
    main_map = cfg.config_file.get("main_map", None)
    if main_map is None:
        main_map = min(list(map_info.map_list_map.keys()))
    side_map = list(map_info.map_list_map.get(main_map).keys())[0]
    return (f"{main_map}-{side_map}", True)


def choose_map_debug(map_info: MapInfo):
    main_map = None

    while True:
        map_version = cfg.config_file.get("map_version", "default")
        if not main_map:
            result = _h_main_map(map_info)
            if result == "back":
                continue
            if isinstance(result, tuple):
                return result
            main_map = result
        else:
            result = _h_side_map(map_info, main_map)
            if result == "back":
                main_map = None
            else:
                return result


def _h_main_map(map_info: MapInfo):
    title = "请选择起始星球："
    opts = {
        "1 空间站「黑塔」": "1",
        "2 雅利洛-VI": "2",
        "3 仙舟「罗浮」": "3",
        "4 匹诺康尼": "4",
        "5 翁法罗斯": "5",
        "优先星球": "first_map",
        "仅此次运行白名单地图": "allowlist",
        "[设置]": "option",
        "[定时]": "scheduled",
    }

    choice = questionary.select(title, list(opts.keys())).ask()
    if not choice:
        return None

    if choice == "优先星球":
        return _h_priority(map_info)
    elif choice == "仅此次运行白名单地图":
        return _h_allowlist()
    elif choice == "[设置]":
        cfg.main_start_rewrite(setting)
        log.info("设置完成")
        return "back"
    elif choice == "[定时]":
        TimeUtils.wait_and_run()
        return ("1-1_0", False)
    return opts[choice]

def _h_priority(map_info: MapInfo):
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
    side = list(map_info.map_list_map.get(main).keys())[0]
    ConfigurationManager.modify_json_file(
        ConfigurationManager.CONFIG_FILE_NAME, "main_map", main)
    return (f"{main}-{side}", True)


def _h_allowlist():
    cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "allowlist_mode_once", True)
    if cfg.config_file.get("allowlist_map"):
        return ("1-1_0", False)
    print(f"请配置allowlist_map的值，当前allowlist_map:{cfg.config_file.get('allowlist_map')}")
    return "back"


def _h_side_map(map_info: MapInfo, main):
    title = "请选择起始地图："
    opts = map_info.map_list_map.get(main)
    if not opts:
        return None

    keys = list(opts.keys())
    values = list(opts.values())

    # 二级选项
    sec_opts = list(
        dict.fromkeys(
            [v[1] for v in values if isinstance(
                v, list) and len(v) >= 2] + ["【返回】"]
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
