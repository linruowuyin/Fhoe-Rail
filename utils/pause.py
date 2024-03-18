import threading
import keyboard
import cv2 as cv
from .log import log

class Pause:
    def __init__(self, dev=False):
        self.dev = dev
        if self.dev:
            self.pause_event = threading.Event()
            self.last_key_pressed = None  # 记录最后按下的按键
            self.pause_event.clear()
            keyboard.on_press_key("F8", self.toggle_pause)
            keyboard.on_press_key("F9", self.continue_and_restart)
        else:
            self.pause_event = None

    def toggle_pause(self, event):
        if not self.dev:
            return
        if self.pause_event.is_set():
            log.info("检测到按下'F8'，即将继续")
            self.pause_event.clear()
            self.last_key_pressed = 'F8'
        else:
            log.info("检测到按下'F8'暂停，将在下一个检测点自动暂停。按下'F8'继续 或 按下'F9'重新传送至地图")
            self.pause_event.set()
            self.last_key_pressed = 'F8'

    def continue_and_restart(self, event):
        if not self.dev:
            return
        if self.pause_event.is_set():
            log.info("检测到按下'F9'，即将重新传送至地图")
            self.pause_event.clear()
            self.last_key_pressed = 'F9'

    def check_pause(self, dev, last_point):
        if not self.dev:
            return False
        if dev:
            show = False
            press = False
            while self.pause_event.is_set():
                press = True
                if not show:
                    if last_point:
                        show = True
                        log.info(f"展示传送点：{last_point}")
                        image = cv.imread(last_point)
                        if image is not None:
                            cv.imshow('temp_point', image)
                            while self.pause_event.is_set():
                                cv.waitKey(1)
            if press:
                cv.destroyAllWindows()
                return self.last_key_pressed == 'F9'
            else:
                return False
        else:
            return False
