"""从一张 1920×1080 帧里识别「是否放弃游玩？」弹窗。

判定是**两段式 AND**，两段必须出现在同一帧上：

1. 提示语（“是否放弃游玩？”）出现在上方提示区域；
2. 右侧的「确认」按钮出现在按钮区域。

只匹配通用的「确认」两个字是不够的 —— 购买、战斗退出等弹窗也有确认键，
误点会把流程带到别的界面。两个区域登记在 `assets.ABSOLUTE_REGIONS`：它们是
**帧内绝对坐标**，不是 `take_screenshot(offset=...)` 的四边增量，别互相换算。

这里只做识别，不截图、不点击；副作用都在 `flows/puzzle_exit.py`。
"""

from utils.core.thresholds import PUZZLE_EXIT_CONFIRM, PUZZLE_EXIT_PROMPT
from utils.drivers.screen import BASE_HEIGHT, BASE_WIDTH
from utils.vision import assets
from utils.vision.matcher import Matcher

#: 固定用「原图 CCOEFF」。阈值 0.90 是按 `TM_CCOEFF_NORMED` 在实机样本（含
#: 擦除文字/按钮的负样本）上量的；换成默认的 CCORR 时，同样本负样本仍有
#: 0.92 / 0.91，会直接越过阈值 —— 换算法必须先重新量阈值。
MATCH_STRATEGY = assets.MATCH_COLOR_CCOEFF


def _match_region(frame, template, bounds, threshold):
    """在帧内绝对区域 `bounds` 里匹配一个模板。

    :return: 命中时返回模板中心 `(x, y)`（帧内坐标）；没命中、模板缺失、
        或区域比模板还小都返回 None —— 检测器返回「没找到」，不抛异常（R12）。
    """
    if template is None:
        return None
    left, top, right, bottom = bounds
    region = frame[top:bottom, left:right]
    height, width = template.shape[:2]
    if region.shape[0] < height or region.shape[1] < width:
        return None
    result = Matcher.match_screenshot(
        region, template, left, top, strategy=MATCH_STRATEGY
    )
    if result["max_val"] <= threshold:
        return None
    # 中心点换算复用 Matcher 的那一份，别在这里再抄一遍
    return Matcher.img_center_point(result, template.shape)


def find_puzzle_exit_confirmation(frame, prompt, confirm):
    """返回「确认」按钮中心；没识别到返回 None。只读一帧，不截图、不点击。

    :param frame: `ScreenSource.take_screenshot()` 返回的 BGR 帧。必须是
        1920×1080 —— 其它分辨率不做猜测，直接 fail closed（返回 None）。
    """
    if frame is None or frame.shape[:2] != (BASE_HEIGHT, BASE_WIDTH):
        return None
    prompt_region = assets.bounds("puzzle_exit_prompt")
    confirm_region = assets.bounds("puzzle_exit_confirm")
    if _match_region(frame, prompt, prompt_region, PUZZLE_EXIT_PROMPT) is None:
        return None
    return _match_region(frame, confirm, confirm_region, PUZZLE_EXIT_CONFIRM)
