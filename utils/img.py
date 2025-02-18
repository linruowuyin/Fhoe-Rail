import time

import cv2
import numpy as np
from PIL import ImageGrab

from utils.log import log
from utils.window import Window


class Img:
    def __init__(self, image_paths: dict = None):
        self.window = Window()
        self.temp_screenshot = (0, 0, 0, 0, 0)  # 初始化临时截图
        self.search_img_allow_retry = False  # 初始化查找图片允许重试为不允许

        if image_paths is None:
            self.image_paths = {
                "main_ui": "./picture/finish_fighting.png",
                "doubt_ui": "./picture/doubt.png",
                "warn_ui": "./picture/warn.png",
                "finish2_ui": "./picture/finish_fighting2.png",
                "finish2_1_ui": "./picture/finish_fighting2_1.png",
                "finish2_2_ui": "./picture/finish_fighting2_2.png",
                "finish3_ui": "./picture/finish_fighting3.png",
                "finish4_ui": "./picture/finish_fighting4.png",
                "finish5_ui": "./picture/finish_fighting5.png",
                "battle_esc_check": "./picture/battle_esc_check.png",
                "switch_run": "./picture/switch_run.png",
            }
        else:
            self.image_paths = image_paths

        # 加载所有图片
        self.load_images()

    @staticmethod
    def get_img(img_path):
        """
        获取图片
        :param img_path: 图片路径
        :return: 图片数据（numpy 数组），如果加载失败返回 None
        """
        try:
            img = cv2.imread(img_path)
            if img is None:
                raise FileNotFoundError(f"图片加载失败，路径不存在或文件损坏: {img_path}")
            return img
        except Exception as e:
            log.error(f"加载图片时发生错误: {e}")
            return None

    def load_images(self):
        """加载所有图片"""
        for name, path in self.image_paths.items():
            img = self.get_img(path)
            if img is not None:
                setattr(self, name, img)
            else:
                log.warning(f"警告: 图片 {name} 加载失败，路径为 {path}")

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

    def on_main_interface(self, check_list=None, timeout=60.0, threshold=0.9, offset=(0, 0, 0, 0), allow_log=True):
        """
        说明：
            检测主页面
        参数：
            :param check_list:检测图片列表，默认检测左上角地图的灯泡，遍历检测
            :param timeout:超时时间（秒），超时后返回False
            :param threshold:识别阈值，默认0.9
        返回：
            是否在主界面
        """
        if check_list is None:
            check_list = [self.main_ui]
            offset = (0, 0, -1630, -800)
        interface_desc = '游戏主界面，非战斗/传送/黑屏状态'

        return self.on_interface(check_list=check_list, timeout=timeout, interface_desc=interface_desc, threshold=threshold, offset=offset, allow_log=allow_log)

    def on_interface(self, check_list=None, timeout=60.0, interface_desc='', threshold=0.9, offset=(0, 0, 0, 0), allow_log=True):
        """
        说明：
            检测check_list中的图片是否在某个页面
        参数：
            :param check_list:检测图片列表，默认为检测[self.main_ui]主界面左上角灯泡
            :param timeout:超时时间（秒），超时后返回False
            :param interface_desc:界面名称或说明，用于日志输出
        返回：
            是否在check_list存在的界面
        """
        if check_list is None:
            check_list = [self.main_ui]

        start_time = time.time()
        temp_max_val = []

        while True:
            for index, img in enumerate(check_list):
                result = self.scan_screenshot(img, offset=offset)
                if result["max_val"] > threshold:
                    if allow_log:
                        log.info(
                            f"检测到{interface_desc}，耗时 {(time.time() - start_time):.1f} 秒")
                        log.info(
                            f"检测图片序号为{index}，匹配度{result['max_val']:.3f}，匹配位置为{result['max_loc']}")
                    return True
                else:
                    temp_max_val.append(result['max_val'])
                    time.sleep(0.2)

            if time.time() - start_time >= timeout:
                if allow_log:
                    log.info(
                        f"在 {timeout} 秒 的时间内未检测到{interface_desc}，相似图片最高匹配值{max(temp_max_val):.3f}")
                return False

    def image_rotate(self, src, rotate=0):
        """
        图像旋转（中心旋转）
        参数：
            :param src: 源图像
            :param rotate: 旋转角度
        """
        h, w, _ = src.shape
        m = self.handle_rotate_val(w // 2, h // 2, rotate)
        # M = cv2.getRotationMatrix2D((w // 2, h // 2), rotate, 1.0)
        img = cv2.warpAffine(src, m, (w, h), flags=cv2.INTER_LINEAR)
        return img

    def handle_rotate_val(self, x, y, rotate):
        """
        计算旋转变换矩阵
        """
        cos_val = np.cos(np.deg2rad(rotate))
        sin_val = np.sin(np.deg2rad(rotate))
        return np.float32(
            [
                [cos_val, sin_val, x * (1 - cos_val) - y * sin_val],
                [-sin_val, cos_val, x * sin_val + y * (1 - cos_val)],
            ]
        )
