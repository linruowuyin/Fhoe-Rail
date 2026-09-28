import time


from utils.vision.blackscreen import BlackScreen
from utils.config.config import ConfigurationManager
from utils.flows.handle import Handle
from utils.drivers.keyboard_event import KeyboardEvent
from utils.vision.img import Img
from utils.core.map_info import MapInfo
from utils.flows.monthly_pass import MonthlyPass
from utils.drivers.mouse_event import MouseEvent
from utils.core.map_move import MAP_MOVE_NAV_DATA
from utils.core.log import log
from utils.core.thresholds import (
    BACK_BUTTON,
    FLOOR_BUTTON,
    MAP_BACK,
    MAP_OPEN,
    ORIENTATION_ICON,
    PLANET,
    PLANET_CLICK,
    SCENE_MIN,
    SCENE_SEARCH,
    STAR_MAP,
    TRANSFER_POINT_MIN,
    TRANSFER_POINT_SEARCH,
)


class Map:
    def __init__(self):
        self.cfg = ConfigurationManager()
        self.img = Img()
        self.monthly_pass = MonthlyPass()
        self.mouse_event = MouseEvent()
        self.handle = Handle()
        self.blackscreen = BlackScreen()
        self.map_info = MapInfo()
        self.open_map_btn = "m"

        # 暂停闸门：由 MapOperations 在跑图前接上 Pause.wait_if_paused。默认 no-op，
        # 这样 Map 在测试里仍能独立构造，也不向 ui/ 产生依赖边（传的是函数对象）。
        # 返回值是「被暂停的秒数」，带墙钟死线的循环要把它加回 start_time。
        self.pause_gate = lambda: 0.0

        # 点击偏移：匹配到锚点后把落点整体平移 (dx, dy)。给「可识别的静态部分与
        # 可点热区不重合」的按钮用，由地图 JSON 的 `click_offset` 修饰键逐条声明。
        self.click_offset = (0, 0)

        self.allowlist_mode = False
        self.map_statu_minimize = False  # 地图最小化
        self.planet = None  # 当前星球初始化
        self.planet_png_lst = [
            "picture\\orientation_2.png",
            "picture\\orientation_3.png",
            "picture\\orientation_4.png",
            "picture\\orientation_5.png",
            "picture\\orientation_6.png",
            "picture\\orientation_7.png",
        ]

    def open_map(self):
        """
        尝试打开地图并识别地图标志性的目标图片
        """
        target = Img.get_img("./picture/contraction.png")
        target_back = Img.get_img("./picture/map_back.png")
        start_time = time.time()
        attempts = 0
        speed_open = False
        max_attempts = 10

        # 主逻辑
        while attempts < max_attempts:
            # start_time 还要给 _wait_for_main_interface 判断 3 秒窗口，所以一并补偿
            start_time += self.pause_gate()
            log.info(f"尝试打开地图 (尝试次数: {attempts + 1}/{max_attempts})")
            KeyboardEvent.keyboard_press(self.open_map_btn)
            time.sleep(0.05)
            self._wait_for_main_interface(speed_open, start_time)
            speed_open = True
            if self._handle_target_recognition(target):
                self._handle_back_button(target_back)
                break
            else:
                attempts += 1
                self.handle.back_to_main()  # 确保返回主界面以重试

    def find_transfer_point(
        self,
        key,
        threshold=TRANSFER_POINT_SEARCH,
        min_threshold=TRANSFER_POINT_MIN,
        timeout=60,
        exact=None,
        offset=None,
    ):
        """
        说明:
            寻找传送点
        参数：
            :param key: 图片地址
            :param threshold: 图片查找阈值
            :param min_threshold: 最低图片查找阈值
            :param timeout: 超时时间（秒）
            :param exact: 精确查找，None 时使用默认移动逻辑
            :param offset: 查找偏移，None 时使用默认移动逻辑
        """
        start_time = time.time()
        target = Img.get_img(key)

        while time.time() - start_time < timeout:
            # 暂停的时间必须从死线里扣掉，否则一暂停就会误判「超时」而放弃这次查找
            start_time += self.pause_gate()
            if self._is_target_found(target, threshold):
                log.info(f"传送点已找到，匹配度：{threshold:.2f}")
                return

            if offset is not None:
                self._move_with_offset(offset)
                offset = None

            if exact is None:
                self._move_default(target, threshold)
            else:
                self._move_with_exact(exact)

            threshold = max(min_threshold, threshold - 0.01)

        log.error("传送点查找失败：超时或未达到最低阈值")

    def _directions(self):
        """
        获取地图移动方向的坐标。
        """
        return MAP_MOVE_NAV_DATA["16:9"]["directions"]

    def _is_target_found(self, target, threshold):
        """
        判断目标是否找到。
        """
        return self.img.have_screenshot([target], (0, 0, 0, 0), threshold)

    def _move_default(self, target, threshold):
        """
        按默认逻辑移动地图。
        """
        for direction_name, direction_coords in self._directions().items():
            log.info(f"尝试 {direction_name} ，当前阈值：{threshold:.2f}")
            for _ in range(3):
                self.pause_gate()
                if not self._is_target_found(target, threshold):
                    self.mouse_event.mouse_drag(*direction_coords)
                else:
                    return

    def _move_with_offset(self, offset):
        """
        按偏移量移动地图。
        """
        log.info("开始按照设置相对移动地图")
        for _ in range(offset[0]):  # 向左
            self.pause_gate()
            log.info("地图左移")
            self.mouse_event.mouse_drag(*self._directions()["left"])
        for _ in range(offset[1]):  # 向上
            self.pause_gate()
            log.info("地图上移")
            self.mouse_event.mouse_drag(*self._directions()["up"])
        for _ in range(offset[2]):  # 向右
            self.pause_gate()
            log.info("地图右移")
            self.mouse_event.mouse_drag(*self._directions()["right"])
        for _ in range(offset[3]):  # 向下
            self.pause_gate()
            log.info("地图下移")
            self.mouse_event.mouse_drag(*self._directions()["down"])

    def _move_with_exact(self, exact):
        """
        按精确移动逻辑移动地图。
        """
        log.info("开始按照设置精确移动地图，先定位到地图左上角后移动到目标位置")
        for _ in range(exact[0]):  # 向左+向上
            self.pause_gate()
            log.info("地图左上移")
            self.mouse_event.mouse_drag(*self._directions()["up_left"])
        for _ in range(exact[1]):  # 向右
            self.pause_gate()
            log.info("地图右移")
            self.mouse_event.mouse_drag(*self._directions()["right"])
        for _ in range(exact[2]):  # 向下
            self.pause_gate()
            log.info("地图下移")
            self.mouse_event.mouse_drag(*self._directions()["down"])

    def find_scene(self, key, threshold=SCENE_SEARCH, min_threshold=SCENE_MIN, timeout=60):
        """
        说明:
            寻找场景
        参数：
            :param key:图片地址
            :param threshold:图片查找阈值
            :param min_threshold:最低图片查找阈值
            :param timeout:超时时间（秒）
        """
        start_time = time.time()
        target = Img.get_img(key)
        inverted_target = Img.invert(target)
        target_list = [target, inverted_target]
        direction_names = ["向下移动", "向上移动"]
        while (
            not self.img.have_screenshot(target_list, (0, 0, 0, 0), threshold)
            and time.time() - start_time < timeout
            and threshold >= min_threshold
        ):
            # 暂停的时间必须从死线里扣掉，否则一暂停就会误判「超时」而放弃这次查找
            start_time += self.pause_gate()
            # 设置向下、向上的移动数值
            directions = [(1700, 900, 1700, 300), (1700, 300, 1700, 900)]
            for index, direction in enumerate(directions):
                log.info(
                    f"开始移动右侧场景，{direction_names[index]}，当前所需匹配值{threshold}"
                )
                for _ in range(3):
                    # 闸门放最内层而不是外层 while：这里一轮「匹配 + 1 秒拖拽」约 2.5 秒，
                    # 放外层要等完两个方向 × 3 次拖拽（约十几秒）才响应按键
                    self.pause_gate()
                    if not self.img.have_screenshot(
                        target_list, (0, 0, 0, 0), threshold
                    ):
                        self.mouse_event.mouse_drag(*direction, press_time=1)
                    else:
                        return
            threshold -= 0.02

    def get_map_list(self, start, start_in_mid: bool = False) -> list:
        """
        获取地图列表
        """
        start_index = self.map_info.map_list.index(f"map_{start}.json")
        if start_in_mid:
            mid_slice = self.map_info.map_list[start_index:]
            map_list = mid_slice + self.map_info.map_list[:start_index]
        else:
            map_list = self.map_info.map_list[start_index:]

        return map_list

    def reset_round_count(self):
        """
        重置该锄地轮次相关的计数
        """
        self.handle.combat.reset()
        self.handle.movement.tatol_save_time = 0

    def allow_map_drag(self, start):
        self.allow_drap_map_switch = bool(start.get("drag", False))  # 默认禁止拖动地图
        self.drag_exact = None
        self.drag_offset = None

        if self.allow_drap_map_switch and "drag_exact" in start:
            self.drag_exact = start["drag_exact"]
        if self.allow_drap_map_switch and "drag_offset" in start:  # 允许先相对移动地图
            self.drag_offset = start["drag_offset"]

    def allow_scene_drag(self, start):
        self.allow_scene_drag_switch = bool(
            start.get("scene", False)
        )  # 默认禁止拖动右侧场景

    def allow_multi_click(self, start):
        self.multi_click = 1
        self.allow_multi_click_switch = bool(
            start.get("clicks", False)
        )  # 默认禁止多次点击
        if self.allow_multi_click_switch:
            self.multi_click = int(start["clicks"])

    def allow_retry_in_map(self, start):
        self.allow_retry_in_map_switch = not bool(
            start.get("forbid_retry", False)
        )  # 默认允许自动重试查找地图点位

    def allow_click_offset(self, start):
        """点击偏移修饰键：`{"picture\\x.png": 1.5, "click_offset": [60, 0]}`

        修饰键必须写在步骤键之后（`core/schema.py` 会拦顺序错）。
        没声明时复位，避免上一条步骤的偏移带到下一条。

        **目前消费它的是 `handle_planet`（星球节点）** —— 别的图片步骤声明了也不会生效，
        要用在别处，在对应 handler 的 `click_target(...)` 上传 `click_offset=self.click_offset`。
        """
        click_offset = start.get("click_offset")
        self.click_offset = tuple(click_offset) if click_offset else (0, 0)

    def check_allowlist_maps(self, map_data_name):
        """检查并跳过非白名单地图"""
        if self.cfg.config_file.get("allowlist_mode_once", False):
            self.allowlist_mode = True
            self.cfg.modify_json_file(
                self.cfg.CONFIG_FILE_NAME, "allowlist_mode_once", False
            )
        if self.cfg.config_file.get("allowlist_mode", False):
            self.allowlist_mode = True
        if self.allowlist_mode:
            map_data_first_name = map_data_name.split("-")[0]
            if map_data_first_name not in self.cfg.config_file.get("allowlist_map", []):
                log.info(f"地图 {map_data_name} 不在白名单中，将跳过此地图。")
                return True
        return False

    def check_forbidden_maps(self, map_data_name):
        """检查是否应该跳过这张地图。

        Args:
            map_data_name (str): 当前处理的地图的名称。

        Returns:
            bool: 如果地图在禁止列表中，则返回 True，否则返回 False。
        """
        self.forbid_map = self.cfg.config_file.get("forbid_map", [])
        if not all(isinstance(item, str) for item in self.forbid_map):
            log.info("配置错误：'forbid_map' 应只包含字符串。")
            return False

        map_data_first_name = map_data_name.split("-")[0]
        if map_data_first_name in self.forbid_map:
            log.info(f"地图 {map_data_name} 在禁止列表中，将跳过此地图。")
            return True

        return False

    def check_planet(self, planet):
        if self.planet == planet:
            log.info(f"星球相同，跳过选择星球 {planet}")
        return self.planet == planet

    def align_angle(self):
        """校准视角"""
        if (
            not self.cfg.config_file.get("angle_set", False)
            or self.cfg.config_file.get("angle", "1.0") == "1.0"
        ):
            self.monthly_pass.monthly_pass_check()  # 月卡检查
            self.handle.back_to_main()
            time.sleep(1)
            self.handle.set_angle()

    def handle_orientation(self, key, map_data):
        """
        已在当前星球，跳过点击星轨航图
        未在当前星球，点击星轨航图后进行黑屏检测，如果因为客户端黑屏，则返回重试点击星轨航图
        """
        keys_to_find = self.planet_png_lst
        planet_dict = {
            k: v
            for item in map_data["start"]
            for k, v in item.items()
            if k in keys_to_find
        }
        planet = list(planet_dict.keys())[0]
        if self.check_planet(planet):
            return
        else:
            orientation_delay = 2
            while True:
                # 这个循环没有硬上限（只有黑屏消失才退），卡住时最需要能停
                self.pause_gate()
                self.img.click_target(
                    key, ORIENTATION_ICON, retry_in_map=self.allow_retry_in_map_switch
                )
                orientation_delay = min(orientation_delay, 4)
                time.sleep(orientation_delay)
                if self.blackscreen.check_blackscreen():
                    KeyboardEvent.keyboard_press("esc")
                    time.sleep(2)
                    orientation_delay += 0.5
                else:
                    return

    def handle_planet(self, key):
        """点击星球"""
        if self.check_planet(key):
            return
        else:
            self.find_transfer_point(
                key, threshold=PLANET, offset=self.drag_offset, exact=self.drag_exact
            )
            if self.img.click_target(
                key, PLANET_CLICK, delay=0.1, click_offset=self.click_offset
            ):
                time.sleep(5)
                img = Img.get_img("./picture/kaituoli_1.png")
                delay_time = 0.5
                while not self.img.on_interface(
                    check_list=[img],
                    timeout=1,
                    interface_desc="星轨航图",
                    threshold=STAR_MAP,
                    offset=(1580, 0, 0, -910),
                    allow_log=False,
                ):
                    # 这个循环也没有硬上限（只有星轨航图出现或黑屏才退）
                    self.pause_gate()
                    if self.blackscreen.check_blackscreen():
                        self.planet = key
                        break
                    delay_time += 0.1
                    delay_time = max(delay_time, 1)
                    log.info(
                        f"检测到未成功点击星球，尝试重试点击星球，鼠标点击间隔时间 {delay_time}"
                    )
                    self.img.click_target(
                        key, PLANET_CLICK, delay=delay_time, click_offset=self.click_offset
                    )
                    time.sleep(5)
                else:
                    self.planet = key
            time.sleep(1.7)

    def handle_floor(self, key):
        """点击楼层"""
        if self.img.img_bitwise_check(target_path=key, offset=(30, 740, -1820, -70)):
            self.img.click_target(key, FLOOR_BUTTON, offset=(30, 740, -1820, -70))
        else:
            log.info("已在对应楼层，跳过选择楼层")

    def handle_back(self, key):
        """点击右上角返回"""
        img = Img.get_img("./picture/kaituoli_1.png")
        if not self.img.on_interface(
            check_list=[img],
            timeout=1,
            interface_desc="星轨航图",
            threshold=STAR_MAP,
            offset=(1580, 0, 0, -910),
            allow_log=False,
        ):
            self.img.click_target(
                key, BACK_BUTTON, timeout=3, offset=(1660, 100, -40, -910), retry_in_map=False
            )
        else:
            log.info("检测到星轨航图，不进行点击'返回'")

    def _handle_back_button(self, target_back):
        """
        处理返回按钮的识别和点击逻辑，用于偶现的卡二级地图，此时使用m键无法关闭地图
        """
        for _ in range(5):
            self.pause_gate()
            result_back = self.img.scan_screenshot(
                target_back, offset=(1830, 0, 0, -975)
            )
            if result_back["max_val"] > MAP_BACK:
                log.info("找到返回键")
                points_back = self.img.img_center_point(result_back, target_back.shape)
                self.mouse_event.click(points_back)
            else:
                break

    def _wait_for_main_interface(self, speed_open, start_time):
        """
        黄泉e的状态下快速打开地图，采用按下s打断技能并且按下地图键的方式
        """
        try:
            while self.img.on_main_interface(timeout=0.0, allow_log=False):
                start_time += self.pause_gate()
                if time.time() - start_time > 3:
                    return
                if not speed_open:
                    log.info("按下s打断技能")
                    KeyboardEvent.press_key("s")
                    KeyboardEvent.keyboard_press(self.open_map_btn)
                    time.sleep(0.05)
        finally:
            KeyboardEvent.release_key("s")
        return

    def _handle_target_recognition(self, target):
        """
        处理目标图片的识别逻辑
        """
        time.sleep(3)  # 增加识别延迟，避免偶现的识别错误
        result = self.img.scan_screenshot(target, offset=(530, 960, -1050, -50))
        if result["max_val"] > MAP_OPEN:
            points = self.img.img_center_point(result, target.shape)
            log.info(f"识别点位{points}，匹配度{result['max_val']:.3f}")
            if not self.map_statu_minimize:
                log.info(f"地图最小化，识别图片匹配度{result['max_val']:.3f}")
                self.mouse_event.click(points, clicks=10)
                self.map_statu_minimize = True
            return True
        return False
