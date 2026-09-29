"""小地图箭头 —— 从 Handle 拆出来的识别部分。

只用 cv2/numpy，不碰键鼠、不碰窗口。取箭头是 HSV 掩膜，求角度是 360 度
暴力旋转匹配（`cal_ang`）—— 后者是这条路径上最贵的一步，见 CLAUDE.md 的性能注记。

这几个函数接受 `img`（Img 门面）而不是持有它：它们只借它做截图与旋转。
"""

import cv2
import numpy as np


def take_screenshot_arrow(img):
    """
    截取小地图蓝色箭头
    """
    # 小地图中心 460-320=140,345-194=151
    screenshot = img.take_screenshot(offset=(125, 136, -1765, -914))[0]

    return screenshot

def take_arrow(img):
    """
    截取小地图蓝色箭头，进行HSV颜色过滤
    """
    img = take_screenshot_arrow(img)
    # 转换到HSV颜色空间
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([93, 120, 60])
    upper_blue = np.array([97, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    result_img = cv2.bitwise_and(img, img, mask=mask)

    return result_img

def cal_ang(img, arrow_img, arrow_begin_img):
    """计算与初始蓝色箭头相差的角度"""
    mx_acc = 0
    ang = 0
    for i in range(360):
        rt = img.image_rotate(arrow_img, i)
        result = cv2.matchTemplate(arrow_begin_img, rt, cv2.TM_CCORR_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val > mx_acc:
            mx_acc = max_val
            mx_loc = (max_loc[0] + 12, max_loc[1] + 12)
            ang = i

    return ang
