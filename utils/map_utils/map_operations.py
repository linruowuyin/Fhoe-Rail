"""
地图处理主逻辑
"""
import datetime
import time

import pyautogui

from utils.calculated import Calculated
from utils.config.config import ConfigurationManager
from utils.config.text_window import show_text, start_tkinter_thread, TEXT_WINDOWS
from utils.handle import Handle
from utils.img import Img
from utils.log import log
from utils.log import webhook_and_log
from utils.map_utils.map import Map
from utils.map_utils.map_info import MapInfo
from utils.map_utils.map_statu import MapStatu
from utils.monthly_pass import MonthlyPass
from utils.mouse_event import MouseEvent
from utils.pause import Pause
from utils.time_utils import TimeUtils
from utils.window import Window
from utils.report import Report


class MapOperations:
    """
    地图处理主逻辑
    """

    def __init__(self):
        self.map = Map()
        self.map_info = MapInfo()
        self.cfg = ConfigurationManager()
        self.time_mgr = TimeUtils()
        self.map_statu = MapStatu()
        self.handle = Handle()
        self.mouse_event = MouseEvent()
        self.img = Img()
        self.window = Window()
        self.calculated = Calculated()
        self.monthly_pass = MonthlyPass()
        self.report = Report(self.map_statu, self.map_info,
                             self.handle, self.mouse_event, self.time_mgr)

        self.now = datetime.datetime.now()

        self.retry_cnt_max = 2  # 初始化最高重试次数

        # 初始化TextWindow实例
        start_tkinter_thread("map_name")
        time.sleep(0.1)
        start_tkinter_thread("key_value")
        time.sleep(0.1)
        start_tkinter_thread("map_key_value")
        time.sleep(0.1)

        # 等待所有窗口准备就绪
        for window_id in ["map_name", "key_value", "map_key_value"]:
            if window_id in TEXT_WINDOWS:
                TEXT_WINDOWS[window_id].ready.wait()
            else:
                raise RuntimeError(f"Failed to initialize {window_id} window")

    def process_map(self, start, start_in_mid: bool = False, dev: bool = False):
        """
        处理地图
        """
        self.map_statu.total_processing_time = 0
        self.map_statu.teleport_click_count = 0
        self.map_statu.error_check_point = False  # 初始化筑梦机关检查为通过
        self.map.align_angle()
        if f'map_{start}.json' in self.map_info.map_list:
            total_start_time = time.time()
            self.map.reset_round_count()  # 重置该锄地轮次相关的计数
            # map_list = self.map_list[self.map_list.index(f'map_{start}.json'):len(self.map_list)]
            map_list = self.map.get_map_list(start, start_in_mid)
            max_index = max(index for index, _ in enumerate(map_list))
            self.map_statu.next_map_drag = False  # 初始化下一张图拖动为否

            for index, map_json in enumerate(map_list):
                self.process_single_map(index, map_json, dev)
                if self.map_statu.skip_this_map:
                    continue

            # 计算总时间与总战斗时间
            self.map_statu.total_time = time.time() - total_start_time
            self.map_statu.total_fight_time = self.handle.total_fight_time

            # 输出报告
            self.report.output_report()
        else:
            log.info(f'地图编号 {start} 不存在，请尝试检查地图文件')

    def process_single_map(self, index, map_json, dev: bool = False):
        """
        处理单张地图
        """
        start_time = time.time()

        self.show_dev_info(dev, map_json, 180, 1045, "map_name")

        # 初始化地图内意外战斗为未发生
        self.handle.fight_in_map = False

        self.process_single_map_start(index, map_json, dev)

        self.map_statu.teleport_click_count = 0  # 在每次地图循环结束后重置计数器

        # 'check'过期邮包/传送识别失败/无法购买 时 跳过，执行下一张图
        if self.map_statu.skip_this_map:
            return

        self.process_single_map_handle(
            map_json, self.map_statu.normal_run, dev=dev, last_point=self.map_statu.temp_point)
        end_time = time.time()
        # 计算处理时间并输出
        processing_time = end_time - start_time
        formatted_time = self.time_mgr.format_time(processing_time)
        self.map_statu.total_processing_time += processing_time
        log.info(
            f"{map_json}用时\033[1;92m『{formatted_time}』\033[0m,总计:\033[1;92m『{self.time_mgr.format_time(self.map_statu.total_processing_time)}』\033[0m")

    def process_single_map_start(self, index, map_json, dev: bool = False):
        """
        处理单张地图的开始
        """
        map_base = map_json.split('.')[0]
        map_data = self.cfg.read_json_file(
            f"map/{self.map_info.map_version}/{map_base}.json")
        map_data_name = map_data['name']
        map_data_author = map_data['author']
        # 白名单模式下，只运行白名单中的地图
        if self.map.check_allowlist_maps(map_data_name):
            self.map_statu.skip_this_map = True
            return
        # 检查是否应该跳过这张地图
        if self.map.check_forbidden_maps(map_data_name):
            self.map_statu.skip_this_map = True
            return
        self.map_drag = self.map_statu.next_map_drag
        self.map_statu.next_map_drag = False
        self.handle.f_key_error = False  # 初始化F键为未发生错误

        retry = True
        retry_cnt = 0
        while retry and retry_cnt < self.retry_cnt_max:
            retry = False
            # 选择地图
            self.map_statu.start_map_name = map_data_name if index == 0 else self.map_statu.start_map_name
            self.map_statu.end_map_name = map_data_name if index > 0 else self.map_statu.end_map_name
            webhook_and_log(f"\033[0;96;40m{map_data_name}\033[0m")
            self.monthly_pass.monthly_pass_check()  # 月卡检查
            log.info(
                f"路线领航员：\033[1;95m{map_data_author}\033[0m 感谢她(们)的无私奉献，准备开始路线：{map_base}")
            self.map_statu.skip_this_map = False  # 跳过这张地图
            self.map_statu.temp_point = ""  # 用于输出传送前的点位
            self.map_statu.normal_run = False  # 初始化跑步模式为默认
            for start in map_data['start']:
                key = list(start.keys())[0]
                log.info(key)
                value = start[key]

                self.show_dev_info(
                    dev, f'"{key}": {value}', 400, 1045, "key_value")

                self.img.search_img_allow_retry = False
                self.map.allow_map_drag(start)  # 是否强制允许拖动地图初始化
                self.map.allow_scene_drag(start)  # 是否强制允许拖动右侧场景初始化
                self.map.allow_multi_click(start)  # 多次点击
                self.map.allow_retry_in_map(start)  # 是否允许重试
                if key == "check":  # 判断周几
                    if value == 1:
                        value = [0, 1, 2, 3, 4, 5, 6]
                    # 1代表周二，4代表周五，6代表周日
                    if self.time_mgr.day_init(value):
                        log.info(f"今天{self.now.strftime('%A')}，尝试购买")
                        self.map_statu.skip_this_map = False
                        continue
                    else:
                        log.info(f"今天{self.now.strftime('%A')}，跳过")
                        self.map_statu.skip_this_map = True
                        break
                elif key == "need_allow_map_buy":
                    self.map_statu.skip_this_map = not self.cfg.read_json_file(
                        self.cfg.CONFIG_FILE_NAME, False).get('allow_map_buy', False)
                    if self.map_statu.skip_this_map:
                        log.info(
                            f" config.json 中的 allow_map_buy 为 False ，跳过该图{map_data['name']}，如果需要开启购买请改为 True 并且【自行确保】能够正常购买对应物品")
                        break
                elif key == "need_allow_snack_buy":
                    self.map_statu.skip_this_map = not self.cfg.read_json_file(
                        self.cfg.CONFIG_FILE_NAME, False).get('allow_snack_buy', False)
                    if self.map_statu.skip_this_map:
                        log.info(
                            f" config.json 中的 allow_snack_buy 为 False ，跳过该图{map_data['name']}，如果需要开启购买请改为 True 并且【自行确保】能够正常购买对应物品")
                        break
                elif key == "need_allow_memory_token":
                    self.map_statu.skip_this_map = not self.cfg.read_json_file(
                        self.cfg.CONFIG_FILE_NAME, False).get('allow_memory_token', False)
                    if self.map_statu.skip_this_map:
                        log.info(
                            f" config.json 中的 allow_memory_token 为 False ，跳过该图{map_data['name']}，如果需要开启请改为 True 并且【自行确保】能够正常获得对应物品")
                        break
                elif key == "normal_run":
                    self.map_statu.normal_run = True  # 此地图json将会被强制设定为禁止疾跑
                elif key == "blackscreen":
                    self.calculated.run_mapload_check()  # 强制执行地图加载检测
                elif key == "esc":
                    pyautogui.press('esc')
                elif key == 'map':
                    self.map.open_map()
                elif key == 'main':
                    self.handle.back_to_main()  # 检测并回到主界面
                    time.sleep(2)
                elif key == 'b':
                    self.handle.handle_b()
                elif key == 'await':
                    self.handle.handle_await(value)
                elif key == "space":
                    self.handle.handle_space(value, key)
                elif key in ["w", "a", "s", "d"]:
                    self.handle.handle_move(value, key)
                elif key in ["F4"]:
                    pyautogui.press(key)
                elif key == "f":
                    self.handle.handle_f(value)
                elif key == "picture\\max.png":
                    if self.calculated.allow_buy_item():
                        self.map_statu.skip_this_map = False
                        self.mouse_event.click_target(key, 0.93)
                        continue
                    else:
                        self.map_statu.skip_this_map = True
                        break
                elif key in ["picture\\transfer.png"]:
                    time.sleep(0.2)
                    if not self.mouse_event.click_target(key, 0.93):
                        self.map_statu.skip_this_map = True
                        break
                    self.calculated.run_mapload_check()
                    if self.map_statu.temp_point:
                        log.info(f'地图加载前的传送点为 {self.map_statu.temp_point}')
                else:
                    value = min(value, 0.8)
                    time.sleep(value)
                    if key in ["picture\\1floor.png", "picture\\2floor.png", "picture\\3floor.png"]:
                        self.map.handle_floor(key)
                    # 有可能未找到该图片，冗余查找
                    elif key in ["picture\\fanhui_1.png", "picture\\fanhui_2.png"]:
                        self.map.handle_back(key)
                    elif key.startswith("picture\\check_4-1_point"):
                        self.map.find_transfer_point(key, threshold=0.992)
                        if self.mouse_event.click_target(key, 0.992, retry_in_map=False):
                            log.info("筑梦机关检查通过")
                        else:
                            log.info("筑梦机关检查不通过，请将机关调整到正确的位置上")
                            self.map_statu.error_check_point = True
                        time.sleep(1)
                    elif key == "picture\\map_4-1_point_2.png":  # 筑梦边境尝试性修复
                        self.map.find_transfer_point(key, threshold=0.975)
                        self.mouse_event.click_target(key, 0.95)
                        self.map_statu.temp_point = key
                    elif key == "picture\\orientation_1.png":
                        self.map.handle_orientation(key, map_data)
                    elif key.startswith("picture\\map_4-3_point"):
                        self.map.find_transfer_point(key, threshold=0.975)
                        self.mouse_event.click_target(key, 0.93)
                        self.map_statu.temp_point = key
                        time.sleep(1.7)
                    elif key in self.map.planet_png_lst:
                        self.map.handle_planet(key)
                    else:
                        if self.map.allow_drap_map_switch or self.map_drag:
                            self.map.find_transfer_point(
                                key, threshold=0.975, offset=self.map.drag_exact)
                        if self.map.allow_scene_drag_switch:
                            self.map.find_scene(key, threshold=0.990)
                        if self.img.on_main_interface(timeout=0.5, allow_log=False):
                            log.info("执行alt")
                            self.mouse_event.click_target_with_alt(
                                key, 0.93, clicks=self.map.multi_click)
                        else:
                            self.mouse_event.click_target(
                                key, 0.93, clicks=self.map.multi_click, retry_in_map=self.map.allow_retry_in_map_switch)
                        self.map_statu.temp_point = key
                    self.map_statu.teleport_click_count += 1
                    log.info(
                        f'传送点击（{self.map_statu.teleport_click_count}）')
                    if self.img.search_img_allow_retry:
                        retry = True
                        retry_cnt += 1
                        if retry_cnt == self.retry_cnt_max:
                            self.map_statu.skip_this_map = True
                            self.map_statu.next_map_drag = True
                        break

                if self.handle.f_key_error:
                    log.info("F键错误，跳过当前地图")
                    self.map_statu.map_f_key_error.append(map_data_name)
                    break

    def process_single_map_handle(self, map_json, normal_run, dev=False, last_point=""):
        """
        处理单张地图的详细信息
        """
        # self.asu.screen = self.img.take_screenshot()[0]
        # self.ang = self.asu.get_now_direc()
        self.pause = Pause(dev=dev)
        map_base = map_json.split('.')[0]
        map_data = self.cfg.read_json_file(
            f"map/{self.map_info.map_version}/{map_base}.json")
        map_data_name = map_data['name']
        map_filename = map_base
        self.handle.fighting_count = sum(
            1 for map in map_data["map"] if "fighting" in map and map["fighting"] == 1)
        self.handle.current_fighting_index = 0
        total_map_count = len(map_data['map'])

        # 1号位相关检测
        self.calculated.first_role_check()  # 1号位为跑图角色
        # TODO: 黄泉情况下必须为黄泉角色

        dev_restart = True  # 初始化开发者重开
        self.handle.handle_view_set(0.1)
        # 开发群657378574，密码hoe2333
        while dev_restart:
            dev_restart = False  # 不进行重开
            last_key = ""
            self.handle.last_step_run = False  # 初始化上一次为走路
            for map_index, map_value in enumerate(map_data["map"]):
                press_key = self.pause.check_pause(
                    dev=dev, last_point=last_point)
                if press_key:
                    if press_key == 'F7':
                        pass
                    else:
                        dev_restart = True  # 检测到需要重开
                        self.window.switch_window()
                        time.sleep(1)
                        if press_key == 'F9':
                            self.mouse_event.click_target(
                                "picture\\transfer.png", 0.93)
                            self.calculated.run_mapload_check()
                        if press_key == 'F10':
                            pass
                        map_data = self.cfg.read_json_file(
                            f"map/{self.map_info.map_version}/{map_base}.json")  # 重新读取最新地图文件
                        break

                # 当前地图执行步骤
                map_progress_info = f"{map_index + 1}/{total_map_count} {map_value}"
                log.info(f"执行{map_filename}文件:{map_progress_info}")

                key, value = next(iter(map_value.items()))

                # 每一步操作开始前，重置地图内意外战斗为未发生
                self.handle.fight_in_map = False

                self.show_dev_info(
                    dev, f'"{key}": {value}', 900, 1045, "map_key_value")

                self.monthly_pass.monthly_pass_check()  # 行进前识别是否接近月卡时间
                if key == "space":
                    self.handle.handle_space(value, key)
                elif key == "caps":
                    self.handle.handle_caps(value)
                elif key == "r":
                    self.handle.handle_r(value, key)
                elif key == "f":
                    self.handle.handle_f(value)
                elif key == "allow_skip_f":
                    self.handle.handle_allow_skip_f(value)
                elif key == "check":
                    self.handle.handle_check(value, self.now.strftime('%A'))
                elif key == "mouse_move":
                    self.handle.mouse_move(value)
                elif key == "fighting":
                    self.handle.handle_fighting(value)
                elif key == "scroll":
                    self.handle.scroll(value)
                elif key == "shutdown":
                    self.handle.handle_shutdown()
                elif key == "e":
                    self.handle.handle_e(value)  # 用E进入战斗
                elif key == "esc":
                    self.handle.handle_esc(value)
                elif key in ['1', '2', '3', '4', '5']:
                    self.handle.handle_num(value, key)
                elif key == "main":
                    self.handle.handle_main(value)
                elif key == "view_set":
                    self.handle.handle_view_set(value)
                elif key == "view_reset":
                    self.handle.handle_view_reset(value)
                elif key == "view_rotate":
                    self.handle.handle_view_rotate(value)
                elif key == "await":
                    self.handle.handle_await(value)
                else:
                    self.handle.handle_move(value, key, normal_run, last_key)

                if self.map_info.map_version == "HuangQuan":
                    last_key = key

                if self.handle.f_key_error:
                    log.info("F键错误，跳过当前地图")
                    self.map_statu.map_f_key_error.append(map_data_name)
                    break

                if self.handle.fight_in_map and map_data_name not in self.map_statu.fight_in_map_list:
                    self.map_statu.fight_in_map_list.append(
                        f"{map_data_name}({map_progress_info})")

            # 黄泉乱砍模式（弃用）
            # if self.map_info.map_version == "HuangQuan":
            #     doubt_result = self.img.scan_screenshot(
            #         self.img.doubt_ui, offset=(0, 0, -1630, -800))
            #     if doubt_result["max_val"] > 0.92:
            #         log.info("检测到警告，有可能漏怪，进入黄泉乱砍模式")
            #         start_time = time.time()
            #         while time.time() - start_time < 60 and doubt_result["max_val"] > 0.92:
            #             directions = ["w", "a", "s", "d"]
            #             for index, direction in enumerate(directions):
            #                 log.info(f"开砍，{directions[index]}")
            #                 for i in range(3):
            #                     self.handle.handle_move(
            #                         0.1, direction, False, "")
            #                     self.handle.fight_e(value=2)
            #                 doubt_result = self.img.scan_screenshot(
            #                     self.img.doubt_ui, offset=(0, 0, -1630, -800))

            if self.map_info.map_version == "HuangQuan" and last_key == "e":
                if not self.img.on_main_interface(timeout=0.2):
                    fight_status = self.handle.fight_elapsed()
                    if not fight_status:
                        log.info('未进入战斗')

    def show_dev_info(self, dev: bool, text, x_offset: int, y_offset: int, text_mode):
        """
        开发者模式下显示文本
        """
        if dev:
            winrect = self.window.get_rect()
            log.info({winrect})
            x, y = winrect[0] + x_offset, winrect[1] + y_offset
            show_text(text, x, y, "nouid", text_mode)
