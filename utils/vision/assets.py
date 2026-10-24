"""图片资源登记表 —— 代码里引用图片模板的唯一入口。

和 `core/thresholds.py` 是同一个思路：图片是「被代码消费、且会被游戏更新集体
打碎」的资源，路径散落在 60 多处调用点时无法审计 —— 哪些图还在用、哪张图属于
哪个检测器、更新后该先怀疑谁，都看不出来。

范围
    这里只登记**代码直接引用**的图。地图 JSON 里的 `picture\\xxx.png` 是地图
    作者/录制器写进数据的「地图点位」资产（633 张地图里几千处引用），不属于
    代码资源，不在这里逐条登记 —— 它们由 `core/schema.py` 与地图目录管理。

用法
    from utils.vision import assets
    target = Img.get_img(assets.path("transfer"))

    不要绕过 `path()` 在调用点手写路径；`tests/test_assets.py` 会扫描 `utils/`
    里的裸路径字面量，只允许数据契约与工具类保留（棘轮，只减不增）。

路径与后缀
    登记的是**代码原来使用的逻辑路径**（多为 `.png`）。实际文件可能是 `.webp`：
    `images.resolve_path` 会按 webp > png > jpg 找同名文件，所以登记 `.png`
    而磁盘上是 `.webp` 是正常的。新增资源时优先登记代码里本来就要写的后缀。

资源 ID 与唯一性（R25）
    地图 JSON 里的 `picture\\xxx.png` 不是物理路径，而是**资源 ID**：
    `resolve_path` 先按字面路径找，找不到就用 `scan_picture_files()` 的 stem
    索引递归查（忽略目录）。因此**文件名（去掉后缀）必须全局唯一**
    （大小写不敏感，`new_pic/` 除外）—— 目录只是分类，名字才是身份。
    重名由 `tools/validate_pictures.py` 在 CI 拦下。

分类
    `category` 是给将来物理分目录、以及「游戏更新后先跑哪一组冒烟」用的元数据。
    它不影响加载；新增分类记得同步 `CATEGORIES`。
"""

import os
from typing import NamedTuple
#: 图片资源根目录（相对仓库根）。`black_screen` 之类按目录扫描的代码用它。
PICTURE_ROOT = "./picture"

#: 指向图片资源的路径前缀（统一成 `/` 之后比较；地图 JSON 用反斜杠写法，
#: 解析前会先归一化）。用于判断"这是不是 picture/ 下的资源 ID"。
PICTURE_REF_PREFIXES = ("picture/", "./picture/")

#: 索引扫描时跳过的目录：`new_pic/` 是采样产物（按日期分目录，重名是设计使然）。
SCAN_SKIP_DIRS = {"new_pic"}

#: 索引只认这三种后缀，优先级与 `images.resolve_path` 一致。
SCAN_EXT_PRIORITY = {"webp": 0, "png": 1, "jpg": 2}

# --- 分类 ------------------------------------------------------------------
#: 主界面 / 脱离战斗 / 加载判定
CATEGORY_MAIN_UI = "main_ui"
#: 战斗流程与结算
CATEGORY_COMBAT = "combat"
#: 购买、零食、弹窗按钮
CATEGORY_PURCHASE = "purchase"
#: F 键交互图标
CATEGORY_F_ICON = "f_icon"
#: 地图 / 星轨航图界面
CATEGORY_MAP_UI = "map_ui"
#: 视角、小地图
CATEGORY_ORIENTATION = "orientation"
#: 设置菜单
CATEGORY_SETTING = "setting"
#: 月卡
CATEGORY_MONTHLY_PASS = "monthly_pass"
#: 角色头像 / 秘技状态
CATEGORY_ROLE = "role"
#: 解谜退出
CATEGORY_PUZZLE = "puzzle"

