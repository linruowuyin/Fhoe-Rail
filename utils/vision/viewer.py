"""调试用图片窗口 —— cv2 的显示接口。

放 vision 层的理由不是"它做识别"（它不做），而是分层规则本身：
**只有 vision/ 直接 import cv2**。这个模块也不识别、也不抓屏，
它是全项目唯一该碰 cv2 显示 API 的地方。

调用方是 ui/pause.py —— F7~F10 暂停时显示最后那个传送点的图，供人肉确认
"停在哪了"。
"""

import cv2

#: 窗口名。固定一个，避免反复 imshow 叠出一堆窗口。
WINDOW_NAME = "temp_point"


def show(image) -> None:
    """把一张图显示出来。"""
    cv2.imshow(WINDOW_NAME, image)


def pump() -> None:
    """让出一次 GUI 事件循环（cv2.waitKey(1)）。

    不是"等 1 毫秒"—— 是让窗口有机会重绘与响应。少了它窗口会是白板。
    """
    cv2.waitKey(1)


def close_all() -> None:
    cv2.destroyAllWindows()
