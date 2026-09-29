"""`Img` —— 屏幕与识图的统一入口（门面）。

全项目 129 处调用点通过它拿截图、比模板、判断界面。它本身不含实现，
只是把三件事组合起来，让调用方不必同时持有三个对象：

    ScreenSource   drivers/screen.py    抓帧（唯一碰 win32/ImageGrab 的地方）
    images         vision/images.py     模板图加载与缓存
    Matcher        vision/matcher.py    匹配、判定、找到图就点

为什么需要这层门面：调用点横跨 drivers / vision / flows / ui 四层，
而「组合了截图与匹配」的模块按分层规则只能待在 vision 及更上层。
门面把这件事收在一个地方，其余代码继续按老写法调用。

**新增能力时想清楚它属于哪一层**，然后加到对应的子模块、在这里转发一行即可 ——
不要往门面里塞实现，它一长就又变回 502 行的上帝类。
"""

from utils.core.singleton import SingletonMeta
from utils.drivers.screen import ScreenSource
from utils.vision import images
from utils.vision.matcher import Matcher


class Img(metaclass=SingletonMeta):
    """屏幕截图 + 模板匹配的统一入口。

    单例：截图缓冲、图片缓存、窗口引用都是进程级资源，每个模块各持一份没有意义
    （曾有 7 处 `Img()` 各自跑一遍 load_images）。与 Window / MouseEvent /
    Handle / MapInfo / ConfigurationManager 保持一致的单例策略。

    注意：不要再往这里塞「跨模块传递的状态」。曾经的 `search_img_allow_retry`
    就是实例属性，而 Img 当时不是单例，于是 mouse_event 写的标志 map_operations
    永远读不到 —— 功能静默失效、不报错。跨模块状态请放在调用方真正持有的那个
    单例上（例：该标志现在是 MouseEvent.last_search_allow_retry）。
    """

    def __init__(self, image_paths: dict = None, screen=None, mouse=None):
        self.screen = screen or ScreenSource()
        self.window = self.screen.window  # 兼容既有调用点
        self.image_paths = image_paths or images.DEFAULT_IMAGE_PATHS

        #: {名称: ndarray}，同时逐个挂成属性（self.main_ui 等）
        self.ui_images = images.load_all(self.image_paths)
        for name, array in self.ui_images.items():
            setattr(self, name, array)

        self.matcher = Matcher(self.screen, self.ui_images, mouse)

    # ------------------------------------------------------------------
    # 图片资源（静态转发）
    # ------------------------------------------------------------------

    resolve_path = staticmethod(images.resolve_path)
    get_img = staticmethod(images.get_img)

    def load_images(self):
        """重新加载所有图片（文件更新后调用）。"""
        self.ui_images = images.load_all(self.image_paths)
        for name, array in self.ui_images.items():
            setattr(self, name, array)
        self.matcher.ui_images = self.ui_images

    # ------------------------------------------------------------------
    # 截图（转发到 ScreenSource）
    # ------------------------------------------------------------------

    @property
    def temp_screenshot(self):
        return self.screen.temp_screenshot

    @temp_screenshot.setter
    def temp_screenshot(self, value):
        self.screen.temp_screenshot = value

    def cal_screenshot(self):
        return self.screen.cal_screenshot()

    def take_screenshot(self, *args, **kwargs):
        return self.screen.take_screenshot(*args, **kwargs)

    capture_window_background = staticmethod(ScreenSource.capture_window_background)

    # ------------------------------------------------------------------
    # 匹配与判定（转发到 Matcher）
    # ------------------------------------------------------------------

    match_screenshot = staticmethod(Matcher.match_screenshot)
    invert = staticmethod(Matcher.invert)
    img_center_point = staticmethod(Matcher.img_center_point)
    handle_rotate_val = staticmethod(Matcher.handle_rotate_val)

    def have_screenshot(self, *args, **kwargs):
        return self.matcher.have_screenshot(*args, **kwargs)

    def scan_screenshot(self, *args, **kwargs):
        return self.matcher.scan_screenshot(*args, **kwargs)

    def scan_temp_screenshot(self, *args, **kwargs):
        return self.matcher.scan_temp_screenshot(*args, **kwargs)

    def on_main_interface(self, *args, **kwargs):
        return self.matcher.on_main_interface(*args, **kwargs)

    def on_interface(self, *args, **kwargs):
        return self.matcher.on_interface(*args, **kwargs)

    def img_trans_bitwise(self, *args, **kwargs):
        return self.matcher.img_trans_bitwise(*args, **kwargs)

    def img_bitwise_check(self, *args, **kwargs):
        return self.matcher.img_bitwise_check(*args, **kwargs)

    def image_rotate(self, *args, **kwargs):
        return self.matcher.image_rotate(*args, **kwargs)

    # 从 MouseEvent 搬过来的「找到图就点它」一族
    def click_target_above_threshold(self, *args, **kwargs):
        return self.matcher.click_target_above_threshold(*args, **kwargs)

    def click_target(self, *args, **kwargs):
        return self.matcher.click_target(*args, **kwargs)

    @property
    def img_search_val_dict(self):
        return self.matcher.img_search_val_dict
