"""色域判定 —— 按 HSV 区间判断画面里有没有目标颜色。

与模板匹配是两类检测器：那个比「像不像」，这个比「有没有这个颜色」。
参数（区间）是识别参数，所以和样板图一样归 vision。

⚠️  通道序不一致（已知，暂不改）
    `FIRST_ROLE_RANGES` 配的是 `cv2.COLOR_RGB2HSV`，而 `take_screenshot` 返回的是
    **BGR**（见 drivers/screen.py）。也就是说这里实际把 BGR 当 RGB 解释，色相是偏的。
    但区间是对着这个行为调出来的 —— **改其中一边就必须同时重标区间**，
    否则"1 号位判定"会立刻失效。要纠正就两边一起改并重新标定。
"""

import cv2
import numpy as np

#: 1 号位角色头像的颜色。配合 any_pixel_in_ranges 使用（注意上面的通道序说明）。
FIRST_ROLE_RANGES = [
    ([28, 49, 253], [32, 189, 255]),
    ([114, 240, 216], [116, 246, 226]),
]


def any_pixel_in_ranges(image, ranges) -> bool:
    """image 里是否有像素落在 ranges 的任一所给 HSV 区间内。"""
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    for lower, upper in ranges:
        if np.any(cv2.inRange(hsv, np.array(lower), np.array(upper))):
            return True
    return False
