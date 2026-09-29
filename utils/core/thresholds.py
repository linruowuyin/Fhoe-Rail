"""识图匹配阈值 —— 全项目唯一来源。

集中在这里的理由只有一个：这些数字散落在 40 多处调用点时无法审计，而游戏每次
版本更新都可能让它们集体失效，那时需要一次性重新标定。
**集中是重新标定的前提。**

这些值是实机跑出来的当前最佳值。集中在这里而不是留在各调用点，是因为游戏
每次版本更新都可能让它们集体失效 —— 那时需要一次性重新校准，集中是前提。

改之前先确认这一条是怎么定出来的**（余量小的最容易碎）**：
    * 若你知道它的正/负样本匹配度，把余量写在旁边，例如 `# 余量 0.07`
    * 若不知道，先按 CLAUDE.md §1.2 跑一次探针再改 —— 不要凭手感调
新增常量必须同步补进 `tests/test_thresholds.py` 的 GOLDEN_VALUES。

约定
    * 阈值统一是「严格大于」判定（`max_val > THRESHOLD`），不是「大于等于」。
      改判定方向必须同时改调用点。
    * 命名取自该阈值判定的 UI 元素或图片资源名，尽量与调用点的变量名一致。
    * 同一个数字出现在不同语义下时，**分设不同的常量** —— 它们将来会各自漂移。

不在本模块范围
    HSV 颜色掩膜（`vision/blackscreen.py` 的灰度阈值、`flows/handle.py::take_arrow`
    的蓝色区间、`vision/get_angle.py` 的青色区间）属于另一类识别参数，本次未搬。
"""

# ---------------------------------------------------------------------------
# 通用默认值（Img 的 API 默认参数）
# ---------------------------------------------------------------------------

#: `Img.have_screenshot` / `Img.on_interface` 的默认阈值
DEFAULT_MATCH = 0.90


# ---------------------------------------------------------------------------
# 主界面与战斗判定
# ---------------------------------------------------------------------------

#: 左上角灯泡：判断「在主界面」
MAIN_INTERFACE = 0.90

#: 主界面的严格判定：`fight_elapsed` 用它判断战斗是否结束
MAIN_INTERFACE_STRICT = 0.92

#: 疑问气泡（`doubt.png`）：附近有敌人待触发
DOUBT_ICON = 0.92

#: `round.png`：必定不在战斗中
ROUND_ICON = 0.95

#: `battle_esc_check.png`：战斗中按 ESC 后的确认画面
BATTLE_ESC_CHECK = 0.97

#: `not_auto.png` / `not_auto_c.png`：自动战斗未开启
AUTO_OFF_ICON = 0.95

#: 行动条识别（判定自动战斗卡住），用实时截图与首帧比较
ACTION_BAR = 0.97

#: `switch_run.png`：疾跑图标。判定「是否在疾跑」要求极高匹配度
SPRINT_ICON = 0.996


# ---------------------------------------------------------------------------
# F 键交互
# ---------------------------------------------------------------------------

#: 扫描 `F` 交互图标（`sw.png` 等一组图）
F_ICON = 0.95


# ---------------------------------------------------------------------------
# 地图与传送
# ---------------------------------------------------------------------------

#: `map_load.png`：地图加载中
MAP_LOADING = 0.95

#: `picture\orientation_1.png`：星轨航图的星球入口图标
ORIENTATION_ICON = 0.97

#: `contraction.png`：地图已打开
MAP_OPEN = 0.97

#: `map_back.png`：地图返回按钮
MAP_BACK = 0.99

#: `find_transfer_point` 的起始搜索阈值
TRANSFER_POINT_SEARCH = 0.99

#: `find_transfer_point` 阈值逐轮下降的下限
TRANSFER_POINT_MIN = 0.93

#: `find_scene` 的起始搜索阈值
SCENE_SEARCH = 0.99

#: `find_scene` 阈值逐轮下降的下限
SCENE_MIN = 0.93

#: `1floor.png` / `2floor.png` / `3floor.png`：楼层按钮
FLOOR_BUTTON = 0.93

#: `orientation_*.png`：星球的定位与查找
PLANET = 0.975

#: 点击星球
PLANET_CLICK = 0.93

#: 通用地图点位查找（`find_transfer_point` 的 threshold 实参）
POINT_SEARCH = 0.975

#: 点击普通传送点
TELEPORT_POINT = 0.93

#: `kaituoli_1.png`：星轨航图
STAR_MAP = 0.97

#: 右上角返回按钮
BACK_BUTTON = 0.94

#: `transfer.png`：地图内传送图标
TRANSFER_ICON = 0.93

#: `max.png`：购买入口图标
BUY_ICON = 0.93

#: `check_4-1_point*.png`：筑梦机关检查
DREAM_MACHINE = 0.992

#: `map_4-1_point_2.png` / `map_4-3_point*.png`：筑梦边境系列点位
DREAM_POINT = 0.975

#: 筑梦边境点位的点击（阈值低于查找）
DREAM_POINT_CLICK = 0.95

#: 筑梦边境场景的拖动查找
DREAM_SCENE = 0.990

#: `finish_fighting.png`：筑梦模块加载完成
DREAM_BUILD = 0.90


# ---------------------------------------------------------------------------
# 设置菜单（自动使用秘技消耗品）
# ---------------------------------------------------------------------------

#: `setting_icon.png`
SETTING_ICON = 0.98

#: `setting_other.png`
SETTING_OPTION = 0.98

#: `auto_use_technique_consumable.png` 开关
TECHNIQUE_CONSUMABLE = 0.98

#: `setting_yes.png` 确认按钮
SETTING_CONFIRM = 0.99


# ---------------------------------------------------------------------------
# 秘技点与道具
# ---------------------------------------------------------------------------

#: `eat.png`：秘技点不足对话框
TECHNIQUE_DIALOG = 0.90

#: `qiqiao.png`：奇巧零食图标
QIQIAO_ICON = 0.95

#: 零食店里的合成/确认按钮。
#: 注意：与 ROUND_ICON 是同一张 round.png，但用途与阈值都不同。
SNACK_CRAFT_BUTTON = 0.9

#: `qiqiao_lab.png`：奇巧零食合成页
QIQIAO_LAB = 0.97

#: `finish_fighting*.png`：判定「已脱离黑屏」
FINISH_FIGHTING = 0.9

#: `round_disable.png`：无法购买
ROUND_DISABLE = 0.95

#: `cancel.png`：取消按钮
CANCEL_BUTTON = 0.95


# ---------------------------------------------------------------------------
# 战斗结算
# ---------------------------------------------------------------------------

#: `continue_fighting.png`
CONTINUE_FIGHTING = 0.98

#: `defeat.png`：战败
DEFEAT = 0.98


# ---------------------------------------------------------------------------
# 月卡
# ---------------------------------------------------------------------------

#: `monthly_pass_pic*.png`：月卡入口
MONTHLY_PASS = 0.91

#: `finish_fighting.png`：判定为「无月卡」
MONTHLY_PASS_NO_PASS = 0.92


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

#: 低于此匹配度才记入 `img_search_val_dict`，供报告输出「最相似图片」
LOW_MATCH_REPORT_FLOOR = 0.99