CATEGORIES = {
    CATEGORY_MAIN_UI,
    CATEGORY_COMBAT,
    CATEGORY_PURCHASE,
    CATEGORY_F_ICON,
    CATEGORY_MAP_UI,
    CATEGORY_ORIENTATION,
    CATEGORY_SETTING,
    CATEGORY_MONTHLY_PASS,
    CATEGORY_ROLE,
    CATEGORY_PUZZLE,
}


class Asset(NamedTuple):
    """一条图片资源：路径 + 分类 +（可选）备注。"""

    path: str
    category: str
    note: str = ""


#: 登记表。key 用小写蛇形，与文件 stem 对得上即可。
ASSETS = {
    # --- 主界面 / 加载 / 脱离战斗 -----------------------------------------
    "finish_fighting": Asset(
        "./picture/ui/finish_fighting.webp", CATEGORY_MAIN_UI, "主界面判定（Img.main_ui）"
    ),
    "finish_fighting2": Asset("./picture/ui/finish_fighting2.webp", CATEGORY_MAIN_UI),
    "finish_fighting2_1": Asset(
        "./picture/ui/finish_fighting2_1.webp", CATEGORY_MAIN_UI
    ),
    "finish_fighting2_2": Asset(
        "./picture/ui/finish_fighting2_2.webp", CATEGORY_MAIN_UI
    ),
    "finish_fighting3": Asset("./picture/ui/finish_fighting3.webp", CATEGORY_MAIN_UI),
    "finish_fighting4": Asset("./picture/ui/finish_fighting4.webp", CATEGORY_MAIN_UI),
    "finish_fighting5": Asset("./picture/ui/finish_fighting5.webp", CATEGORY_MAIN_UI),
    "doubt": Asset("./picture/ui/doubt.webp", CATEGORY_MAIN_UI, "疑问气泡（附近有敌人）"),
    "warn": Asset("./picture/ui/warn.webp", CATEGORY_MAIN_UI),
    "battle_esc_check": Asset(
        "./picture/ui/battle_esc_check.webp", CATEGORY_MAIN_UI, "战斗中按 ESC 的确认画面"
    ),
    "switch_run": Asset("./picture/ui/switch_run.webp", CATEGORY_MAIN_UI, "疾跑图标"),
    "map_load": Asset("./picture/map_ui/map_load.webp", CATEGORY_MAIN_UI, "地图加载中"),
    "round": Asset("./picture/ui/round.webp", CATEGORY_MAIN_UI, "必定不在战斗中"),
    # --- 战斗 --------------------------------------------------------------
    "auto": Asset("./picture/ui/auto.webp", CATEGORY_COMBAT, "自动战斗已开启"),
    "not_auto": Asset("./picture/ui/not_auto.webp", CATEGORY_COMBAT, "自动战斗未开启"),
    "continue_fighting": Asset(
        "./picture/ui/continue_fighting.webp", CATEGORY_COMBAT, "继续战斗按钮"
    ),
    "defeat": Asset("./picture/ui/defeat.webp", CATEGORY_COMBAT),
    # --- 购买 / 零食 / 弹窗 ------------------------------------------------
    "eat": Asset("./picture/ui/eat.webp", CATEGORY_PURCHASE, "秘技点不足对话框"),
    "qiqiao": Asset("./picture/ui/qiqiao.webp", CATEGORY_PURCHASE, "奇巧零食图标"),
    "qiqiao_lab": Asset("./picture/ui/qiqiao_lab.webp", CATEGORY_PURCHASE),
    "cancel": Asset("./picture/ui/cancel.webp", CATEGORY_PURCHASE),
    "round_disable": Asset("./picture/ui/round_disable.webp", CATEGORY_PURCHASE, "无法购买"),
    "max": Asset("./picture/ui/max.webp", CATEGORY_PURCHASE, "购买数量拉满"),
    # --- F 键交互 ----------------------------------------------------------
    "sw": Asset("./picture/f_icon/sw.webp", CATEGORY_F_ICON, "F 图标（通用）"),
    "f_teleport": Asset("./picture/f_icon/F_Teleport.webp", CATEGORY_F_ICON),
    "f_space_anchor": Asset("./picture/f_icon/F_SpaceAnchor.webp", CATEGORY_F_ICON),
    "f_dream_module": Asset("./picture/f_icon/F_DreamModule.webp", CATEGORY_F_ICON),
    "f_dream_pop": Asset("./picture/f_icon/F_DreamPop.webp", CATEGORY_F_ICON),
    "f_dream_scape": Asset("./picture/f_icon/F_DreamScape.webp", CATEGORY_F_ICON),
    "f_listen": Asset("./picture/f_icon/F_Listen.webp", CATEGORY_F_ICON),
    "f_goto": Asset("./picture/f_icon/F_Goto.webp", CATEGORY_F_ICON),
    # --- 地图 / 星轨航图 ---------------------------------------------------
    "transfer": Asset("./picture/map_ui/transfer.webp", CATEGORY_MAP_UI, "传送锚点"),
    "contraction": Asset("./picture/map_ui/contraction.webp", CATEGORY_MAP_UI, "地图收缩图标"),
    "map_back": Asset("./picture/map_ui/map_back.webp", CATEGORY_MAP_UI, "地图返回按钮"),
    "kaituoli_1": Asset("./picture/map_ui/kaituoli_1.webp", CATEGORY_MAP_UI, "星轨航图"),
    # --- 视角 / 小地图 -----------------------------------------------------
    "screenshot_arrow": Asset(
        "./picture/orientation/screenshot_arrow.webp", CATEGORY_ORIENTATION, "视角校准箭头"
    ),
    "orientation_2": Asset("./picture/orientation/orientation_2.webp", CATEGORY_ORIENTATION),
    "orientation_3": Asset("./picture/orientation/orientation_3.webp", CATEGORY_ORIENTATION),
    "orientation_4": Asset("./picture/orientation/orientation_4.webp", CATEGORY_ORIENTATION),
    "orientation_5": Asset("./picture/orientation/orientation_5.webp", CATEGORY_ORIENTATION),
    "orientation_6": Asset("./picture/orientation/orientation_6.webp", CATEGORY_ORIENTATION),
    "orientation_7": Asset("./picture/orientation/orientation_7.webp", CATEGORY_ORIENTATION),
    "loc_arrow": Asset("./picture/orientation/loc_arrow.webp", CATEGORY_ORIENTATION, "小地图箭头"),
    # --- 设置菜单 ----------------------------------------------------------
    "setting_icon": Asset("./picture/ui/setting_icon.webp", CATEGORY_SETTING),
    "setting_other": Asset("./picture/ui/setting_other.webp", CATEGORY_SETTING),
    "setting_yes": Asset("./picture/ui/setting_yes.webp", CATEGORY_SETTING),
    "auto_use_technique_consumable": Asset(
        "./picture/ui/auto_use_technique_consumable.webp", CATEGORY_SETTING
    ),
    # --- 月卡 --------------------------------------------------------------
    "monthly_pass_pic": Asset("./picture/ui/monthly_pass_pic.webp", CATEGORY_MONTHLY_PASS),
    "monthly_pass_pic_2": Asset(
        "./picture/ui/monthly_pass_pic_2.webp", CATEGORY_MONTHLY_PASS
    ),
    "monthly_pass_pic_3": Asset(
        "./picture/ui/monthly_pass_pic_3.webp", CATEGORY_MONTHLY_PASS
    ),
    # --- 角色 --------------------------------------------------------------
    "silver_wolf_lv999_e": Asset(
        "./picture/role/silver_wolf_lv999_e.png", CATEGORY_ROLE, "银狼 LV.999 秘技状态"
    ),
    "role_acheron": Asset(
        "./picture/role/role_acheron.png", CATEGORY_ROLE, "1 号位黄泉头像"
    ),
    "role_silver_wolf_lv999": Asset(
        "./picture/role/role_silver_wolf_lv999.png",
        CATEGORY_ROLE,
        "1 号位银狼 LV.999 头像",
    ),
    # --- 解谜 --------------------------------------------------------------
    "puzzle_exit_prompt": Asset(
        "./picture/ui/puzzle_exit_prompt.png", CATEGORY_PUZZLE, "放弃游玩？提示"
    ),
    "puzzle_exit_confirm": Asset(
        "./picture/ui/puzzle_exit_confirm.png", CATEGORY_PUZZLE, "放弃游玩确认按钮"
    ),
}


