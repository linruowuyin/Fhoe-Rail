import datetime
import time

import cv2 as cv
import pyautogui

from utils.blackscreen import BlackScreen
from utils.calculated import Calculated
from utils.config import ConfigurationManager
from utils.handle import Handle
from utils.img import Img
from utils.log import log, webhook_and_log
from utils.map_info import MapInfo
from utils.monthly_pass import MonthlyPass
from utils.mouse_event import MouseEvent
from utils.time_utils import TimeUtils


class Map:
    def __init__(self):
        self.calculated = Calculated()
        self.cfg = ConfigurationManager()
        self.time_mgr = TimeUtils()
        self.img = Img()
        self.monthly_pass = MonthlyPass()
        self.mouse_event = MouseEvent()
        self.handle = Handle()
        self.blackscreen = BlackScreen()

        self.open_map_btn = "m"
        self.map_list = MapInfo.read_maps(
            self.cfg.config_file.get("map_version", "default"))[0]
        self.map_list_map = MapInfo.read_maps(
            self.cfg.config_file.get("map_version", "default"))[1]
        self.map_version = MapInfo.read_maps(
            self.cfg.config_file.get("map_version", "default"))[2]
        self.now = datetime.datetime.now()
        self.retry_cnt_max = 2
        self.map_statu_minimize = False  # 地图最小化
        self.planet = None  # 当前星球初始化
        self.planet_png_lst = ["picture\\orientation_2.png", "picture\\orientation_3.png",
                               "picture\\orientation_4.png", "picture\\orientation_5.png", "picture\\orientation_6.png"]

    def open_map(self):
        """
        尝试打开地图并识别地图标志性的目标图片
        """
        target = cv.imread('./picture/contraction.png')
        target_back = cv.imread('./picture/map_back.png')
        start_time = time.time()
        attempts = 0
        speed_open = False
        max_attempts = 10

        # 主逻辑
        while attempts < max_attempts:
            log.info(f'尝试打开地图 (尝试次数: {attempts + 1}/{max_attempts})')
            pyautogui.press(self.open_map_btn)
            time.sleep(0.05)
            self._wait_for_main_interface(speed_open, start_time)
            speed_open = True
            if self._handle_target_recognition(target):
                self._handle_back_button(target_back)
                break
            else:
                attempts += 1
                self.handle.back_to_main()  # 确保返回主界面以重试

    def find_transfer_point(self, key, threshold=0.99, min_threshold=0.93, timeout=60, offset=None):
        """
        说明:
            寻找传送点
        参数：
            :param key: 图片地址
            :param threshold: 图片查找阈值
            :param min_threshold: 最低图片查找阈值
            :param timeout: 超时时间（秒）
            :param offset: 查找偏移，None 时使用默认移动逻辑
        """
        start_time = time.time()
        target = cv.imread(key)

        while time.time() - start_time < timeout:
            if self._is_target_found(target, threshold):
                log.info(f"传送点已找到，匹配度：{threshold:.2f}")
                return

            if offset is None:
                self._move_default(target, threshold)
            else:
                self._move_with_offset(offset)

            threshold = max(min_threshold, threshold - 0.01)

        log.error("传送点查找失败：超时或未达到最低阈值")

    def _directions(self):
        directions = {
            "down": (250, 900, 250, 300),
            "left": (250, 900, 850, 900),
            "up": (1330, 200, 1330, 800),
            "right": (1330, 200, 730, 200),
        }
        return directions

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
                if not self._is_target_found(target, threshold):
                    self.mouse_event.mouse_drag(*direction_coords)
                else:
                    return

    def _move_with_offset(self, offset):
        """
        按偏移量移动地图。
        """
        for _ in range(offset[0]):  # 向左+向上
            self.mouse_event.mouse_drag(*self._directions()["left"])
            self.mouse_event.mouse_drag(*self._directions()["up"])
        for _ in range(offset[1]):  # 向右
            self.mouse_event.mouse_drag(*self._directions()["right"])
        for _ in range(offset[2]):  # 向下
            self.mouse_event.mouse_drag(*self._directions()["down"])

    def find_scene(self, key, threshold=0.99, min_threshold=0.93, timeout=60):
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
        target = cv.imread(key)
        inverted_target = cv.bitwise_not(target)
        target_list = [target, inverted_target]
        direction_names = ["向下移动", "向上移动"]
        while not self.img.have_screenshot(target_list, (0, 0, 0, 0), threshold) and time.time() - start_time < timeout and threshold >= min_threshold:
            # 设置向下、向上的移动数值
            directions = [(1700, 900, 1700, 300), (1700, 300, 1700, 900)]
            for index, direction in enumerate(directions):
                log.info(
                    f"开始移动右侧场景，{direction_names[index]}，当前所需匹配值{threshold}")
                for i in range(1):
                    if not self.img.have_screenshot(target_list, (0, 0, 0, 0), threshold):
                        self.mouse_event.mouse_drag(*direction)
                    else:
                        return
            threshold -= 0.02

    def get_map_list(self, start, start_in_mid: bool = False) -> list:
        """
        获取地图列表
        """
        start_index = self.map_list.index(f'map_{start}.json')
        if start_in_mid:
            mid_slice = self.map_list[start_index:]
            map_list = mid_slice + self.map_list[:start_index]
        else:
            map_list = self.map_list[start_index:]

        return map_list

    def reset_round_count(self):
        """
        重置该锄地轮次相关的计数
        """
        self.handle.total_fight_time = 0
        self.handle.tatol_save_time = 0
        self.handle.total_fight_cnt = 0
        self.handle.total_no_fight_cnt = 0
        self.handle.auto_final_fight_e_cnt = 0

    def allow_map_drag(self, start):
        self.allow_drap_map_switch = bool(start.get("drag", False))  # 默认禁止拖动地图
        self.drag_exact = None

        if self.allow_drap_map_switch and "drag_exact" in start:
            self.drag_exact = start["drag_exact"]

    def allow_scene_drag(self, start):
        self.allow_scene_drag_switch = bool(
            start.get("scene", False))  # 默认禁止拖动右侧场景

    def allow_multi_click(self, start):
        self.multi_click = 1
        self.allow_multi_click_switch = bool(
            start.get("clicks", False))  # 默认禁止多次点击
        if self.allow_multi_click_switch:
            self.multi_click = int(start["clicks"])

    def allow_retry_in_map(self, start):
        self.allow_retry_in_map_switch = not bool(
            start.get("forbid_retry", False))  # 默认允许自动重试查找地图点位

    def check_and_skip_forbidden_maps(self, map_data_name):
        """检查并跳过配置中禁止的地图。

        Args:
            map_data_name (str): 当前处理的地图的名称。

        Returns:
            bool: 如果地图在禁止列表中，则返回 True，否则返回 False。
        """
        self.forbid_map = self.cfg.config_file.get('forbid_map', [])
        if not all(isinstance(item, str) for item in self.forbid_map):
            log.info("配置错误：'forbid_map' 应只包含字符串。")
            return False

        map_data_first_name = map_data_name.split('-')[0]
        if map_data_first_name in self.forbid_map:
            log.info(f"地图 {map_data_name} 在禁止列表中，将跳过此地图。")
            return True

        return False

    def check_planet(self, planet):
        if self.planet == planet:
            log.info(f"星球相同，跳过选择星球 {planet}")
        return self.planet == planet

    def align_angle(self):
        """校准视角
        """
        if not self.cfg.config_file.get("angle_set", False) or self.cfg.config_file.get("angle", "1.0") == "1.0":
            self.monthly_pass.monthly_pass_check()  # 月卡检查
            self.handle.back_to_main()
            time.sleep(1)
            self.calculated.set_angle()

    def handle_orientation(self, key, map_data):
        """
        已在当前星球，跳过点击星轨航图
        未在当前星球，点击星轨航图后进行黑屏检测，如果因为客户端黑屏，则返回重试点击星轨航图
        """
        keys_to_find = self.planet_png_lst
        planet_dict = {k: v for item in map_data['start']
                       for k, v in item.items() if k in keys_to_find}
        planet = list(planet_dict.keys())[0]
        if self.check_planet(planet):
            return
        else:
            orientation_delay = 2
            while True:
                self.mouse_event.click_target(
                    key, 0.97, retry_in_map=self.allow_retry_in_map_switch)
                orientation_delay = min(orientation_delay, 4)
                time.sleep(orientation_delay)
                if self.blackscreen.check_blackscreen():
                    pyautogui.press('esc')
                    time.sleep(2)
                    orientation_delay += 0.5
                else:
                    return

    def handle_planet(self, key):
        """点击星球
        """
        if self.check_planet(key):
            return
        else:
            self.find_transfer_point(key, threshold=0.975)
            if self.mouse_event.click_target(key, 0.93, delay=0.1):
                time.sleep(5)
                img = cv.imread("./picture/kaituoli_1.png")
                delay_time = 0.5
                while not self.img.on_interface(check_list=[img], timeout=1, interface_desc='星轨航图', threshold=0.97, offset=(1580, 0, 0, -910), allow_log=False):
                    if self.blackscreen.check_blackscreen():
                        self.planet = key
                        break
                    delay_time += 0.1
                    delay_time = max(delay_time, 1)
                    log.info(f"检测到未成功点击星球，尝试重试点击星球，鼠标点击间隔时间 {delay_time}")
                    self.mouse_event.click_target(key, 0.93, delay=delay_time)
                    time.sleep(5)
                else:
                    self.planet = key
            time.sleep(1.7)

    def handle_floor(self, key):
        """点击楼层
        """
        if self.img.img_bitwise_check(target_path=key, offset=(30, 740, -1820, -70)):
            self.mouse_event.click_target(
                key, 0.93, offset=(30, 740, -1820, -70))
        else:
            log.info("已在对应楼层，跳过选择楼层")

    def handle_back(self, key):
        """点击右上角返回
        """
        img = cv.imread("./picture/kaituoli_1.png")
        if not self.img.on_interface(check_list=[img], timeout=1, interface_desc='星轨航图', threshold=0.97, offset=(1580, 0, 0, -910), allow_log=False):
            self.mouse_event.click_target(key, 0.94, timeout=3, offset=(
                1660, 100, -40, -910), retry_in_map=False)
        else:
            log.info("检测到星轨航图，不进行点击'返回'")

    def _handle_back_button(self, target_back):
        """
        处理返回按钮的识别和点击逻辑，用于偶现的卡二级地图，此时使用m键无法关闭地图
        """
        for _ in range(5):
            result_back = self.img.scan_screenshot(
                target_back, offset=(1830, 0, 0, -975))
            if result_back['max_val'] > 0.99:
                log.info("找到返回键")
                points_back = self.img.img_center_point(
                    result_back, target_back.shape)
                pyautogui.click(points_back, clicks=1, interval=0.1)
            else:
                break

    def _wait_for_main_interface(self, speed_open, start_time):
        """
        黄泉e的状态下快速打开地图，采用按下s打断技能并且按下地图键的方式
        """
        while self.img.on_main_interface(timeout=0.0, allow_log=False):
            if time.time() - start_time > 3:
                return
            if not speed_open:
                log.info("按下s打断技能")
                pyautogui.keyDown('s')
                pyautogui.press(self.open_map_btn)
                time.sleep(0.05)
        pyautogui.keyUp('s')
        return

    def _handle_target_recognition(self, target):
        """
        处理目标图片的识别逻辑
        """
        time.sleep(3)  # 增加识别延迟，避免偶现的识别错误
        result = self.img.scan_screenshot(
            target, offset=(530, 960, -1050, -50))
        if result['max_val'] > 0.97:
            points = self.img.img_center_point(result, target.shape)
            log.info(f"识别点位{points}，匹配度{result['max_val']:.3f}")
            if not self.map_statu_minimize:
                log.info(f"地图最小化，识别图片匹配度{result['max_val']:.3f}")
                pyautogui.click(points, clicks=10, interval=0.1)
                self.map_statu_minimize = True
            return True
        return False

    def auto_map(self, start, start_in_mid: bool = False, dev: bool = False):
        total_processing_time = 0
        teleport_click_count = 0
        error_check_point = False  # 初始化筑梦机关检查为通过
        today_weekday_str = self.now.strftime('%A')
        self.align_angle()
        if f'map_{start}.json' in self.map_list:
            total_start_time = time.time()
            self.reset_round_count()  # 重置该锄地轮次相关的计数
            # map_list = self.map_list[self.map_list.index(f'map_{start}.json'):len(self.map_list)]
            map_list = self.get_map_list(start, start_in_mid)
            max_index = max(index for index, _ in enumerate(map_list))
            next_map_drag = False  # 初始化下一张图拖动为否
            start_map_name, end_map_name = None, None
            for index, map_json in enumerate(map_list):
                map_base = map_json.split('.')[0]
                map_data = self.cfg.read_json_file(
                    f"map/{self.map_version}/{map_base}.json")
                map_data_name = map_data['name']
                map_data_author = map_data['author']
                # 检查是否应该跳过这张地图
                if self.check_and_skip_forbidden_maps(map_data_name):
                    continue
                self.map_drag = next_map_drag
                next_map_drag = False

                retry = True
                retry_cnt = 0
                while retry and retry_cnt < self.retry_cnt_max:
                    retry = False
                    # 选择地图
                    start_time = time.time()
                    start_map_name, end_map_name = (
                        map_data_name if index == 0 else start_map_name, map_data_name if index == max_index else end_map_name)
                    webhook_and_log(f"\033[0;96;40m{map_data_name}\033[0m")
                    self.monthly_pass.monthly_pass_check()  # 月卡检查
                    log.info(
                        f"路线领航员：\033[1;95m{map_data_author}\033[0m 感谢她(们)的无私奉献，准备开始路线：{map_base}")
                    jump_this_map = False  # 跳过这张地图，一般用于过期邮包购买
                    self.temp_point = ""  # 用于输出传送前的点位
                    normal_run = False  # 初始化跑步模式为默认
                    for start in map_data['start']:
                        key = list(start.keys())[0]
                        log.info(key)
                        value = start[key]
                        self.img.search_img_allow_retry = False
                        self.allow_map_drag(start)  # 是否强制允许拖动地图初始化
                        self.allow_scene_drag(start)  # 是否强制允许拖动右侧场景初始化
                        self.allow_multi_click(start)  # 多次点击
                        self.allow_retry_in_map(start)  # 是否允许重试
                        if key == "check":  # 判断周几
                            if value == 1:
                                value = [0, 1, 2, 3, 4, 5, 6]
                            # 1代表周二，4代表周五，6代表周日
                            if self.time_mgr.day_init(value):
                                log.info(f"今天{today_weekday_str}，尝试购买")
                                jump_this_map = False
                                continue
                            else:
                                log.info(f"今天{today_weekday_str}，跳过")
                                jump_this_map = True
                                break
                        elif key == "need_allow_map_buy":
                            jump_this_map = not self.cfg.read_json_file(
                                self.cfg.CONFIG_FILE_NAME, False).get('allow_map_buy', False)
                            if jump_this_map:
                                log.info(
                                    f" config.json 中的 allow_map_buy 为 False ，跳过该图{map_data['name']}，如果需要开启购买请改为 True 并且【自行确保】能够正常购买对应物品")
                                break
                        elif key == "need_allow_snack_buy":
                            jump_this_map = not self.cfg.read_json_file(
                                self.cfg.CONFIG_FILE_NAME, False).get('allow_snack_buy', False)
                            if jump_this_map:
                                log.info(
                                    f" config.json 中的 allow_snack_buy 为 False ，跳过该图{map_data['name']}，如果需要开启购买请改为 True 并且【自行确保】能够正常购买对应物品")
                                break
                        elif key == "need_allow_memory_token":
                            jump_this_map = not self.cfg.read_json_file(
                                self.cfg.CONFIG_FILE_NAME, False).get('allow_memory_token', False)
                            if jump_this_map:
                                log.info(
                                    f" config.json 中的 allow_memory_token 为 False ，跳过该图{map_data['name']}，如果需要开启请改为 True 并且【自行确保】能够正常获得对应物品")
                                break
                        elif key == "normal_run":
                            normal_run = True  # 此地图json将会被强制设定为禁止疾跑
                        elif key == "blackscreen":
                            self.calculated.run_mapload_check()  # 强制执行地图加载检测
                        elif key == "esc":
                            pyautogui.press('esc')
                        elif key == 'map':
                            self.open_map()
                        elif key == 'main':
                            self.handle.back_to_main()  # 检测并回到主界面
                            time.sleep(2)
                        elif key == 'b':
                            pyautogui.press('b')
                            time.sleep(1)
                        elif key == 'await':
                            time.sleep(abs(value))
                        elif key == "space":
                            pyautogui.press('space')
                        elif key in ["w", "a", "s", "d"]:
                            self.handle.handle_move(value, key)
                        elif key in ["F4"]:
                            pyautogui.press(key)
                        elif key == "f":
                            self.handle.handle_f(value)
                        elif key == "picture\\max.png":
                            if self.calculated.allow_buy_item():
                                jump_this_map = False
                                self.mouse_event.click_target(key, 0.93)
                                continue
                            else:
                                jump_this_map = True
                                break
                        elif key in ["picture\\transfer.png"]:
                            time.sleep(0.2)
                            if not self.mouse_event.click_target(key, 0.93):
                                jump_this_map = True
                                break
                            self.calculated.run_mapload_check()
                            if self.temp_point:
                                log.info(f'地图加载前的传送点为 {self.temp_point}')
                        else:
                            value = min(value, 0.8)
                            time.sleep(value)
                            if key in ["picture\\1floor.png", "picture\\2floor.png", "picture\\3floor.png"]:
                                self.handle_floor(key)
                            # 有可能未找到该图片，冗余查找
                            elif key in ["picture\\fanhui_1.png", "picture\\fanhui_2.png"]:
                                self.handle_back(key)
                            elif key.startswith("picture\\check_4-1_point"):
                                self.find_transfer_point(key, threshold=0.992)
                                if self.mouse_event.click_target(key, 0.992, retry_in_map=False):
                                    log.info("筑梦机关检查通过")
                                else:
                                    log.info("筑梦机关检查不通过，请将机关调整到正确的位置上")
                                    error_check_point = True
                                time.sleep(1)
                            elif key == "picture\\map_4-1_point_2.png":  # 筑梦边境尝试性修复
                                self.find_transfer_point(key, threshold=0.975)
                                self.mouse_event.click_target(key, 0.95)
                                self.temp_point = key
                            elif key == "picture\\orientation_1.png":
                                self.handle_orientation(key, map_data)
                            elif key.startswith("picture\\map_4-3_point"):
                                self.find_transfer_point(key, threshold=0.975)
                                self.mouse_event.click_target(key, 0.93)
                                self.temp_point = key
                                time.sleep(1.7)
                            elif key in self.planet_png_lst:
                                self.handle_planet(key)
                            else:
                                if self.allow_drap_map_switch or self.map_drag:
                                    self.find_transfer_point(
                                        key, threshold=0.975, offset=self.drag_exact)
                                if self.allow_scene_drag_switch:
                                    self.find_scene(key, threshold=0.990)
                                if self.img.on_main_interface(timeout=0.5, allow_log=False):
                                    log.info("执行alt")
                                    self.mouse_event.click_target_with_alt(
                                        key, 0.93, clicks=self.multi_click)
                                else:
                                    self.mouse_event.click_target(
                                        key, 0.93, clicks=self.multi_click, retry_in_map=self.allow_retry_in_map_switch)
                                self.temp_point = key
                            teleport_click_count += 1
                            log.info(f'传送点击（{teleport_click_count}）')
                            if self.img.search_img_allow_retry:
                                retry = True
                                retry_cnt += 1
                                if retry_cnt == self.retry_cnt_max:
                                    jump_this_map = True
                                    next_map_drag = True
                                break

                teleport_click_count = 0  # 在每次地图循环结束后重置计数器

                # 'check'过期邮包/传送识别失败/无法购买 时 跳过，执行下一张图
                if jump_this_map:
                    continue

                # 记录处理开始时间
                start_time = time.time()

                self.calculated.auto_map(
                    map_base, normal_run, dev=dev, last_point=self.temp_point)

                # 记录处理结束时间
                end_time = time.time()

                # 计算处理时间并输出
                processing_time = end_time - start_time
                formatted_time = self.time_mgr.format_time(processing_time)
                total_processing_time += processing_time
                log.info(
                    f"{map_base}用时\033[1;92m『{formatted_time}』\033[0m,总计:\033[1;92m『{self.time_mgr.format_time(total_processing_time)}』\033[0m")

                if index == max_index:
                    total_time = time.time() - total_start_time
                    total_fight_time = self.handle.total_fight_time
                    log.info(
                        f"结束该阶段的锄地，总计用时 {self.time_mgr.format_time(total_time)}，总计战斗用时 {self.time_mgr.format_time(total_fight_time)}")
                    error_fight_cnt = self.handle.error_fight_cnt
                    log.info(
                        f"异常战斗识别（战斗时间 < {self.handle.error_fight_threshold} 秒）次数：{error_fight_cnt}")
                    if error_check_point:
                        log.info("筑梦机关检查不通过，请将机关调整到正确的位置上")
                    log.info(
                        f"疾跑节约的时间为 {self.time_mgr.format_time(self.handle.tatol_save_time)}")
                    log.info(f"战斗次数{self.handle.total_fight_cnt}")
                    log.info(f"未战斗次数{self.handle.total_no_fight_cnt}")
                    log.info(
                        "未战斗次数在非黄泉地图首次锄地参考值：70-80，不作为漏怪标准，漏怪具体请在背包中对材料进行溯源查找")
                    log.info(f"系统卡顿次数：{self.handle.time_error_cnt}")
                    log.debug(
                        f"匹配值小于0.99的图片：{self.mouse_event.img_search_val_dict}")
                    log.info(f"开始地图：{start_map_name}，结束地图：{end_map_name}")

        else:
            log.info(f'地图编号 {start} 不存在，请尝试检查地图文件')
