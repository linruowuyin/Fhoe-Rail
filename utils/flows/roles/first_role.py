"""1 号位角色识别：跑图前确认队伍 1 号位是不是这张地图要求的角色。

头像模板在 `picture/roles_pic/` 下，识别框固定在 1920×1080 基准的 (1790, 310)、
20×30 —— 两张模板按同一位置裁切，搜索区四周各外扩 2px 防抖动（与银狼 LV.999
的 E 状态图标同一套做法）。

**为什么要强制校验**：黄泉图的 `e` 步骤、银狼 LV.999 图的 `lv999_e` 步骤都是按
对应角色的技能录制的。1 号位放错角色时地图会整体跑歪，而且不会报错 —— 越早
终止越省时间（README 运行须知：黄泉专用地图必须为黄泉）。这也是
`map_operations.py` 里原 TODO「黄泉情况下必须为黄泉角色」的落地。

校验只对 `REQUIRED_FIRST_ROLE` 里登记的版本生效，其它版本保持原来的宽松行为。
"""

from typing import NamedTuple

from utils.core.exceptions import CustomException
from utils.core.log import log
from utils.core.match_offsets import padded_offset_for_box
from utils.core.thresholds import FIRST_ROLE_ICON
from utils.drivers.screen import BASE_HEIGHT, BASE_WIDTH

#: 角色头像识别框的左上角，坐标是 1920×1080 的截图基准（与
#: `take_screenshot` 的 offset 同一坐标系）。
ROLE_ICON_POSITION = (1790, 310)

#: 识别框大小 = 模板大小（两张模板都按 20×30 裁切）。
ROLE_ICON_SIZE = (20, 30)

#: 搜索区域在模板四周各外扩的像素数（防反烧屏/动画抖动）。
ROLE_ICON_PADDING = 2

#: 角色 key。与地图版本名分开：同一个角色将来可能被多个版本要求。
ROLE_ACHERON = "acheron"
ROLE_SILVER_WOLF_LV999 = "silver_wolf_lv999"


class RoleIcon(NamedTuple):
    """一个角色头像模板：模板路径 + 日志/报错用的中文名。"""

    path: str
    label: str


#: 角色 key → 模板。`.png` / `.webp` 都行：`images.resolve_path` 会按
#: webp > png > jpg 找同名文件，所以目录里是 png 也照样加载。
ROLE_ICONS = {
    ROLE_ACHERON: RoleIcon("./picture/roles_pic/role_acheron.png", "黄泉"),
    ROLE_SILVER_WOLF_LV999: RoleIcon(
        "./picture/roles_pic/role_silver_wolf_lv999.png", "银狼 LV.999"
    ),
}

#: 地图版本 → 1 号位必须是的角色。不在表里的版本不做校验。
REQUIRED_FIRST_ROLE = {
    "HuangQuan": ROLE_ACHERON,
    "SilverWolfLv999": ROLE_SILVER_WOLF_LV999,
}


def role_icon_offset(
    template_size=ROLE_ICON_SIZE,
    position=ROLE_ICON_POSITION,
    pad=ROLE_ICON_PADDING,
):
    """模板尺寸 → `take_screenshot(offset=...)` 的四边增量。

    **offset 不是 width/height**：它是加在截取区域四条边上的增量，
    左上为正（往里收）、右下为负（从右/下边缘往里收）。（0,0,0,0）是整张
    1920×1080。模板框固定在上表位置，四周各外扩 `pad` 像素，并夹在
    1920×1080 之内 —— 所以右下角贴边时实际外扩量会变成 0，这是正常的。

    20×30 的模板在 (1790,310)、pad=2 时：
        框 = (1790, 310, 1810, 340) → 外扩 (1788, 308, 1812, 342)
        offset = (1788, 308, 1812-1920, 342-1080) = (1788, 308, -108, -738)

    :param template_size: (width, height)
    :raises CustomException: 模板放在该位置会超出画面 —— 说明模板裁过头了
    """
    width, height = template_size
    left, top = position
    right, bottom = left + width, top + height
    if right > BASE_WIDTH or bottom > BASE_HEIGHT:
        raise CustomException(
            f"1 号位角色模板 {width}×{height} 放在 ({left},{top}) 会超出 "
            f"{BASE_WIDTH}×{BASE_HEIGHT} 画面；请重新裁切模板或修正坐标"
        )
    # 用 (0,0,1920,1080) 这个虚拟基准区域算四边增量：offset 本来就是相对基准
    # 区域的增量，不需要知道窗口在桌面上的绝对位置。
    offset, _, _ = padded_offset_for_box(
        (left, top, right, bottom), (0, 0, BASE_WIDTH, BASE_HEIGHT), pad
    )
    return offset


