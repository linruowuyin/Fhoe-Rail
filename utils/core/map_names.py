"""地图的展示名（版本 / 星球 / 区域）—— 纯逻辑，不碰文件系统（CLAUDE.md R23）。

以前这几张表散在四处、互不同步：`webui/server.py` 的 `PLANET_NAMES` / `VERSION_NAMES`、
`ui/map_selector.py` 的 `PLANET_LABELS`（逐字重复一份）、`ui/setting.py` 提示语里手写的
一段（提到目录里**已经不存在**的 `SilverWolfLv999`）、README 的表格，外加前端
`index.html` 里的 `PLANET_EMOJI`。漏项就是这么来的：目录里有 `default_lite`，
`VERSION_NAMES` 里没有 —— 图鉴标签与指挥台一直显示成裸的 "default_lite"。

现在只在这里维护一份。`tools/validate_maps.py` 会在 CI 里检查「磁盘上有的版本/星球
是否都登记了中文名」，新增一个版本目录却忘了登记会被拦下。

**区域**（"主控舱段"）不用登记：实测 633 张地图的 `name` 100% 是「区域-序号」，
直接从中取；个别写歪的（如「绥  园」多打了个空格）在 `AREA_NAMES` 里覆盖显示名。
"""

import re

#: 星球编号 -> 中文名。编号来自文件名 `map_<主>-<次>_<序号>.json` 的主号。
PLANET_NAMES = {
    "1": "黑塔",
    "2": "雅利洛",
    "3": "罗浮",
    "4": "匹诺康尼",
    "5": "翁法罗斯",
    "6": "二相乐园",
}

#: 星球编号 -> 展示用 emoji（原来单独放在前端 index.html 里）
PLANET_EMOJI = {
    "1": "🛰️",
    "2": "❄️",
    "3": "🚢",
    "4": "🌙",
    "5": "🏛️",
    "6": "🎡",
}

#: 地图版本 -> 中文名。版本就是 `map/<版本>/` 的目录名。
#: 新增版本目录时**必须**在这里登记，否则图鉴/配置页会显示裸目录名（校验器会拦）。
VERSION_NAMES = {
    "default": "默认",
    "HuangQuan": "黄泉专用",
    "technique": "秘技版",
    "default_lite": "精简版",
    "reward": "特殊物品领取",
}

#: 区域显示名覆盖。键是**规范化后**的区域名（连续空白折成一个空格），
#: 例如地图名写成「绥  园-1」，规范化成「绥 园」，这里把它显示成「绥园」。
AREA_NAMES = {
    "绥 园": "绥园",
}

#: 「区域-序号」里的序号后缀
_SEQ_SUFFIX = re.compile(r"^(.*)-\d+$")


def area_key(map_name):
    """从地图名取区域键："主控舱段-1" -> "主控舱段"。

    不符合「xx-序号」的名字原样返回（并会被校验器提醒）。连续空白折成一个空格，
    免得「绥 园」和「绥  园」被当成两个区域。
    """
    text = (map_name or "").strip()
    match = _SEQ_SUFFIX.match(text)
    return " ".join((match.group(1) if match else text).split())


def area_label(map_name):
    """区域展示名：默认用规范化后的区域名，`AREA_NAMES` 里有就覆盖。"""
    key = area_key(map_name)
    return AREA_NAMES.get(key, key)


def planet_label(main, fallback=""):
    """星球展示名；没登记就退回 `fallback`，再退回编号本身。"""
    return PLANET_NAMES.get(str(main), fallback or str(main))


def planet_emoji(main):
    return PLANET_EMOJI.get(str(main), "🌍")


def version_label(version, fallback=""):
    """版本展示名；没登记就退回 `fallback`，再退回目录名本身。"""
    return VERSION_NAMES.get(version, fallback or version)
