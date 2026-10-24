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

分类
    `category` 是给将来物理分目录、以及「游戏更新后先跑哪一组冒烟」用的元数据。
    它不影响加载；新增分类记得同步 `CATEGORIES`。
"""

from typing import NamedTuple

#: 图片资源根目录（相对仓库根）。`black_screen` 之类按目录扫描的代码用它。
PICTURE_ROOT = "./picture"

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
        "./picture/finish_fighting.png", CATEGORY_MAIN_UI, "主界面判定（Img.main_ui）"
    ),
    "finish_fighting2": Asset("./picture/finish_fighting2.png", CATEGORY_MAIN_UI),
    "finish_fighting2_1": Asset(
        "./picture/finish_fighting2_1.png", CATEGORY_MAIN_UI
    ),
    "finish_fighting2_2": Asset(
        "./picture/finish_fighting2_2.png", CATEGORY_MAIN_UI
    ),
    "finish_fighting3": Asset("./picture/finish_fighting3.png", CATEGORY_MAIN_UI),
    "finish_fighting4": Asset("./picture/finish_fighting4.png", CATEGORY_MAIN_UI),
    "finish_fighting5": Asset("./picture/finish_fighting5.png", CATEGORY_MAIN_UI),
    "doubt": Asset("./picture/doubt.png", CATEGORY_MAIN_UI, "疑问气泡（附近有敌人）"),
    "warn": Asset("./picture/warn.png", CATEGORY_MAIN_UI),
    "battle_esc_check": Asset(
        "./picture/battle_esc_check.png", CATEGORY_MAIN_UI, "战斗中按 ESC 的确认画面"
    ),
    "switch_run": Asset("./picture/switch_run.png", CATEGORY_MAIN_UI, "疾跑图标"),
    "map_load": Asset("./picture/map_load.png", CATEGORY_MAIN_UI, "地图加载中"),
    "round": Asset("./picture/round.png", CATEGORY_MAIN_UI, "必定不在战斗中"),
    # --- 战斗 --------------------------------------------------------------
    "auto": Asset("./picture/auto.png", CATEGORY_COMBAT, "自动战斗已开启"),
    "not_auto": Asset("./picture/not_auto.png", CATEGORY_COMBAT, "自动战斗未开启"),
    "continue_fighting": Asset(
        "./picture/continue_fighting.png", CATEGORY_COMBAT, "继续战斗按钮"
    ),
    "defeat": Asset("./picture/defeat.png", CATEGORY_COMBAT),
    # --- 购买 / 零食 / 弹窗 ------------------------------------------------
    "eat": Asset("./picture/eat.png", CATEGORY_PURCHASE, "秘技点不足对话框"),
    "qiqiao": Asset("./picture/qiqiao.png", CATEGORY_PURCHASE, "奇巧零食图标"),
    "qiqiao_lab": Asset("./picture/qiqiao_lab.png", CATEGORY_PURCHASE),
    "cancel": Asset("./picture/cancel.png", CATEGORY_PURCHASE),
    "round_disable": Asset("./picture/round_disable.png", CATEGORY_PURCHASE, "无法购买"),
    "max": Asset("./picture/max.png", CATEGORY_PURCHASE, "购买数量拉满"),
    # --- F 键交互 ----------------------------------------------------------
    "sw": Asset("./picture/sw.png", CATEGORY_F_ICON, "F 图标（通用）"),
    "f_teleport": Asset("./picture/F_Teleport.png", CATEGORY_F_ICON),
    "f_space_anchor": Asset("./picture/F_SpaceAnchor.png", CATEGORY_F_ICON),
    "f_dream_module": Asset("./picture/F_DreamModule.png", CATEGORY_F_ICON),
    "f_dream_pop": Asset("./picture/F_DreamPop.png", CATEGORY_F_ICON),
    "f_dream_scape": Asset("./picture/F_DreamScape.png", CATEGORY_F_ICON),
    "f_listen": Asset("./picture/F_Listen.png", CATEGORY_F_ICON),
    "f_goto": Asset("./picture/F_Goto.png", CATEGORY_F_ICON),
    # --- 地图 / 星轨航图 ---------------------------------------------------
    "transfer": Asset("./picture/transfer.png", CATEGORY_MAP_UI, "传送锚点"),
    "contraction": Asset("./picture/contraction.png", CATEGORY_MAP_UI, "地图收缩图标"),
    "map_back": Asset("./picture/map_back.png", CATEGORY_MAP_UI, "地图返回按钮"),
    "kaituoli_1": Asset("./picture/kaituoli_1.png", CATEGORY_MAP_UI, "星轨航图"),
    # --- 视角 / 小地图 -----------------------------------------------------
    "screenshot_arrow": Asset(
        "./picture/screenshot_arrow.png", CATEGORY_ORIENTATION, "视角校准箭头"
    ),
    "orientation_2": Asset("./picture/orientation_2.png", CATEGORY_ORIENTATION),
    "orientation_3": Asset("./picture/orientation_3.png", CATEGORY_ORIENTATION),
    "orientation_4": Asset("./picture/orientation_4.png", CATEGORY_ORIENTATION),
    "orientation_5": Asset("./picture/orientation_5.png", CATEGORY_ORIENTATION),
    "orientation_6": Asset("./picture/orientation_6.png", CATEGORY_ORIENTATION),
    "orientation_7": Asset("./picture/orientation_7.png", CATEGORY_ORIENTATION),
    "loc_arrow": Asset("./picture/loc_arrow.jpg", CATEGORY_ORIENTATION, "小地图箭头"),
    # --- 设置菜单 ----------------------------------------------------------
    "setting_icon": Asset("./picture/setting_icon.png", CATEGORY_SETTING),
    "setting_other": Asset("./picture/setting_other.png", CATEGORY_SETTING),
    "setting_yes": Asset("./picture/setting_yes.png", CATEGORY_SETTING),
    "auto_use_technique_consumable": Asset(
        "./picture/auto_use_technique_consumable.png", CATEGORY_SETTING
    ),
    # --- 月卡 --------------------------------------------------------------
    "monthly_pass_pic": Asset("./picture/monthly_pass_pic.png", CATEGORY_MONTHLY_PASS),
    "monthly_pass_pic_2": Asset(
        "./picture/monthly_pass_pic_2.png", CATEGORY_MONTHLY_PASS
    ),
    "monthly_pass_pic_3": Asset(
        "./picture/monthly_pass_pic_3.png", CATEGORY_MONTHLY_PASS
    ),
    # --- 角色 --------------------------------------------------------------
    "silver_wolf_lv999_e": Asset(
        "./picture/silver_wolf_lv999_e.png", CATEGORY_ROLE, "银狼 LV.999 秘技状态"
    ),
    "role_acheron": Asset(
        "./picture/roles_pic/role_acheron.png", CATEGORY_ROLE, "1 号位黄泉头像"
    ),
    "role_silver_wolf_lv999": Asset(
        "./picture/roles_pic/role_silver_wolf_lv999.png",
        CATEGORY_ROLE,
        "1 号位银狼 LV.999 头像",
    ),
    # --- 解谜 --------------------------------------------------------------
    "puzzle_exit_prompt": Asset(
        "./picture/puzzle_exit_prompt.png", CATEGORY_PUZZLE, "放弃游玩？提示"
    ),
    "puzzle_exit_confirm": Asset(
        "./picture/puzzle_exit_confirm.png", CATEGORY_PUZZLE, "放弃游玩确认按钮"
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
