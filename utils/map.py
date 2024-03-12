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
from datetime import datetime

class Map:
    def __init__(self):
        self.calculated = Calculated()
        self.cfg = ConfigurationManager()
        self.open_map = self.cfg.read_json_file(self.cfg.CONFIG_FILE_NAME).get("open_map", "m")
        self.map_list = []
        self.map_list_map = {}
        self.map_versions = self.read_maps_versions()
        self.map_version = ""
        self.now = datetime.now()

    def map_init(self, max_attempts=60):

        target = cv.imread('./picture/contraction.png')
        attempts = 0

        time.sleep(2)  # 增加2秒识别延迟，避免偶现的识别错误
        while attempts < max_attempts:
            result = self.calculated.scan_screenshot(target, offset=(550,960,-1050,-50))
            if result['max_val'] > 0.95:
                points = self.calculated.calculated(result, target.shape)
                log.info(f"识别点位{points}")
                log.info(f"地图最小化，识别图片匹配度{result['max_val']:.3f}")
                pyautogui.click(points, clicks=5, interval=0.1)
                break
            else:
                attempts += 1
                log.info(f'打开地图')
            pyautogui.press(self.open_map)
            time.sleep(3)  # 3秒延迟

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
            value = self.map_list_map.get(key1)
        
            if value is None:
                value = {}
        
            value[key2] = map_data["name"]
            self.map_list_map[key1] = value
    
        log.info(f"self.map_list:{self.map_list}")
        log.info(f"self.map_list_map:{self.map_list_map}")


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

    def get_map_list(self, start, start_in_mid: bool=False):
        start_index = self.map_list.index(f'map_{start}.json')
        if start_in_mid:
            mid_slice = self.map_list[start_index:]
            map_list = mid_slice + self.map_list[:start_index]
        else:
            map_list = self.map_list[start_index:]
        
        return map_list
    
    def auto_map(self, start, start_in_mid: bool=False):
        total_processing_time = 0
        teleport_click_count = 0  
        today_weekday_str = self.now.strftime('%A')
        if f'map_{start}.json' in self.map_list:
            total_start_time = time.time()
            # map_list = self.map_list[self.map_list.index(f'map_{start}.json'):len(self.map_list)]
            map_list = self.get_map_list(start, start_in_mid)
            max_index = max(index for index, _ in enumerate(map_list))
            for index, map_ in enumerate(map_list):
                # 选择地图
                start_time = time.time() 
                map_ = map_.split('.')[0]
                map_data = self.cfg.read_json_file(f"map/{self.map_version}/{map_}.json")
                webhook_and_log(f"\033[0;96;40m{map_data['name']}\033[0m")
                self.calculated.monthly_pass()
                log.info(f"路线领航员：\033[1;95m{map_data['author']}\033[0m 感谢她(们)的无私奉献，准备开始路线：{map_}")
                jump_this_map = False  # 跳过这张地图，一般用于过期邮包购买
                temp_point = ""  # 用于输出传送前的点位
                self.calculated.on_main_interface(timeout=5)  # 地图json，start运行前保证在主界面
                for start in map_data['start']:
                    key = list(start.keys())[0]
                    log.info(key)
                    value = start[key]
                    allow_drap_map = 0  # 初始化禁止拖动地图
                    if "drag" in start:
                        allow_drap_map = start["drag"]
                    self.calculated.monthly_pass_check()
                    if key == "check" and value == 1:  # 判断是否为周二，周五，周日
                       if self.day_init([1,4,6]):  # 1代表周二，4代表周五，6代表周日
                            log.info(f"{today_weekday_str}，周二五日，尝试购买")
                            jump_this_map = False
                            continue
                       else:
                            log.info(f"{today_weekday_str}，非周二五日，跳过")
                            jump_this_map = True
                            break
                    elif key == "esc":
                        pyautogui.press('esc')
                        continue
                    elif key == 'map':
                        self.map_init()
                    elif key == 'main':
                        self.calculated.back_to_main()  # 检测并回到主界面
                        time.sleep(2)
                    elif key == "picture\\max.png":
                        if self.calculated.allow_buy_item():
                            jump_this_map = False
                            continue
                        else:
                            jump_this_map = True
                            break
                    elif key in ["picture\\transfer.png"]:
                        time.sleep(0.1)
                        self.calculated.click_target_with_alt(key, 0.93)
                        self.calculated.run_mapload_check()
                        if temp_point:
                            log.info(f'地图加载前的传送点为 {temp_point}')
                    else:
                        value = min(value, 0.8)
                        time.sleep(value)
                        if key == "picture\\map_0.png":
                            self.calculated.click_target_with_alt(key, 0.93)
                            self.calculated.run_mapload_check()
                        elif key == "picture\\map_4-1_point_5.png":  # 筑梦模块移动模块识别
                            self.calculated.click_target_with_alt(key, 0.93)
                            self.calculated.run_dreambuild_check()
                        elif key in ["picture\\first_floor.png","picture\\second_floor.png","picture\\third_floor.png"]:
                            if self.calculated.img_bitwise_check(key):
                                self.calculated.click_target_with_alt(key, 0.93)
                            else:
                                log.info(f"已在对应楼层，跳过选择楼层")
                                pass
                        elif key.startswith("picture\\map_4-3_point") or key in ["picture\\orientation_2.png", "picture\\orientation_3.png", "picture\\orientation_4.png", "picture\\orientation_5.png"]:
                            self.find_transfer_point(key, threshold=0.97)
                            self.calculated.click_target_with_alt(key, 0.93)
                            temp_point = key
                            time.sleep(1.7)
                        else:
                            if allow_drap_map:
                                self.find_transfer_point(key, threshold=0.97)
                            self.calculated.click_target_with_alt(key, 0.93)
                            temp_point = key
                        teleport_click_count += 1 
                        log.info(f'传送点击（{teleport_click_count}）')
                        # time.sleep(1.7)  # 传送点击后等待2秒
                
                teleport_click_count = 0  # 在每次地图循环结束后重置计数器

                # 'check'过期邮包跳过，执行下一张图
                if jump_this_map:
                    continue
                
                # 记录处理开始时间
                start_time = time.time()

                self.calculated.auto_map(map_, False)

                # 记录处理结束时间
                end_time = time.time()

                # 计算处理时间并输出
                processing_time = end_time - start_time
                formatted_time = self.format_time(processing_time)
                total_processing_time += processing_time
                log.info(f"{map_}用时\033[1;92m『{formatted_time}』\033[0m,总计:\033[1;92m『{self.format_time(total_processing_time)}』\033[0m")
                
                if index == max_index:
                    total_time = time.time() - total_start_time
                    total_fight_time = self.calculated.total_fight_time
                    log.info(f"结束运行，总计用时 {self.format_time(total_time)}，总计战斗用时 {self.format_time(total_fight_time)}")
                    error_fight_cnt = self.calculated.error_fight_cnt
                    log.info(f"异常战斗识别（战斗时间 < {self.calculated.error_fight_threshold} 秒）次数：{error_fight_cnt}")
                    log.info(f"疾跑节约的时间为 {self.format_time(self.calculated.tatol_save_time)}")
                    log.info(f"战斗次数{self.calculated.total_fight_cnt}")
                    log.info(f"未战斗次数{self.calculated.total_no_fight_cnt}")

        else:
            log.info(f'地图编号 {start} 不存在，请尝试检查地图文件')