def path(key):
    """登记 key → 图片路径。

    未登记时抛 `KeyError`：拼错 key 要在第一次运行时立刻炸，而不是静默返回
    一个不存在的路径让识图去猜。
    """
    try:
        return ASSETS[key].path
    except KeyError:
        raise KeyError(
            f"未登记的图片资源：{key!r}（请先在 utils/vision/assets.py 登记）"
        ) from None


def is_picture_ref(value):
    """这个字符串是不是地图 JSON 里的图片步骤键（`picture\\xxx.png`）。"""
    return value.replace("\\", "/").startswith(PICTURE_REF_PREFIXES)


def asset_id(step):
    """地图 JSON 的图片步骤键 → 资源 ID（stem，小写）；不是图片引用时返回 ""。

    `"picture\\map_4-3_point_5.png"` → `"map_4-3_point_5"`

    业务逻辑只认这个 ID（R25）：前缀、目录、分隔符、后缀都属于序列化细节，
    统一在这里剥掉。文件改名 / 搬目录 / `.png`→`.webp` 都不影响分派。
    """
    if not is_picture_ref(step):
        return ""
    name = step.replace("\\", "/").rsplit("/", 1)[-1]
    return os.path.splitext(name)[0].lower()


def iter_picture_files(root=None):
    """递归列出图片文件路径（跳过 `new_pic/` 与隐藏目录），顺序稳定。

    所有"扫目录"的工具（WebUI 图片库、样本收集、匹配探针、黑屏判定）都从这里
    拿列表，别各自 `os.listdir` —— 目录分类以后，平铺扫描会漏掉子目录。
    """
    root = root or PICTURE_ROOT
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in SCAN_SKIP_DIRS and not name.startswith(".")
        )
        for filename in sorted(filenames):
            ext = os.path.splitext(filename)[1].lower().lstrip(".")
            if ext in SCAN_EXT_PRIORITY:
                yield os.path.join(dirpath, filename)


