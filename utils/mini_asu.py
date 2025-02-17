import cv2 as cv
import numpy as np


class ASU:
    def __init__(self):
        self.screen = None
        self.rotate = False

    # 计算旋转变换矩阵
    def handle_rotate_val(self, x, y, rotate):
        cos_val = np.cos(np.deg2rad(rotate))
        sin_val = np.sin(np.deg2rad(rotate))
        return np.float32(
            [
                [cos_val, sin_val, x * (1 - cos_val) - y * sin_val],
                [-sin_val, cos_val, x * sin_val + y * (1 - cos_val)],
            ]
        )

    # 图像旋转（以任意点为中心旋转）
    def image_rotate(self, src, rotate=0):
        h, w, _ = src.shape
        m = self.handle_rotate_val(w // 2, h // 2, rotate)
        img = cv.warpAffine(src, m, (w, h))
        return img

    # 计算小地图中蓝色箭头的角度
    def get_now_direc(self):
        loc_scr = self.screen[101:241, 94:224]
        arrow = "./picture/loc_arrow.jpg"
        arrow = cv.imread(arrow)
        hsv = cv.cvtColor(loc_scr, cv.COLOR_BGR2HSV)  # 转HSV
        lower = np.array([93, 120, 60])
        upper = np.array([97, 255, 255])
        mask = cv.inRange(hsv, lower, upper)  # 创建掩膜
        loc_tp = cv.bitwise_and(loc_scr, loc_scr, mask=mask)
        mx_acc = 0
        ang = 0
        for i in range(360):
            rt = self.image_rotate(arrow, i)
            result = cv.matchTemplate(loc_tp, rt, cv.TM_CCORR_NORMED)
            _, max_val, _, _ = cv.minMaxLoc(result)
            if max_val > mx_acc:
                mx_acc = max_val
                ang = i
        return ang
