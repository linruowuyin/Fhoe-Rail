import os
import time

import cv2

from utils.img import Img
from utils.log import log


class BlackScreen:
    def __init__(self):
        self.img = Img()

    def blackscreen_check(self, threshold=10):
        """
        说明：
            检测是否黑屏
        """
        screenshot = cv2.cvtColor(self.img.take_screenshot()[
                                  0], cv2.COLOR_BGR2GRAY)
        current_param = cv2.mean(screenshot)[0]
        if current_param < threshold:
            log.info(f'当前黑屏，值为{current_param:.3f} < {threshold}')
            return True

        return False

    def check_blackscreen(self):
        screenshot = self.img.take_screenshot()
        return self.img.is_blackscreen(screenshot)

    def is_blackscreen(self, threshold=10):
        screenshot = cv2.cvtColor(self.img.take_screenshot()[
                                  0], cv2.COLOR_BGR2GRAY)

        if cv2.mean(screenshot)[0] < threshold:  # 如果平均像素值小于阈值
            return True
        else:
            image_folder = "./picture/"
            finish_fighting_images = [f for f in os.listdir(
                image_folder) if f.startswith("finish_fighting")]
            attempts = 0
            max_attempts_ff1 = 3
            while attempts < max_attempts_ff1:
                for image_name in finish_fighting_images:
                    target = cv2.imread(os.path.join(image_folder, image_name))
                    result = self.img.scan_screenshot(target)
                    if result and result["max_val"] > 0.9:
                        log.info(f"匹配到{image_name}，匹配度{result['max_val']:.3f}")
                        return False  # 如果匹配度大于0.9，表示不是黑屏，返回False
                attempts += 1
                time.sleep(2)  # 等待2秒再尝试匹配

        return True  # 如果未匹配到指定的图像，返回True

    def run_blackscreen_cal_time(self):
        """
        说明：
            黑屏时间
        """
        start_time = time.time()
        while self.is_blackscreen():
            time.sleep(1)
        end_time = time.time()  # 记录黑屏加载完成的时间
        loading_time = end_time - start_time + 1

        return loading_time
