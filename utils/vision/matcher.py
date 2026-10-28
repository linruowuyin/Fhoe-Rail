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
from utils.vision import assets
from utils.vision import images as image_library
from utils.vision import samples


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
    def shape_features(image):
        """把图转成梯度幅值图：只保留轮廓，抹掉底色。

        给「图标固定、底色随游戏内模糊背景变化」的模板用（`assets.MATCH_SHAPE`）：
        高斯模糊的背景几乎没有梯度，图标的边缘则很明显，因此匹配结果与背景颜色无关。
        用 `TM_CCOEFF_NORMED`（会减均值）比 `TM_CCORR_NORMED` 更能把两个亮色图标区分开。

        固定缩放成 uint8（`/4`，Sobel ksize=3 的理论上限附近截断）而不是按图归一化：
        浮点图在平坦区域会出数值异常，uint8 下纯色帧得分为 0，不会冒假高分。
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(grad_x, grad_y)
        return np.clip(magnitude / 4.0, 0, 255).astype(np.uint8)

    @staticmethod
    def _prepare_match(screenshot, prepared, strategy=None):
        """按匹配策略返回 `(帧, 模板, matchTemplate 方法)`。

        :param strategy: 显式指定策略（探针要同时跑多种；解谜弹窗固定用
            `MATCH_COLOR_CCOEFF`）；None 表示按模板登记的策略。
        """
        if strategy is None:
            strategy = image_library.strategy_of(prepared)
        if strategy == assets.MATCH_SHAPE:
            return (
                Matcher.shape_features(screenshot),
                Matcher.shape_features(prepared),
                cv2.TM_CCOEFF_NORMED,
            )
        if strategy == assets.MATCH_COLOR_CCOEFF:
            # 不转梯度：原图直接减均值相关。对话框的整块亮度会变，CCORR 在
            # 「擦掉文字」的负样本上仍有 0.92，CCOEFF 只有 0.24。
            return screenshot, prepared, cv2.TM_CCOEFF_NORMED
        return screenshot, prepared, cv2.TM_CCORR_NORMED

    @staticmethod
    def match_screenshot(screenshot, prepared, left, top, strategy=None):
        """比对 screenshot 与 prepared，返回匹配值与位置。

        这里是**全部匹配的唯一汇聚点**，所以图片样本收集也挂在这一处（见
        `vision/samples.py`）—— 挂在各调用点等于抄十几遍。

        匹配策略跟着模板走：`assets.MATCH_SHAPE` 的模板先转成梯度幅值再比，
        `assets.MATCH_COLOR_CCOEFF` 用原图 CCOEFF；其余用 CCORR。样本收集仍用
        原始帧/模板，落下来的样本是真实画面。
        """
        match_frame, match_template, method = Matcher._prepare_match(
            screenshot, prepared, strategy
        )
        result = cv2.matchTemplate(match_frame, match_template, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        Matcher._collect_sample(screenshot, prepared, left, top, max_val, max_loc)
        return {
            "screenshot": screenshot,
            "min_val": min_val,
            "max_val": max_val,
            "min_loc": (min_loc[0] + left, min_loc[1] + top),
            "max_loc": (max_loc[0] + left, max_loc[1] + top),
        }

    @staticmethod
    def _collect_sample(screenshot, prepared, left, top, max_val, max_loc):
        """开发者模式：把这次匹配喂给样本收集器。

        路径靠**对象身份**反查（`images.path_of`）—— 这里只拿得到 ndarray。
        反色 / 旋转造出来的新数组查不到，那几次就不落样本（不影响「未使用」口径，
        那条走的是 `images.get_img` 的加载钩子）。
        """
        if not samples.enabled():
            return
        height, width = prepared.shape[:2]
        box_left, box_top = max_loc[0] + left, max_loc[1] + top
        samples.note_match(
            image_library.path_of(prepared),
            screenshot,
            (left, top, left + screenshot.shape[1], top + screenshot.shape[0]),
            (box_left, box_top, box_left + width, box_top + height),
            max_val,
        )

    @staticmethod
    def match_peaks(screenshot, prepared, left=0, top=0, strategy=None):
        """一次匹配，同时给出最优峰与**次优峰**。

        次优峰 = 屏蔽掉最优峰周围一个模板大小的邻域（即所有与最优位置有像素重叠的
        候选位置）后剩下的最高匹配值。它回答的是「这张模板在这一帧里唯一吗」：
        最优 0.97 而次优也 0.96，说明帧里到处都长得像它，阈值定得再高也会指到错的
        位置 —— 这是标定阈值时比最优值更该看的一个数（CLAUDE.md §1.2 的负样本余量）。

        :param strategy: 显式指定匹配策略（探针会同时跑 color 与 shape）；
            None 表示按模板登记的策略（`images.strategy_of`）。
        :return: {"max_val", "max_loc"(已加 left/top), "second_val"}
                 模板与帧一样大（只有一个候选位置）时 `second_val` 为 0.0
        """
        match_frame, match_template, method = Matcher._prepare_match(
            screenshot, prepared, strategy
        )
        result = cv2.matchTemplate(match_frame, match_template, method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        height, width = prepared.shape[:2]
        suppressed = result.copy()
        y0 = max(0, max_loc[1] - height + 1)
        y1 = min(result.shape[0], max_loc[1] + height)
        x0 = max(0, max_loc[0] - width + 1)
        x1 = min(result.shape[1], max_loc[0] + width)
        suppressed[y0:y1, x0:x1] = -1.0

        if (suppressed == -1.0).all():
            second_val = 0.0
        else:
            second_val = cv2.minMaxLoc(suppressed)[1]

        return {
            "max_val": max_val,
            "max_loc": (max_loc[0] + left, max_loc[1] + top),
            "second_val": second_val,
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
            # 主界面灯泡固定在左上角；区域与探针/其它调用点同一份（R25）
            offset = assets.search_offset("finish_fighting")

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
        # 轮廓识别的模板不跑「阴阳变转」：梯度幅值对颜色取反不变
        # （Sobel 是线性的，取反后幅值相同），再跑一遍反色图是空转；
        # 而反色数组查不回路径、会退回颜色匹配 —— 那等于绕开轮廓判定，
        # 在 0.85 这种低阈值下可能凭颜色点中错误位置。
        strategy = image_library.strategy_of(original_target)
        inverted_target = cv2.bitwise_not(original_target)
        start_time = time.time()

        while time.time() - start_time < timeout:
            click_it, img_search_val = self.click_target_above_threshold(
                original_target, threshold, offset, clicks, delay, click_offset
            )
            if click_it:
                return True
            if time.time() - start_time > 1 and strategy != assets.MATCH_SHAPE:
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
