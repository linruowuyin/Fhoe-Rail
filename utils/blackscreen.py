import os
import time

import cv2

from utils.img import Img
from utils.log import log


class BlackScreen:
    def __init__(self):
        self.img = Img()
        self.image_folder = "./picture/"

    @staticmethod
    def convert_to_grayscale(screenshot):
        """将截图转换为灰度图像"""
        return cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def calculate_mean_pixel_value(grayscale_image):
        """计算灰度图像的灰度均值"""
        return cv2.mean(grayscale_image)[0]

    def check_blackscreen(self, threshold=10):
        """通过阈值判断是否为黑屏"""
        screenshot = self.img.take_screenshot()[0]
        grayscale_image = self.convert_to_grayscale(screenshot)
        mean_pixel_value = self.calculate_mean_pixel_value(grayscale_image)

        if mean_pixel_value < threshold:
            log.info(f'当前黑屏，值为{mean_pixel_value:.3f} < {threshold}')
            return True
        return False

    def load_finish_fighting_images(self):
        """加载所有以 'finish_fighting' 开头的图像"""
        return [f for f in os.listdir(self.image_folder) if f.startswith("finish_fighting")]

    def match_finish_fighting_images(self, finish_fighting_images, max_attempts=3):
        """尝试匹配 'finish_fighting' 图像"""
        attempts = 0
        while attempts < max_attempts:
            for image_name in finish_fighting_images:
                target = cv2.imread(os.path.join(self.image_folder, image_name))
                result = self.img.scan_screenshot(target)
                if result and result["max_val"] > 0.9:
                    log.info(f"匹配到{image_name}，匹配度{result['max_val']:.3f}")
                    return False  # 如果匹配度大于0.9，表示不是黑屏，返回False
            attempts += 1
            time.sleep(2)  # 等待2秒再尝试匹配
        return True  # 如果未匹配到指定的图像，返回True

    def check_exit_blackscreen(self, threshold=10):
        """判断是否脱离黑屏状态"""
        if self.check_blackscreen(threshold):
            return True
        else:
            finish_fighting_images = self.load_finish_fighting_images()
            return self.match_finish_fighting_images(finish_fighting_images)

    def run_blackscreen_cal_time(self):
        """计算黑屏时间"""
        start_time = time.time()
        while self.check_exit_blackscreen():
            time.sleep(1)
        end_time = time.time()  # 记录黑屏加载完成的时间
        loading_time = end_time - start_time + 1

        return loading_time
