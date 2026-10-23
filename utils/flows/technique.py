"""银狼 LV.999 秘技（`check_e`）：设置整轮只做一次，E 每次都按，按完验证状态。

地图 JSON 里每张银狼图的开头是 `{"check_e": 1}`，分两段：

  * 第一段：银狼专用游戏设置。目前就是 `handle.auto_use_technique_consumable()`
    —— 它走 ESC → 设置 → 其他设置 → 拖动 → 点开关键 → 确认 的硬编码流程。
    **整轮只执行一次**；失败时抛 `CustomException`，由 `fhoe.py` 的 `__main__`
    兜底：写日志并发 `notify_on_error` 通知，不会静默继续。
  * 第二段：按 E 打开秘技状态，然后用 `picture/silver_wolf_lv999_e.png` 验证。
    固定用 `handle_e(2)` —— value=2 是「只放秘技」，不点画面中心、不进入战斗；
    value=1 是「引战」语义，不能用在地图开头。没检测到状态就抛
    `CustomException` 终止本轮（不自动重按：E 若有开关语义，盲按第二次会把
    刚打开的状态关掉；确认 E 一定是「使用」而不是「切换」后再考虑重试）。

状态放在 `Technique` 实例上，由 `MapOperations` 持有：分派 `check_e` 的是它，
R13 要求跨模块状态挂在读取方真正持有的对象上。一个实例覆盖 `allow_run_again`
和跨日连锄；`--dev` 重开是新实例，设置会重做一次（配方在设计上应当幂等）。

TODO(银狼专用设置): 现在只有一个开关。后续如果银狼还需要别的游戏内开关，
都加在 `ensure_settings` 里，**每一项都必须先识图判断当前状态再点**——盲点开关键
在「本来就是开」的时候会把它关掉；新增的硬编码设置不要另起一套流程。

TODO(阈值校准): `SILVER_WOLF_LV999_E_ICON` 是用户指定的 0.98 精确匹配阈值；
模板 7×14、搜索区按模板尺寸 + 2px 外扩。若游戏更新后误报/漏报，先跑
tools/match_probe.py 量正负样本，再按实测余量调整。
"""

from utils.core.exceptions import CustomException
from utils.core.match_offsets import padded_offset_for_box
from utils.core.thresholds import SILVER_WOLF_LV999_E_ICON
from utils.drivers.screen import BASE_HEIGHT, BASE_WIDTH

#: 银狼 LV.999 E 状态图标的左上角，坐标是 1920×1080 的截图基准（与
#: `take_screenshot` 的 offset 同一坐标系）。模板 7×14，右边缘 1637、下边缘 334。
SILVER_WOLF_LV999_E_POSITION = (1630, 320)

#: 模板搜索区域在 7×14 模板四周各外扩的像素数（防反烧屏/动画抖动）。
SILVER_WOLF_LV999_E_PADDING = 2

#: 模板文件。`.png` / `.webp` 都行：`images.resolve_path` 会按 webp > png > jpg
#: 找同名文件，所以目录里是 png 也照样加载。
SILVER_WOLF_LV999_E_IMAGE = "./picture/silver_wolf_lv999_e.png"


def e_state_offset(
    template_size,
    position=SILVER_WOLF_LV999_E_POSITION,
    pad=SILVER_WOLF_LV999_E_PADDING,
):
    """模板尺寸 → `take_screenshot(offset=...)` 的四边增量。

    **offset 不是 width/height**：它是加在截取区域四条边上的增量，
    左上为正（往里收）、右下为负（从右/下边缘往里收）。（0,0,0,0）是整张
    1920×1080。模板框固定在上表位置，四周各外扩 `pad` 像素，并夹在
    1920×1080 之内 —— 所以右下角贴边时实际外扩量会变成 0，这是正常的。

    7×14 的模板在 (1630,320)、pad=2 时：
        框 = (1630, 320, 1637, 334) → 外扩 (1628, 318, 1639, 336)
        offset = (1628, 318, 1639-1920, 336-1080) = (1628, 318, -281, -744)

    :param template_size: (width, height)
    :raises CustomException: 模板放在该位置会超出画面 —— 说明模板裁过头了
    """
    width, height = template_size
    left, top = position
    right, bottom = left + width, top + height
    if right > BASE_WIDTH or bottom > BASE_HEIGHT:
        raise CustomException(
            f"银狼 LV.999 E 状态模板 {width}×{height} 放在 ({left},{top}) 会超出 "
            f"{BASE_WIDTH}×{BASE_HEIGHT} 画面；请重新裁切模板或修正坐标"
        )
    # 用 (0,0,1920,1080) 这个虚拟基准区域算四边增量：offset 本来就是相对基准
    # 区域的增量，不需要知道窗口在桌面上的绝对位置。
    offset, _, _ = padded_offset_for_box(
        (left, top, right, bottom), (0, 0, BASE_WIDTH, BASE_HEIGHT), pad
    )
    return offset


class Technique:
    """银狼秘技的两段逻辑与「设置已做」状态。"""

    def __init__(self):
        #: 本次运行（一个 MapOperations 实例）里，银狼设置是否已经验证成功。
        #: 只有 auto_use_technique_consumable() 返回 True 才置位，失败不置位。
        self.settings_ready = False

    def ensure_settings(self, handle) -> bool:
        """确保银狼设置已完成；已完成时直接返回 True（不再走菜单）。

        返回 False 表示这次设置失败（或菜单/识图没找到）。调用方决定是中止
        （SilverWolf 版本）还是警告后继续（其它版本）。
        """
        if self.settings_ready:
            return True
        if not handle.auto_use_technique_consumable():
            return False
        self.settings_ready = True
        return True

    def is_e_active(self, handle) -> bool:
        """右上角是否出现银狼 LV.999 秘技已开启的状态图标。

        模板缺失 / 裁切超出画面时抛 `CustomException`（配置错误，不是「没找到」）。
        没匹配到只返回 False。
        """
        template = handle.img.get_img(SILVER_WOLF_LV999_E_IMAGE)
        if template is None:
            raise CustomException(
                f"缺少银狼 LV.999 E 状态图 {SILVER_WOLF_LV999_E_IMAGE}"
                "（文件不存在或损坏）"
            )
        height, width = template.shape[:2]
        offset = e_state_offset((width, height))
        return handle.img.on_interface(
            check_list=[template],
            timeout=1.0,
            interface_desc="银狼 LV.999 秘技已开启",
            threshold=SILVER_WOLF_LV999_E_ICON,
            offset=offset,
        )

    def check_e(self, value, handle):
        """执行一步 `{"check_e": 1}`：首次做设置，按 E，然后验证状态。"""
        if value != 1:
            raise CustomException(
                f"map数据错误, check_e参数只能为1（设置+按E），实际为 {value!r}"
            )
        if not self.ensure_settings(handle):
            # fhoe.py 的顶层 except 会捕获它，写日志并发 notify_on_error 通知。
            raise CustomException(
                "银狼 LV.999 秘技设置失败：自动使用秘技消耗品未能开启，已终止运行"
            )

        handle.handle_e(2)  # 只放秘技，不点屏幕、不引战
        if not self.is_e_active(handle):
            raise CustomException(
                "银狼 LV.999 秘技未能开启（按 E 后未检测到状态图标），已终止运行"
            )
