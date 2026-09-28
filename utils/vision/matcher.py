"""模板匹配与界面判定。

这一层只跟「帧 + 模板 → 匹配结果」打交道，**不自己抓屏**：
帧由注入的 `ScreenSource` 提供。这样检测器可以拿录下来的截图跑测试，
不需要游戏在窗口里（见 CLAUDE.md §1.5）。

`click_target` 一族也在这里：它的本质是「先认图、再点击」，
识别才是主体，输入只是执行动作。把它们从 `MouseEvent` 拆出来之后，
`drivers/` 层才真正只剩设备操作。
"""

import time

import cv2
import numpy as np

from utils.core.log import log
from utils.core.thresholds import DEFAULT_MATCH, LOW_MATCH_REPORT_FLOOR
from utils.drivers.mouse_event import MouseEvent
from utils.drivers.screen import ScreenSource
from utils.vision import images as image_library


class Matcher:
    """模板匹配、界面判定、以及「找到图就点它」。

    :param screen: 截图源；不传则用默认的 `ScreenSource()`
    :param ui_images: {名称: ndarray}，`on_interface` 的默认检测目标从这里取
    :param mouse: 点击执行者；不传则用 `MouseEvent()` 单例
    """

    def __init__(self, screen=None, ui_images=None, mouse=None):
        self.screen = screen or ScreenSource()
        self.ui_images = ui_images or {}
        #: 点击执行者。**惰性构造**：MouseEvent() 会连锁构造 Window()，
        #: 而 Window() 要等游戏窗口出现。识别层必须能在没有游戏的机器上实例化
        #: （黄金图测试的前提），所以只有真的要点击时才去拿它。
        self._mouse = mouse
        # 匹配值低于 LOW_MATCH_REPORT_FLOOR 的图，供报告输出「最相似图片」
        self.img_search_val_dict = {}

    @property
    def mouse(self):
        if self._mouse is None:
            self._mouse = MouseEvent()
        return self._mouse

    # ------------------------------------------------------------------
    # 纯函数：帧 + 模板 -> 结果，不碰任何状态
    # ------------------------------------------------------------------

    @staticmethod
    def match_screenshot(screenshot, prepared, left, top):
        """比对 screenshot 与 prepared，返回匹配值与位置。"""
        result = cv2.matchTemplate(screenshot, prepared, cv2.TM_CCORR_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        return {
            "screenshot": screenshot,
            "min_val": min_val,
            "max_val": max_val,
            "min_loc": (min_loc[0] + left, min_loc[1] + top),
            "max_loc": (max_loc[0] + left, max_loc[1] + top),
        }

    @staticmethod
    def invert(image):
        """颜色反转（取反色）。用于「阴阳变转」那类原图/反色谁更像的判定。"""
        return cv2.bitwise_not(image)

    @staticmethod
    def img_center_point(result, shape) -> tuple:
        """计算匹配到的图片中心位置。"""
        mat_top, mat_left = result["max_loc"]
        prepared_height, prepared_width, prepared_channels = shape
        return (
            int((mat_top + mat_top + prepared_width) / 2),
            int((mat_left + mat_left + prepared_height) / 2),
        )

    @staticmethod
    def handle_rotate_val(x, y, rotate):
        """计算旋转变换矩阵。"""
        cos_val = np.cos(np.deg2rad(rotate))
        sin_val = np.sin(np.deg2rad(rotate))
        return np.float32(
            [
                [cos_val, sin_val, x * (1 - cos_val) - y * sin_val],
                [-sin_val, cos_val, x * sin_val + y * (1 - cos_val)],
            ]
        )

    def image_rotate(self, src, rotate=0):
        """图像旋转（中心旋转）。"""
        h, w, _ = src.shape
        m = self.handle_rotate_val(w // 2, h // 2, rotate)
        return cv2.warpAffine(src, m, (w, h), flags=cv2.INTER_LINEAR)

    # ------------------------------------------------------------------
    # 抓一帧再比对
    # ------------------------------------------------------------------

    def scan_screenshot(self, prepared, offset=(0, 0, 0, 0)) -> dict:
        """抓一帧并与 prepared 比对。"""
        screenshot, left, top, right, bottom = self.screen.take_screenshot(offset=offset)
        return self.match_screenshot(screenshot, prepared, left, top)

    def scan_temp_screenshot(self, prepared) -> dict:
        """用最近一帧比对。

        `temp_screenshot` 未初始化时才补一次抓屏。注意不能写
        `temp_screenshot[0] == 0` —— 真实截图是 numpy 数组，与 0 比较返回
        布尔数组，在 if 中求值会抛 ValueError（issue #433）。
        """
        if not self.screen.has_fresh_frame():
            self.screen.take_screenshot()

        try:
            screenshot, left, top, right, bottom = self.screen.temp_screenshot
        except (TypeError, ValueError) as e:
            raise ValueError(f"temp_screenshot 数据格式错误: {e}") from e
        return self.match_screenshot(screenshot, prepared, left, top)

    def have_screenshot(self, prepared, offset=(0, 0, 0, 0), threshold=DEFAULT_MATCH):
        """prepared 列表里是否有任何一张超过阈值。"""
        for image in prepared:
            max_val = self.scan_screenshot(image, offset)["max_val"]
            if max_val > threshold:
                log.info(f"找到图片，匹配值：{max_val:.3f}")
                return True
            log.debug(f"图片匹配值未达到阈值，当前值：{max_val:.3f}")
        return False

    # ------------------------------------------------------------------
    # 判定
    # ------------------------------------------------------------------

    def on_main_interface(
        self,
        check_list=None,
        timeout=60.0,
        threshold=DEFAULT_MATCH,
        offset=(0, 0, 0, 0),
        allow_log=True,
    ):
        """检测是否在主界面（默认看左上角灯泡）。"""
        if check_list is None:
            check_list = [self.ui_images["main_ui"]]
            offset = (0, 0, -1630, -800)

        return self.on_interface(
            check_list=check_list,
            timeout=timeout,
            interface_desc="游戏主界面，非战斗/传送/黑屏状态",
            threshold=threshold,
            offset=offset,
            allow_log=allow_log,
        )

    def on_interface(
        self,
        check_list=None,
        timeout=60.0,
        interface_desc="",
        threshold=DEFAULT_MATCH,
        offset=(0, 0, 0, 0),
        allow_log=True,
    ):
        """检测 check_list 中的图片是否出现在某个页面。

        :param timeout: 超时时间（秒），超时返回 False
        """
        if check_list is None:
            check_list = [self.ui_images["main_ui"]]

        start_time = time.time()
        temp_max_val = []

        while True:
            for index, img in enumerate(check_list):
                result = self.scan_screenshot(img, offset=offset)
                if result["max_val"] > threshold:
                    if allow_log:
                        log.info(
                            f"检测到{interface_desc}，耗时 {(time.time() - start_time):.1f} 秒"
                        )
                        log.info(
                            f"检测图片序号为{index}，匹配度{result['max_val']:.3f}，匹配位置为{result['max_loc']}"
                        )
                    return True
                temp_max_val.append(result["max_val"])
                time.sleep(0.2)

            if time.time() - start_time >= timeout:
                if allow_log:
                    log.info(
                        f"在 {timeout} 秒 的时间内未检测到{interface_desc}，相似图片最高匹配值{max(temp_max_val):.3f}"
                    )
                return False

    def img_trans_bitwise(self, target_path, offset=(0, 0, 0, 0)):
        """颜色反转后比对。"""
        original_target = image_library.get_img(target_path)
        inverted_target = cv2.bitwise_not(original_target)
        return inverted_target, self.scan_screenshot(inverted_target, offset)

    def img_bitwise_check(self, target_path: str, offset: tuple = (0, 0, 0, 0)):
        """比较原图与反色图谁匹配得更好，返回「原图是否更匹配」。"""
        retry = 0
        while retry < 5:
            original_target = image_library.get_img(target_path)
            target, result_inverted = self.img_trans_bitwise(target_path, offset)
            result_original = self.scan_screenshot(original_target, offset)
            log.info(
                f"颜色反转后的匹配值：{result_inverted['max_val']:.3f}，反转前匹配值：{result_original['max_val']:.3f}"
            )
            if (
                round(result_original["max_val"], 3) == 0.0
                or round(result_inverted["max_val"], 3) == 0.0
            ):
                retry += 1
                time.sleep(0.5)
            else:
                break
        else:
            log.info("超过重试次数，强制认为原图正确")
            return True

        return result_original["max_val"] > result_inverted["max_val"]

    # ------------------------------------------------------------------
    # 找到图就点它
    # ------------------------------------------------------------------

    def click_target_above_threshold(
        self, target, threshold, offset, clicks=1, delay=0.05, click_offset=(0, 0)
    ):
        """匹配度超过阈值就点击，返回 (是否点击, 匹配值)。

        :param click_offset: 落点相对**匹配中心**的平移 (dx, dy)。给「可识别的静态
            部分与可点热区不重合」的按钮用（地图 JSON 的 `click_offset` 修饰键）。
        """
        result = self.scan_screenshot(target, offset)
        if result["max_val"] > threshold:
            points = self.img_center_point(result, target.shape)
            if click_offset != (0, 0):
                log.debug(f"落点加偏移 {click_offset}")
                points = (points[0] + click_offset[0], points[1] + click_offset[1])
            self.mouse.click(points, result["max_val"], clicks, delay)
            return True, result["max_val"]
        return False, result["max_val"]

    def click_target(
        self,
        target_path,
        threshold,
        flag=True,
        timeout=30.0,
        offset=(0, 0, 0, 0),
        retry_in_map: bool = True,
        clicks=1,
        delay=0.05,
        click_offset=(0, 0),
    ):
        """点击指定图片。

        :param flag: True 表示一定要找到（会一直重试到 timeout）
        :param retry_in_map: 超时时是否允许调用方重试整张地图；
            写入 `self.last_search_allow_retry` 供 `flows/map_operations` 读取
        :param click_offset: 落点相对匹配中心的平移 (dx, dy)，见 click_target_above_threshold
        :return: 是否点击成功
        """
        original_target = image_library.get_img(target_path)
        if original_target is None:
            log.error(f"图片不存在: {target_path}")
            return False
        inverted_target = cv2.bitwise_not(original_target)
        start_time = time.time()

        while time.time() - start_time < timeout:
            click_it, img_search_val = self.click_target_above_threshold(
                original_target, threshold, offset, clicks, delay, click_offset
            )
            if click_it:
                return True
            if time.time() - start_time > 1:
                # 超过 1 秒仍未命中，同时试颜色反转图
                click_it, _ = self.click_target_above_threshold(
                    inverted_target, threshold, offset, clicks, delay, click_offset
                )
                if click_it:
                    log.info("阴阳变转")
                    return True

            # 持续记录最低匹配值，供报告输出「最相似图片」参考
            if img_search_val < LOW_MATCH_REPORT_FLOOR:
                recorded = self.img_search_val_dict.get(target_path)
                if recorded is None or img_search_val < recorded:
                    self.img_search_val_dict[target_path] = img_search_val

            if not flag:
                return False
            time.sleep(0.5)

        log.info(
            f"查找图片超时 {target_path} ，最相似图片匹配值 {img_search_val}，所需匹配值 {threshold}"
        )
        # 只有超时这一条路径会写入：提前返回（flag=False）与图片缺失都不算「可重试的失败」。
        # 标志放在 MouseEvent 上而不是这里：读取方是 flows/map_operations，
        # 它持有的是 self.mouse_event，跨模块状态必须放在读取方真正拿得到的对象上
        # （这正是当初 img.search_img_allow_retry 静默失效的原因，见 CLAUDE.md R13）。
        self.mouse.last_search_allow_retry = retry_in_map
        return False
