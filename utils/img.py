import time

import cv2
import numpy as np
from PIL import ImageGrab

from utils.log import log
from utils.window import Window


class Img:
    def __init__(self):
        self.window = Window()
        self.temp_screenshot = (0, 0, 0, 0, 0)  # 初始化临时截图
        self.search_img_allow_retry = False  # 初始化查找图片允许重试为不允许

    @staticmethod
    def get_img(img_path):
        """
        获取图片
        """
        return cv2.imread(img_path)

    def cal_screenshot(self):
        """
        计算窗口截图范围
        """
        left, top, right, bottom = self.window.get_rect()
        # 计算初始边框
        width = right - left
        height = bottom - top
        other_border = (width - 1920) // 2
        up_border = height - 1080 - other_border
        # 计算窗口截图范围
        screenshot_left = left + other_border
        screenshot_top = top + up_border
        screenshot_right = right - other_border
        screenshot_bottom = bottom - other_border

        return screenshot_left, screenshot_top, screenshot_right, screenshot_bottom

    @staticmethod
    def match_screenshot(screenshot, prepared, left, top):
        """
        说明：
            比对screenshot与prepared，返回匹配值与位置
        参数：
            :param screenshot:屏幕截图图片
            :param prepared:比对图片
            :param left:截图左侧坐标，用于计算真实位置
            :param top:截图上方坐标，用于计算真实位置
        """
        result = cv2.matchTemplate(screenshot, prepared, cv2.TM_CCORR_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        return {
            "screenshot": screenshot,
            "min_val": min_val,
            "max_val": max_val,
            "min_loc": (min_loc[0] + left, min_loc[1] + top),
            "max_loc": (max_loc[0] + left, max_loc[1] + top),
        }

    def have_screenshot(self, prepared, offset=(0, 0, 0, 0), threshold=0.90):
        """
        验证屏幕截图中是否存在预设的图片之一。

        参数:
            prepared (list): 需要匹配的图片列表。
            offset (tuple): 在搜索时屏幕截图的偏移量，默认为 (0, 0, 0, 0)。
            threshold (float): 确定匹配成功的最小阈值，默认为 0.90。

        返回:
            bool: 如果找到至少一张符合阈值的图片，则返回 True，否则返回 False。
        """
        for image in prepared:
            result_dict = self.scan_screenshot(image, offset)
            max_val = result_dict['max_val']
            if max_val > threshold:
                log.info(f'找到图片，匹配值：{max_val:.3f}')
                return True
            else:
                log.debug(f'图片匹配值未达到阈值，当前值：{max_val:.3f}')
        return False

    def take_screenshot(self, offset=(0, 0, 0, 0), max_retries=50, retry_interval=2):
        """
        说明：
            获取游戏窗口的屏幕截图
        参数：
            :param window: 窗口对象
            :param offset: 左、上、右、下，正值为向右或向下偏移
            :param max_retries: 最大重试次数
            :param retry_interval: 重试间隔（秒）
        """
        if self.window.check_window_visibility():
            screenshot_left, screenshot_top, screenshot_right, screenshot_bottom = self.cal_screenshot()

            # 计算偏移截图范围
            new_left = screenshot_left + offset[0]
            new_top = screenshot_top + offset[1]
            new_right = screenshot_right + offset[2]
            new_bottom = screenshot_bottom + offset[3]
            # 偏移有效则使用偏移值
            if all([new_left < new_right, new_top < new_bottom]):
                screenshot_left, screenshot_top, screenshot_right, screenshot_bottom = new_left, new_top, new_right, new_bottom
            else:
                log.info(
                    f'截图区域无效，偏移值错误({offset[0]},{offset[1]},{offset[2]},{offset[3]})，将使用窗口截图')

            retries = 0
            while retries <= max_retries:
                try:
                    picture = ImageGrab.grab(
                        (screenshot_left, screenshot_top, screenshot_right, screenshot_bottom), all_screens=True)
                    # 保存截图到本地，测试用
                    # picture.save("test.png")
                    screenshot = np.array(picture)
                    screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
                    self.temp_screenshot = (
                        screenshot, screenshot_left, screenshot_top, screenshot_right, screenshot_bottom)
                    return screenshot, screenshot_left, screenshot_top, screenshot_right, screenshot_bottom
                except Exception as e:
                    log.info(f"截图失败，原因: {str(e)}，等待 {retry_interval} 秒后重试")
                    retries += 1
                    time.sleep(retry_interval)
            raise RuntimeError(f"截图尝试失败，已达到最大重试次数 {max_retries} 次）")

    def scan_screenshot(self, prepared, offset=(0, 0, 0, 0)) -> dict:
        """
        说明：
            比对图片
        参数：
            :param prepared: 比对图片地址
            :param offset: 左、上、右、下，正值为向右或向下偏移
        """
        screenshot, left, top, right, bottom = self.take_screenshot(
            offset=offset)

        return Img.match_screenshot(screenshot, prepared, left, top)

    def scan_temp_screenshot(self, prepared):
        """
        说明：
            使用临时截图数据进行扫描匹配
        参数：
            :param prepared: 比对图片地址
        """
        if not self.temp_screenshot:
            self.take_screenshot()

        try:
            screenshot, left, top, right, bottom = self.temp_screenshot
        except (TypeError, ValueError) as e:
            raise ValueError(f"self.temp_screenshot 数据格式错误: {e}") from e
        return Img.match_screenshot(screenshot, prepared, left, top)

    @staticmethod
    def img_center_point(result, shape) -> tuple:
        """
        计算匹配到的图片中心位置
        """
        mat_top, mat_left = result["max_loc"]
        prepared_height, prepared_width, prepared_channels = shape

        x = int((mat_top + mat_top + prepared_width) / 2)
        y = int((mat_left + mat_left + prepared_height) / 2)

        return x, y

    def img_trans_bitwise(self, target_path, offset=(0, 0, 0, 0)):
        """
        颜色反转
        """
        original_target = cv2.imread(target_path)
        inverted_target = cv2.bitwise_not(original_target)
        result = self.scan_screenshot(inverted_target, offset)
        return inverted_target, result

    def img_bitwise_check(self, target_path: str, offset: tuple = (0, 0, 0, 0)):
        """
        比对颜色反转
        """
        retry = 0
        while retry < 5:
            original_target = cv2.imread(target_path)
            target,  result_inverted = self.img_trans_bitwise(
                target_path, offset)
            result_original = self.scan_screenshot(original_target, offset)
            log.info(
                f"颜色反转后的匹配值：{result_inverted['max_val']:.3f}，反转前匹配值：{result_original['max_val']:.3f}")
            if round(result_original['max_val'], 3) == 0.0 or round(result_inverted['max_val'], 3) == 0.0:
                retry += 1
                time.sleep(0.5)
            else:
                break
        else:
            log.info("超过重试次数，强制认为原图正确")
            return True

        if result_original["max_val"] > result_inverted["max_val"]:
            return True
        else:
            return False
