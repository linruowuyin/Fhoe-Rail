import threading
import time
from typing import Union

import keyboard

from utils.vision.img import Img
from utils.core.log import log
from utils.vision import viewer

# 模块级保存已注册的键盘监听器，避免每张地图 new Pause() 时重复注册导致监听器泄漏
_INSTALLED_HANDLERS = []


class Pause:
    def __init__(self, dev=False):
        self.dev = dev

        self.pause_event = threading.Event()
        self.last_key_pressed = None  # 记录最后按下的按键
        # 深层循环（拖地图找点位那类）里按下的 F9/F10：那里的闸门只会「恢复运行」，
        # 重跑意图先寄存在这，由最近的步骤检查点消费 —— 否则按了 F9 却只是继续跑。
        self.pending_key = None
        self.pause_event.clear()
        # 先注销上一次注册的监听器，再重新注册（每次跑图会重新创建一个 Pause）
        for handler in _INSTALLED_HANDLERS:
            try:
                keyboard.unhook(handler)
            except Exception:
                pass
        _INSTALLED_HANDLERS.clear()
        _INSTALLED_HANDLERS.append(keyboard.on_press_key("F7", self.continue_in_map))
        _INSTALLED_HANDLERS.append(keyboard.on_press_key("F8", self.toggle_pause))
        _INSTALLED_HANDLERS.append(
            keyboard.on_press_key("F9", self.continue_and_restart)
        )
        _INSTALLED_HANDLERS.append(keyboard.on_press_key("F10", self.continue_new_map))

    def continue_in_map(self, event):
        if self.pause_event.is_set():
            log.info("检测到按下'F7'，即将继续")
            self.pause_event.clear()
            self.last_key_pressed = "F7"

    def toggle_pause(self, event):
        if self.pause_event.is_set():
            log.info("检测到按下'F8'，当前已在暂停，无操作")
            self.last_key_pressed = "F8"
        else:
            log.info(
                "检测到按下'F8'暂停，将在下一个检测点自动暂停。按下'F7'继续 或 选中传送点后按下'F9'重新传送至地图"
            )
            self.pause_event.set()
            self.last_key_pressed = "F8"

    def continue_and_restart(self, event):
        if not self.dev:
            return
        if self.pause_event.is_set():
            log.info("检测到按下'F9'，即将重新传送至地图")
            self.pause_event.clear()
            self.last_key_pressed = "F9"
            self.pending_key = "F9"

    def continue_new_map(self, event):
        if not self.dev:
            return
        if self.pause_event.is_set():
            log.info("检测到按下'F10'，即将重跑map")
            self.pause_event.clear()
            self.last_key_pressed = "F10"
            self.pending_key = "F10"

    def _show_img(self, img: str):
        """展示图片

        Args:
            img (str): 图片地址
        """
        log.info(f"展示图片：{img}")
        image = Img.get_img(img)
        if image is not None:
            viewer.show(image)
            while self.pause_event.is_set():
                viewer.pump()

    def check_pause(self, dev: bool, last_point: str) -> Union[str, bool]:
        """检查是否暂停，暂停情况下返回取消暂停使用的按键

        Args:
            dev (bool): 开发者模式下允许暂停
            last_point (str): 最后传送点图片地址

        Returns:
            str | bool: 暂停取消时返回暂停取消的按键字符串'F10','F9','F8'，无暂停时返回False
        """

        show = False
        press = False
        while self.pause_event.is_set():
            press = True
            if not show and last_point and dev:
                show = True
                self._show_img(last_point)
            # 必须 sleep：dev=False 且 last_point 为空时循环体没有别的事可做，忙等会把
            # 一个 CPU 核心跑满，还会跟后台截图线程抢 GIL（见 CLAUDE.md R2）
            time.sleep(0.05)
        if press:
            viewer.close_all()
            # 同一个意图已经由 last_key_pressed 带出去了，别让它再触发一次重跑
            self.pending_key = None
            return self.last_key_pressed
        if self.pending_key is not None:
            # 深层循环里按下的 F9/F10 只会恢复运行，意图寄存在这里，由本检查点消费
            key = self.pending_key
            self.pending_key = None
            return key
        else:
            return False

    def wait_if_paused(self) -> float:
        """暂停时阻塞到恢复，返回被暂停的秒数；没暂停返回 0.0。

        给 flows 层那些「拖地图找点位」的循环用。与 check_pause 的分工：这里只负责
        停住，不弹调试图片（弹图是 handle 阶段检查点的语义）。

        **调用方必须把返回值从自己的墙钟死线里扣掉**，否则暂停会吃掉搜索的超时预算，
        恢复后立刻超时、报「传送点查找失败」—— 而且只在暂停过的路径上出现。
        """
        if not self.pause_event.is_set():
            return 0.0
        paused_from = time.time()
        while self.pause_event.is_set():
            time.sleep(0.05)
        return time.time() - paused_from
