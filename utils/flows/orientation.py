"""视角校准 —— 从 Handle 拆出来的第三簇。

识别部分在 `vision/arrow.py`；这里只做编排：按一下 w 让箭头指向与视角方向一致，
读箭头角度，转动视角，直到对齐。

:param move: 注入的「短按 w」动作，通常是 Handle.handle_move。
    本簇需要它，但它是移动簇的能力 —— 用具名参数注入而不是反向持有 Handle，
    边界才不会被这层绕回去。
"""

import time

import numpy as np

from utils.core.log import log
from utils.vision import arrow
from utils.vision import assets
from utils.vision.img import Img

# 校准最多转几次就放弃
MAX_ALIGN_TRIES = 4
# 转到位判定：角度差小于 1 度就认为对齐了
ALIGN_TOLERANCE = 1
# 连续两次读数之差超过这些度数的，当成离群值丢掉
OUTLIER_TOLERANCE = 5


def signed_rotation_to(ang: float) -> float:
    """把 `arrow.cal_ang` 给的 0..359 夹角，换成鼠标该转的角度。

    先反向（箭头转了 ang，视角就要转 -ang），再折成 (-180, 180]。

    结果正好是 0 时替换成一个极小值：调用方拿它去判断「是否已对齐」并做除法的
    中间量，0 会让循环空转。
    """
    sub = 360 - ang
    sub = (sub + 180) % 360 - 180
    return sub if sub != 0 else 1e-9


def unwrap_angle_delta(delta: float, direction: float) -> float:
    """把相邻两次读数之差折到 `direction` 那一侧，消掉跨过 0 度的那一跳。

    朝正方向转却读出负的差值，说明中间跨了 0 度（比如 179 → -179），加回 360。
    """
    if direction >= 0 and delta < 0:
        return delta + 360
    if direction < 0 and delta > 0:
        return delta - 360
    return delta


def median_filtered(angles: list, tolerance: float = OUTLIER_TOLERANCE) -> list:
    """丢掉偏离中位数超过 `tolerance` 的读数。读数为空时返回空表。"""
    if not angles:
        return []
    median = float(np.median(angles))
    return [a for a in angles if abs(a - median) <= tolerance]


class Orientation:
    """视角设置、重置、旋转与校准。"""

    def __init__(self, cfg, img, mouse_event, move):
        self.cfg = cfg
        self.img = img
        self.mouse_event = mouse_event
        self.move = move

        self.arrow_begin = None  # 初始箭头
        self.multi_config = 1.0
        self.arrow_0 = Img.get_img(assets.path("screenshot_arrow"))

    def handle_view_set(self, value):
        """设置初始视角"""
        time.sleep(value)
        self.arrow_begin = arrow.take_arrow(self.img)

    def _align_to(self, target_arrow, label: str):
        """转视角直到箭头对齐 `target_arrow`，最多试 `MAX_ALIGN_TRIES` 次。

        `handle_view_reset` 与 `handle_view_rotate` 只有目标箭头和日志前缀不同，
        收敛过程是同一段 —— 原先两处逐行重复。
        """
        for _ in range(MAX_ALIGN_TRIES):
            arrow_temp = arrow.take_arrow(self.img)
            ang = arrow.cal_ang(self.img, arrow_temp, target_arrow)
            sub = signed_rotation_to(ang)
            log.info(f"{label}，计算角度ang:{ang}，旋转角度sub:{sub}")
            self.mouse_event.mouse_move(sub)
            self.move(value=0.01, key="w")
            if abs(sub) <= ALIGN_TOLERANCE:
                break
            time.sleep(0.6)

    def handle_view_reset(self, value):
        """重置视角"""
        time.sleep(value)
        self.move(value=0.01, key="w")  # 重置箭头指向为视角方向
        time.sleep(0.6)
        self._align_to(self.arrow_begin, "开始重置视角")

    def handle_view_rotate(self, value):
        """
        旋转视角至value度，顺时针
        """
        time.sleep(1)
        self.move(value=0.01, key="w")  # 重置箭头指向为视角方向
        time.sleep(0.6)
        final_arrow = self.img.image_rotate(self.arrow_0, -value)
        self._align_to(final_arrow, "开始旋转视角")

    def set_angle(self, ang=None):
        """校准视角旋转"""
        if ang is None:
            ang = [1, 1, 3]

        log.info("开始校准")
        move_list = [60, -60]
        offset_list = []

        for move_num in move_list:
            self.move(0.01, "w")
            time.sleep(0.6)
            self.handle_view_set(0.1)
            init_ang = arrow.cal_ang(self.img, self.arrow_begin, self.arrow_begin)
            log.debug(f"init_ang: {init_ang}")
            last_ang = init_ang

            for repeat in ang:
                if last_ang != init_ang and repeat == 1:
                    continue

                ang_list = []
                for _ in range(repeat):
                    self.mouse_event.mouse_move(move_num, fine=3 // repeat, align=True)
                    time.sleep(0.2)
                    self.move(0.01, "w")
                    time.sleep(0.6)
                    arrow_temp = arrow.take_arrow(self.img)
                    now_ang = arrow.cal_ang(self.img, arrow_temp, self.arrow_begin)
                    log.debug(f"now_ang: {now_ang}")
                    ang_list.append(unwrap_angle_delta(now_ang - last_ang, move_num))
                    last_ang = now_ang

                valid_angles = median_filtered(ang_list)
                if valid_angles:
                    # 鼠标走了 move_num×n 像素、视角转了 sum 度 → 比例就是 ax/ay
                    total_angle = sum(valid_angles)
                    if total_angle != 0:
                        offset_list.append(move_num * len(valid_angles) / total_angle)
                    else:
                        log.info("疑似校准错误")
                        offset_list.append(1)

        if offset_list:
            self.multi_config = np.median(offset_list)
            self.cfg.modify_json_file(
                filename=self.cfg.CONFIG_FILE_NAME,
                key="angle",
                value=str(self.multi_config),
            )
            self.cfg.modify_json_file(
                filename=self.cfg.CONFIG_FILE_NAME, key="angle_set", value=True
            )
            log.info(f"校准完成，angle: {self.multi_config}")
        else:
            log.info("校准失败")

        time.sleep(1)
