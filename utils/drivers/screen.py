"""屏幕截图 —— 唯一直接调用 PrintWindow / ImageGrab 的地方。

这一层只负责「把窗口像素取出来」，不做任何识别。取出来的帧统一是
**BGR 顺序的 ndarray**（与 `cv2.imread` 的约定一致，模板匹配才能对得上）。

刻意不 import cv2：通道序用 numpy 切片完成，这样 drivers 层不必为了
一次颜色转换而依赖图像库。
"""

import time

import numpy as np
from PIL import Image, ImageGrab
import win32con
import win32gui
import win32ui

from utils.core.log import log
from utils.drivers.window import Window

#: 截图基准分辨率。窗口不是这个尺寸时 `cal_screenshot` 会算出超界区域，
#: 见 CLAUDE.md R8（目前只警告不拒绝运行）。
BASE_WIDTH = 1920
BASE_HEIGHT = 1080


class ScreenSource:
    """游戏窗口的截图源。

    持有 `temp_screenshot`：最近一帧及其坐标。`scan_temp_screenshot` 依赖它
    复用同一帧，避免一次判定里反复抓屏。
    """

    def __init__(self, window=None):
        self.window = window or Window()
        self.temp_screenshot = (0, 0, 0, 0, 0)  # (帧, left, top, right, bottom)

    def cal_screenshot(self):
        """
        计算窗口截图范围：按 1920x1080 基准裁掉两侧黑边/标题栏。

        窗口小于基准分辨率时会算出一个比窗口还大的区域（不会报错），
        由调用方承担后果。
        """
        left, top, right, bottom = self.window.get_rect()
        width = right - left
        height = bottom - top
        other_border = (width - BASE_WIDTH) // 2
        up_border = height - BASE_HEIGHT - other_border

        return (
            left + other_border,
            top + up_border,
            right - other_border,
            bottom - other_border,
        )

    @staticmethod
    def capture_window_background(hwnd, region, crop_region=None):
        """
        后台截取指定窗口客户区，尽量避免被其他窗口遮挡影响。

        :return: PIL 图像（RGB 序），失败返回 None
        """
        left, top, width, height = region

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)

        try:
            win32gui.SendMessage(hwnd, win32con.WM_PAINT, 0, 0)
            import ctypes

            # 3: 强制渲染 + 仅客户区
            result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
            if result != 1:
                return None

            bmp_info = save_bitmap.GetInfo()
            bmp_str = save_bitmap.GetBitmapBits(True)
            picture = Image.frombuffer(
                "RGB",
                (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                bmp_str,
                "raw",
                "BGRX",
                0,
                1,
            )

            if crop_region is not None:
                crop_left, crop_top, crop_right, crop_bottom = crop_region
                rel_left = max(0, crop_left - left)
                rel_top = max(0, crop_top - top)
                rel_right = min(width, crop_right - left)
                rel_bottom = min(height, crop_bottom - top)
                if rel_left >= rel_right or rel_top >= rel_bottom:
                    return None
                picture = picture.crop((rel_left, rel_top, rel_right, rel_bottom))

            return picture
        finally:
            win32gui.DeleteObject(save_bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

    def take_screenshot(self, offset=(0, 0, 0, 0), max_retries=50, retry_interval=2):
        """
        获取游戏窗口的屏幕截图。

        :param offset: 左、上、右、下，正值为向右或向下偏移
        :param max_retries: 最大重试次数
        :param retry_interval: 重试间隔（秒）
        :return: (帧, left, top, right, bottom)，帧为 BGR ndarray
        """
        if self.window.check_window_visibility():
            base_left, base_top, base_right, base_bottom = self.cal_screenshot()
            screenshot_left, screenshot_top, screenshot_right, screenshot_bottom = (
                base_left,
                base_top,
                base_right,
                base_bottom,
            )

            # 计算偏移截图范围
            new_left = screenshot_left + offset[0]
            new_top = screenshot_top + offset[1]
            new_right = screenshot_right + offset[2]
            new_bottom = screenshot_bottom + offset[3]
            if all([new_left < new_right, new_top < new_bottom]):
                screenshot_left, screenshot_top, screenshot_right, screenshot_bottom = (
                    new_left,
                    new_top,
                    new_right,
                    new_bottom,
                )
            else:
                log.info(
                    f"截图区域无效，偏移值错误({offset[0]},{offset[1]},{offset[2]},{offset[3]})，将使用窗口截图"
                )

            retries = 0
            while retries <= max_retries:
                picture = None
                try:
                    # 优先后台截图，失败后再回退到前台截图
                    base_width = base_right - base_left
                    base_height = base_bottom - base_top
                    if self.window.hwnd and base_width > 0 and base_height > 0:
                        picture = self.capture_window_background(
                            self.window.hwnd,
                            (base_left, base_top, base_width, base_height),
                            (
                                screenshot_left,
                                screenshot_top,
                                screenshot_right,
                                screenshot_bottom,
                            ),
                        )
                        if picture is None:
                            log.debug("后台截图失败，回退到前台截图")

                    if picture is None:
                        picture = ImageGrab.grab(
                            (
                                screenshot_left,
                                screenshot_top,
                                screenshot_right,
                                screenshot_bottom,
                            ),
                            all_screens=True,
                        )

                    # PIL 给的是 RGB 序；统一翻成 BGR，与 cv2.imread 的约定一致，
                    # 否则模板匹配会拿反通道的图去比。
                    # 用切片而不是 cv2.cvtColor：drivers 层不依赖图像库。
                    screenshot = np.array(picture)[:, :, ::-1].copy()
                    self.temp_screenshot = (
                        screenshot,
                        screenshot_left,
                        screenshot_top,
                        screenshot_right,
                        screenshot_bottom,
                    )
                    return self.temp_screenshot
                except Exception as e:
                    log.info(f"截图失败，原因: {str(e)}，等待 {retry_interval} 秒后重试")
                    retries += 1
                    time.sleep(retry_interval)
            raise RuntimeError(f"截图尝试失败，已达到最大重试次数 {max_retries} 次）")

    def has_fresh_frame(self) -> bool:
        """`temp_screenshot` 里是否已经有一帧真实截图。"""
        shot = self.temp_screenshot
        return (
            isinstance(shot, tuple)
            and len(shot) == 5
            and isinstance(shot[0], np.ndarray)
        )
