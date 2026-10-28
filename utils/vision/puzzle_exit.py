"""Recognize the specific Chinese puzzle-abandon dialog from one 1080p frame.

The prompt and the confirm button must both match in their expected regions.
Matching only the generic confirm label could accept purchases or battle exits.

与项目其它检测器共用 `Matcher.match_screenshot`：样本收集、次优峰/探针口径都一致。
两个区域是**帧内绝对坐标**，登记在 `assets.ABSOLUTE_REGIONS` —— 它们不是
`take_screenshot(offset=...)` 的四边增量，别拿来互相换算。
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
    match_left, match_top = result["max_loc"]
    return match_left + width // 2, match_top + height // 2


def find_puzzle_exit_confirmation(frame, prompt, confirm):
    """Return the confirm-button center, or None; never capture or click here.

    Coordinates refer to the same 1920x1080 client frame supplied by ScreenSource.
    Unknown resolutions and missing resources fail closed.
    """
    if frame is None or frame.shape[:2] != (BASE_HEIGHT, BASE_WIDTH):
        return None
    prompt_region = assets.bounds("puzzle_exit_prompt")
    confirm_region = assets.bounds("puzzle_exit_confirm")
    if _match_region(frame, prompt, prompt_region, PUZZLE_EXIT_PROMPT) is None:
        return None
    return _match_region(frame, confirm, confirm_region, PUZZLE_EXIT_CONFIRM)