def recognize_first_role(img):
    """识别 1 号位是谁。

    :return: `{"role": 角色 key 或 None, "max_val": 最高匹配度,
              "scores": {角色 key: 匹配度}}`。两张模板都没过
              `FIRST_ROLE_ICON` 时 `role` 为 None。
    :raises CustomException: 模板缺失或损坏 —— 那是配置错误，不是「没找到」

    两张模板**共用同一帧**比对（CLAUDE.md R10）：识别框只有 24×34，
    逐个 `scan_screenshot` 会在同一位置重复截图，没必要也不算对。
    """
    templates = {}
    for role, icon in ROLE_ICONS.items():
        template = img.get_img(icon.path)
        if template is None:
            raise CustomException(
                f"缺少 1 号位角色模板 {icon.path}（文件不存在或损坏）"
            )
        height, width = template.shape[:2]
        if (width, height) != ROLE_ICON_SIZE:
            raise CustomException(
                f"1 号位角色模板 {icon.path} 尺寸 {width}×{height}，"
                f"与识别框 {ROLE_ICON_SIZE[0]}×{ROLE_ICON_SIZE[1]} 不一致；"
                "请按同一位置重新裁切"
            )
        templates[role] = template

    frame, left, top, _, _ = img.take_screenshot(offset=role_icon_offset())
    scores = {
        role: img.match_screenshot(frame, template, left, top)["max_val"]
        for role, template in templates.items()
    }

    role, max_val = max(scores.items(), key=lambda item: item[1])
    if max_val <= FIRST_ROLE_ICON:  # 判定方向与全项目一致：严格大于阈值
        role = None
    return {"role": role, "max_val": max_val, "scores": scores}


def check_first_role(map_version, img):
    """按地图版本强制校验 1 号位角色；不需要校验的版本直接返回 None。

    黄泉版本要求 1 号位是黄泉，银狼 LV.999 版本要求是银狼 LV.999。识别结果
    可能是「其它角色」或「两张模板都不像」，两种都终止运行 —— 放错角色时
    地图会整体跑歪，继续跑只会浪费一轮时间。

    :raises CustomException: 1 号位不是该版本要求的角色，或模板缺失
    """
    required = REQUIRED_FIRST_ROLE.get(map_version)
    if required is None:
        return None

    detection = recognize_first_role(img)
    if detection["role"] == required:
        log.info(
            f"1号位角色校验通过：{ROLE_ICONS[required].label}，"
            f"匹配度{detection['scores'][required]:.3f}"
        )
        return detection

    expected = ROLE_ICONS[required].label
    detected = (
        ROLE_ICONS[detection["role"]].label
        if detection["role"]
        else "未识别出角色"
    )
    scores = "，".join(
        f"{ROLE_ICONS[role].label} {value:.3f}"
        for role, value in detection["scores"].items()
    )
    raise CustomException(
        f"1号位角色不符：{map_version} 地图要求 1 号位为{expected}，"
        f"当前识别到{detected}（{scores}，阈值 {FIRST_ROLE_ICON}）。"
        "请把对应角色放到队伍 1 号位后重新运行"
    )