def scan_picture_files(root=None):
    """扫描图片目录，返回 `(索引, 重名表)`。

    :param root: 默认 `PICTURE_ROOT`；测试可传临时目录
    :return: `({"stem(小写)": 路径}, {"stem": [路径, ...]})`

    索引按 stem（文件名去掉后缀）建，扩展名优先级 webp > png > jpg。
    **同一张图同时有 .webp 和 .png 不算重名**（那是迁移过程），
    但同一个 stem 出现在两个不同目录算重名 —— 地图 JSON 的 `picture\\xxx.png`
    是资源 ID（R25），解析时忽略目录，重名会让"指向哪个"取决于遍历顺序。

    `new_pic/` 跳过：采样产物按日期分目录，重名是设计使然。
    用 `os.walk` 且不缓存：调用方（`images`）负责缓存与清理（R15）。
    """
    candidates = {}
    for path in iter_picture_files(root):
        stem, ext = os.path.splitext(os.path.basename(path))
        candidates.setdefault(stem.lower(), []).append(
            (SCAN_EXT_PRIORITY[ext.lower().lstrip(".")], path)
        )

    index = {}
    duplicates = {}
    for stem, found in candidates.items():
        found.sort()
        index[stem] = found[0][1]
        directories = {os.path.dirname(path) for _, path in found}
        if len(directories) > 1:
            duplicates[stem] = [path for _, path in found]
    return index, duplicates
