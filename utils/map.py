import time
import cv2 as cv
import pyautogui
import os
import win32api
import win32con
import win32gui
import random

from .calculated import Calculated
from .config import ConfigurationManager
from .log import log, webhook_and_log
import datetime

class Map:
    def __init__(self):
        self.calculated = Calculated()
        self.cfg = ConfigurationManager()
        self.open_map = self.cfg.read_json_file(self.cfg.CONFIG_FILE_NAME).get("open_map", "m")
        self.map_list = []
        self.map_list_map = {}
        self.map_versions = self.read_maps_versions()
        self.map_version = ""
        self.now = datetime.datetime.now()
        self.retry_cnt_max = 2
        self.map_statu_minimize = False  # 地图最小化

    def map_init(self, max_attempts=10):

        target = cv.imread('./picture/contraction.png')
        attempts = 0
        
        start_time = time.time()
        speed_open = False
        
        while attempts < max_attempts:
            log.info(f'打开地图')
            pyautogui.press(self.open_map)
            while self.calculated.on_main_interface(timeout=0.0,allow_log=False) and time.time() - start_time < 3 and not speed_open:
                pyautogui.keyDown('s')
                pyautogui.press(self.open_map)
                time.sleep(0.05)
            speed_open = True
            pyautogui.keyUp('s')
            time.sleep(3)  # 增加3秒识别延迟，避免偶现的识别错误
            result = self.calculated.scan_screenshot(target, offset=(550,960,-1050,-50))
            if result['max_val'] > 0.95:
                points = self.calculated.calculated(result, target.shape)
                log.info(f"识别点位{points}")
                if not self.map_statu_minimize:
                    log.info(f"地图最小化，识别图片匹配度{result['max_val']:.3f}")
                    pyautogui.click(points, clicks=10, interval=0.1)
                    self.map_statu_minimize = True
                break
            else:
                attempts += 1
                self.calculated.back_to_main()  # 打开map运行前保证在主界面

    def read_maps_versions(self):
        map_dir = './map'
        map_versions = [f for f in os.listdir(map_dir) if os.path.isdir(os.path.join(map_dir, f))]
        
        return map_versions
    
    def read_maps(self, map_version):
        # 从'./map'目录获取地图文件列表（排除'old'）
        map_dir = os.path.join('./map', map_version)
        json_files = [f for f in os.listdir(map_dir) if f.endswith('.json') and not f.startswith('old')]
        json_files = sorted(json_files, key=lambda x: [int(y) for y in x.replace('-','_').replace('.','_').split('_')[1:-1]])
    
        self.map_list = json_files
        self.map_list_map.clear()
        self.map_version = map_version
    
        for map_ in json_files:
            map_data = self.cfg.read_json_file(f"map/{map_version}/{map_}")
            key1 = map_[map_.index('_') + 1:map_.index('-')]
            key2 = map_[map_.index('-') + 1:map_.index('.')]
            key2_front = key2[:key2.index('_')]
            value = self.map_list_map.get(key1)
        
            if value is None:
                value = {}

            map_data_first_name = map_data["name"].replace(' ','')
            map_data_first_name = map_data_first_name[:map_data_first_name.index('-')]
            format_map_data_first_name = key1 + '-' + key2_front + ' ' + map_data_first_name
            value[key2] = [map_data["name"], format_map_data_first_name]
            self.map_list_map[key1] = value
            
        # log.info(f"self.map_list:{self.map_list}")
        # log.info(f"self.map_list_map:{self.map_list_map}")


    def format_time(self, seconds):
        # 格式化时间
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours:.0f}小时{minutes:.0f}分{seconds:.1f}秒"
        elif minutes > 0:
            return f"{minutes:.0f}分{seconds:.1f}秒"
        else:
            return f"{seconds:.1f}秒"

    def day_init(self, days: list=None):
        if days is None:  
            days = []
        today_weekday_num = self.now.weekday()
        in_day = today_weekday_num in days
        
        return in_day

    def get_target_datetime(self, hour, minute, second):
        now = datetime.datetime.now()
        target_date = now.date()
        target_time = datetime.datetime.combine(target_date, datetime.time(hour, minute, second))  # 设置目标时间    

        return target_time  
    
    def get_valid_hour(self):
        default_hour = 4

        while True:
            try:
                hour_input = input(f"请输入需要几点运行，默认为{default_hour}点 (0-23): ")
                if not hour_input:
                    log.debug(f"未输入小时数，使用默认值 {default_hour}。")
                    return default_hour
                hour = int(hour_input)  # 尝试将输入转换为整数  
                if 0 <= hour <= 23:  # 检查小时数是否在合法范围内  
                    return hour  
                else:
                    log.debug(f"输入的小时数不合法，请输入0-23之间的数字。")
            except ValueError:
                log.debug(f"未输入一个有效的数字。使用默认值 {default_hour}")
                return default_hour

    def wait_and_run(self, minute=1, second=0):  
        
        hour = self.get_valid_hour()  

        target_time = self.get_target_datetime(hour, minute, second)  # 计算目标时间  
        time_diff = target_time - datetime.datetime.now()  # 计算目标时间与当前时间的时间差  
        if time_diff.total_seconds() < 0:  # 如果目标时间已经过去，则设置为明天的这个时间  
            target_time += datetime.timedelta(days=1)  
            time_diff = target_time - datetime.datetime.now()
        wait_time = time_diff.total_seconds()  # 等待到目标时间    
        log.info(f"将在 {target_time.strftime('%Y-%m-%d %H:%M:%S')}")  
        log.info(f"需要等待 {wait_time:.0f} 秒")  
        time.sleep(wait_time)

    def has_crossed_4am(self, start, end):
        """
        检查是否从开始时间到结束时间跨越了凌晨4点
        """
        # 获取开始时间的凌晨4点
        start_4am = start.replace(hour=4, minute=0, second=0, microsecond=0)
        if start.hour >= 4:
            # 如果开始时间在4点之后，则4点时间应该是下一天的4点
            start_4am += datetime.timedelta(days=1)
        
        return start < start_4am <= end

    def find_transfer_point(self, key, threshold=0.99, min_threshold=0.93, timeout=60):
        """
        说明:
            寻找传送点
        参数：
            :param key:图片地址
            :param threshold:图片查找阈值
            :param min_threshold:最低图片查找阈值
            :param timeout:超时时间（秒）
        """
        start_time = time.time()
        target = cv.imread(key)
        direction_names = ["向下移动", "向左移动", "向上移动", "向右移动"]
        while not self.calculated.have_screenshot(target, (0, 0, 0, 0), threshold) and time.time() - start_time < timeout and threshold >= min_threshold:
            # 设置向下、向左、向上、向右的移动数值
            directions = [(250, 900, 250, 300), (250, 900, 850, 900), (1330, 200, 1330, 800), (1330, 200, 730, 200)]
            for index, direction in enumerate(directions):
                log.info(f"开始移动地图，{direction_names[index]}，当前所需匹配值{threshold}")
                for i in range(3):
                    if not self.calculated.have_screenshot(target, (0, 0, 0, 0), threshold):
                        self.calculated.mouse_drag(*direction)
                    else:
                        return
            threshold -= 0.01
    
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
        direction_names = ["向下移动", "向上移动"]
        while not self.calculated.have_screenshot(target, (0, 0, 0, 0), threshold) and time.time() - start_time < timeout and threshold >= min_threshold:
            # 设置向下、向上的移动数值
            directions = [(1700, 900, 1700, 300), (1700, 300, 1700, 900)]
            for index, direction in enumerate(directions):
                log.info(f"开始移动右侧场景，{direction_names[index]}，当前所需匹配值{threshold}")
                for i in range(1):
                    if not self.calculated.have_screenshot(target, (0, 0, 0, 0), threshold):
                        self.calculated.mouse_drag(*direction)
                    else:
                        return
            threshold -= 0.02

    def get_map_list(self, start, start_in_mid: bool=False):
        start_index = self.map_list.index(f'map_{start}.json')
        if start_in_mid:
            mid_slice = self.map_list[start_index:]
            map_list = mid_slice + self.map_list[:start_index]
        else:
            map_list = self.map_list[start_index:]
        
        return map_list
    
    def reset_round_count(self):
        """重置该锄地轮次相关的计数
        """
        self.calculated.total_fight_time = 0
        self.calculated.tatol_save_time = 0
        self.calculated.total_fight_cnt = 0
        self.calculated.total_no_fight_cnt = 0
        self.calculated.auto_final_fight_e_cnt = 0
    
    def allow_map_drag(self, start):
        self.allow_drap_map_switch = 0  # 初始化禁止拖动地图
        if "drag" in start and start["drag"] >= 1:
            self.allow_drap_map_switch = True
    
    def allow_scene_drag(self, start):
        self.allow_scene_drag_switch = 0  # 初始化禁止拖动
        if "scene" in start and start["scene"] >= 1:
            self.allow_scene_drag_switch = True
        
    
    def allow_multi_click(self, start):
        self.multi_click = 1
        self.allow_multi_click_switch = False
        if "clicks" in start and start["clicks"] >= 1:
            self.allow_multi_click_switch = True
            self.multi_click = int(start["clicks"])
    
    def allow_retry_in_map(self, start):
        self.allow_retry_in_map_switch = True
        if "forbid_retry" in start and start["forbid_retry"] >= 1:
            self.allow_retry_in_map_switch = False

    def check_and_skip_forbidden_maps(self, map_data_name):
        """检查并跳过配置中禁止的地图。

        Args:
            map_data_name (str): 当前处理的地图的名称。

        Returns:
            bool: 如果地图在禁止列表中，则返回 True，否则返回 False。
        """
        self.forbid_map = self.cfg.CONFIG.get('forbid_map', [])
        if not all(isinstance(item, str) for item in self.forbid_map):
            log.info("配置错误：'forbid_map' 应只包含字符串。")
            return False

        map_data_first_name = map_data_name.split('-')[0]
        if map_data_first_name in self.forbid_map:
            log.info(f"地图 {map_data_name} 在禁止列表中，将跳过此地图。")
            return True

        return False
    
    def align_angle(self):
        """校准视角
        """
        if not self.cfg.CONFIG.get("angle_set", False):
            self.calculated.back_to_main()
            time.sleep(1)
            self.calculated.set_angle()
        

    def auto_map(self, start, start_in_mid: bool=False, dev: bool = False):
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
            for index, map_json in enumerate(map_list):
                map_base = map_json.split('.')[0]
                map_data = self.cfg.read_json_file(f"map/{self.map_version}/{map_base}.json")
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
                    start_map_name, end_map_name = None, None
                    start_map_name, end_map_name = (map_data_name if index == 0 else start_map_name, map_data_name if index == max_index else end_map_name)
                    webhook_and_log(f"\033[0;96;40m{map_data_name}\033[0m")
                    self.calculated.monthly_pass_check()  # 月卡检查
                    log.info(f"路线领航员：\033[1;95m{map_data_author}\033[0m 感谢她(们)的无私奉献，准备开始路线：{map_base}")
                    jump_this_map = False  # 跳过这张地图，一般用于过期邮包购买
                    self.temp_point = ""  # 用于输出传送前的点位
                    normal_run = False  # 初始化跑步模式为默认
                    for start in map_data['start']:
                        key = list(start.keys())[0]
                        log.info(key)
                        value = start[key]
                        self.calculated.search_img_allow_retry = False
                        self.allow_map_drag(start)  # 是否强制允许拖动地图初始化
                        self.allow_scene_drag(start)  # 是否强制允许拖动右侧场景初始化
                        self.allow_multi_click(start)  # 多次点击
                        self.allow_retry_in_map(start)  # 是否允许重试
                        if key == "check":  # 判断周几
                            if value == 1:
                                value = [0,1,2,3,4,5,6]
                            if self.day_init(value):  # 1代表周二，4代表周五，6代表周日
                                log.info(f"今天{today_weekday_str}，尝试购买")
                                jump_this_map = False
                                continue
                            else:
                                log.info(f"今天{today_weekday_str}，跳过")
                                jump_this_map = True
                                break
                        elif key == "need_allow_map_buy":
                            if self.cfg.read_json_file(self.cfg.CONFIG_FILE_NAME, False).get('allow_map_buy', False):
                                jump_this_map = False
                                continue
                            else:
                                log.info(f" config.json 中的 allow_map_buy 为 False ，跳过该图{map_data['name']}，如果需要开启购买请改为 True 并且【自行确保】能够正常购买对应物品")
                                jump_this_map = True
                                break
                        elif key == "need_allow_snack_buy":
                            if self.cfg.read_json_file(self.cfg.CONFIG_FILE_NAME, False).get('allow_snack_buy', False):
                                jump_this_map = False
                                continue
                            else:
                                log.info(f" config.json 中的 allow_snack_buy 为 False ，跳过该图{map_data['name']}，如果需要开启购买请改为 True 并且【自行确保】能够正常购买对应物品")
                                jump_this_map = True
                                break
                        elif key == "normal_run":
                            normal_run = True  # 此地图json将会被强制设定为禁止疾跑
                            continue
                        elif key == "blackscreen":
                            self.calculated.run_mapload_check()  # 强制执行地图加载检测
                            continue
                        elif key == "esc":
                            pyautogui.press('esc')
                            continue
                        elif key == 'map':
                            self.map_init()
                        elif key == 'main':
                            self.calculated.back_to_main()  # 检测并回到主界面
                            time.sleep(2)
                        elif key == 'b':
                            pyautogui.press('b')
                            time.sleep(1)
                        elif key == 'await':
                            time.sleep(abs(value))
                        elif key == "space":
                            pyautogui.press('space')
                        elif key == "picture\\max.png":
                            if self.calculated.allow_buy_item():
                                jump_this_map = False
                                self.calculated.click_target(key, 0.93)
                                continue
                            else:
                                jump_this_map = True
                                break
                        elif key in ["picture\\transfer.png"]:
                            time.sleep(0.1)
                            if not self.calculated.click_target(key, 0.93):
                                jump_this_map = True
                                break
                            self.calculated.run_mapload_check()
                            if self.temp_point:
                                log.info(f'地图加载前的传送点为 {self.temp_point}')
                        else:
                            value = min(value, 0.8)
                            time.sleep(value)
                            if key == "picture\\map_0.png":
                                self.calculated.click_target(key, 0.93)
                                self.calculated.run_mapload_check()
                            elif key == "picture\\map_4-1_point_5.png":  # 筑梦模块移动模块识别
                                self.calculated.click_target_with_alt(key, 0.93)
                                self.calculated.run_dreambuild_check()
                            elif key in ["picture\\1floor.png","picture\\2floor.png","picture\\3floor.png"]:
                                if self.calculated.img_bitwise_check(target_path=key, offset=(30,740,-1820,-70)):
                                    self.calculated.click_target(key, 0.93, offset=(30,740,-1820,-70))
                                else:
                                    log.info(f"已在对应楼层，跳过选择楼层")
                                    pass
                            elif key in ["picture\\fanhui_1.png","picture\\fanhui_2.png"]:  # 有可能未找到该图片，冗余查找
                                img = cv.imread("./picture/kaituoli_1.png")
                                if not self.calculated.on_interface(check_list=[img], timeout=1, interface_desc='星轨航图', threshold=0.97, offset=(1580,0,0,-910), allow_log=False):
                                    self.calculated.click_target(key, 0.94,timeout=3, offset=(1660,100,-40,-910), retry_in_map=False)
                                else:
                                    log.info(f"检测到星轨航图，不进行点击'返回'")
                            elif key.startswith("picture\\check_4-1_point"):
                                self.find_transfer_point(key, threshold=0.992)
                                if self.calculated.click_target(key, 0.992, retry_in_map=False):
                                    log.info(f"筑梦机关检查通过")
                                else:
                                    log.info(f"筑梦机关检查不通过，请将机关调整到正确的位置上")
                                    error_check_point = True
                                time.sleep(1)
                            elif key == "picture\\map_4-1_point_2.png":  # 筑梦边境尝试性修复
                                self.find_transfer_point(key, threshold=0.975)
                                self.calculated.click_target(key, 0.95)
                                self.temp_point = key
                            elif key.startswith("picture\\map_4-3_point") or key in ["picture\\orientation_2.png", "picture\\orientation_3.png", "picture\\orientation_4.png", "picture\\orientation_5.png"]:
                                self.find_transfer_point(key, threshold=0.975)
                                self.calculated.click_target(key, 0.93)
                                self.temp_point = key
                                time.sleep(1.7)
                            else:
                                if self.allow_drap_map_switch or self.map_drag:
                                    self.find_transfer_point(key, threshold=0.975)
                                if self.allow_scene_drag_switch:
                                    self.find_scene(key, threshold=0.990)
                                if self.calculated.on_main_interface(timeout=0.5, allow_log=False):
                                    self.calculated.click_target_with_alt(key, 0.93, clicks=self.multi_click)
                                else:
                                    self.calculated.click_target(key, 0.93, clicks=self.multi_click, retry_in_map=self.allow_retry_in_map_switch)
                                self.temp_point = key
                            teleport_click_count += 1
                            log.info(f'传送点击（{teleport_click_count}）')
                            if self.calculated.search_img_allow_retry:
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

                self.calculated.auto_map(map_base, False, normal_run, dev=dev, last_point=self.temp_point)

                # 记录处理结束时间
                end_time = time.time()

                # 计算处理时间并输出
                processing_time = end_time - start_time
                formatted_time = self.format_time(processing_time)
                total_processing_time += processing_time
                log.info(f"{map_base}用时\033[1;92m『{formatted_time}』\033[0m,总计:\033[1;92m『{self.format_time(total_processing_time)}』\033[0m")
                
                if index == max_index:
                    total_time = time.time() - total_start_time
                    total_fight_time = self.calculated.total_fight_time
                    log.info(f"结束该阶段的锄地，总计用时 {self.format_time(total_time)}，总计战斗用时 {self.format_time(total_fight_time)}")
                    error_fight_cnt = self.calculated.error_fight_cnt
                    log.info(f"异常战斗识别（战斗时间 < {self.calculated.error_fight_threshold} 秒）次数：{error_fight_cnt}")
                    if error_check_point:
                        log.info(f"筑梦机关检查不通过，请将机关调整到正确的位置上")
                    log.info(f"疾跑节约的时间为 {self.format_time(self.calculated.tatol_save_time)}")
                    log.info(f"战斗次数{self.calculated.total_fight_cnt}")
                    log.info(f"未战斗次数{self.calculated.total_no_fight_cnt}")
                    log.info(f"未战斗次数首次锄地参考值：70-80，不作为漏怪标准，漏怪具体请在背包中对材料进行溯源查找")
                    log.info(f"开始地图：{start_map_name}，结束地图：{end_map_name}")

        else:
            log.info(f'地图编号 {start} 不存在，请尝试检查地图文件')
