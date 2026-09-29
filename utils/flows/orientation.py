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
from utils.vision.img import Img


class Orientation:
    """视角设置、重置、旋转与校准。"""

    def __init__(self, cfg, img, mouse_event, move):
        self.cfg = cfg
        self.img = img
        self.mouse_event = mouse_event
        self.move = move

        self.arrow_begin = None  # 初始箭头
        self.multi_config = 1.0
        self.arrow_0 = Img.get_img("./picture/screenshot_arrow.png")


    def handle_view_set(self, value):
        """设置初始视角"""
        time.sleep(value)
        self.arrow_begin = arrow.take_arrow(self.img)

    def handle_view_reset(self, value):
        """重置视角"""
        time.sleep(value)
        sub = 0
        cnt = 0
        self.move(value=0.01, key="w")  # 重置箭头指向为视角方向
        time.sleep(0.6)
        while cnt < 4:
            arrow_temp = arrow.take_arrow(self.img)
            ang = arrow.cal_ang(self.img, arrow_temp, self.arrow_begin)
            sub = 360 - ang
            sub = (sub + 180) % 360 - 180
            sub = sub if sub != 0 else 1e-9
            log.info(f"开始重置视角，计算角度ang:{ang}，旋转角度sub:{sub}")
            # KeyboardEvent.keyboard_press("caps_lock", 0.2)
            # time.sleep(1)
            self.mouse_event.mouse_move(sub)
            self.move(value=0.01, key="w")
            cnt += 1
            if abs(sub) <= 1:
                break
            time.sleep(0.6)

    def handle_view_rotate(self, value):
        """
        旋转视角至value度，顺时针
        """
        time.sleep(1)
        sub = 0
        cnt = 0
        self.move(value=0.01, key="w")  # 重置箭头指向为视角方向
        time.sleep(0.6)
        arrow_temp = self.arrow_0
        final_arrow = self.img.image_rotate(arrow_temp, -value)
        while cnt < 4:
            arrow_temp = arrow.take_arrow(self.img)
            ang = arrow.cal_ang(self.img, arrow_temp, final_arrow)
            sub = 360 - ang
            sub = (sub + 180) % 360 - 180
            sub = sub if sub != 0 else 1e-9
            log.info(f"开始旋转视角，计算角度ang:{ang}，旋转角度sub:{sub}")
            # KeyboardEvent.keyboard_press("caps_lock", 0.2)
            # time.sleep(1)
            self.mouse_event.mouse_move(sub)
            self.move(value=0.01, key="w")
            cnt += 1
            if abs(sub) <= 1:
                break
            time.sleep(0.6)

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
                    sub = now_ang - last_ang
                    sub = (
                        sub + 360
                        if (move_num >= 0 and sub < 0)
                        else sub - 360
                        if (move_num < 0 and sub > 0)
                        else sub
                    )
                    ang_list.append(sub)
                    last_ang = now_ang

                valid_angles = [
                    a for a in ang_list if abs(a - np.median(ang_list)) <= 5
                ]
                if valid_angles:
                    ax = sum([move_num for _ in valid_angles])
                    ay = sum(valid_angles)

                    if ay != 0:
                        offset_list.append(ax / ay)
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
