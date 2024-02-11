import time
import cv2 as cv
import pyautogui
import os

from .calculated import Calculated
from .config import get_file, read_json_file, CONFIG_FILE_NAME
from .log import log, webhook_and_log

class Map:
    def __init__(self):
        self.calculated = Calculated()
        self.open_map = read_json_file(CONFIG_FILE_NAME).get("open_map", "m")
        self.map_list = []
        self.map_list_map = {}
        self.read_maps()

    def map_init(self):

        target = cv.imread('./picture/contraction.png')
        max_attempts = 60  # 最大重试次数
        attempts = 0

        while attempts < max_attempts:
            result = self.calculated.scan_screenshot(target)
            if result['max_val'] > 0.97:
                points = self.calculated.calculated(result, target.shape)
                log.debug(points)
                log.info(f'地图最小化')
                pyautogui.click(points, clicks=5, interval=0.1)
                break
            else:
                attempts += 1
                log.info(f'打开地图')
            pyautogui.keyDown(self.open_map)
            pyautogui.keyUp(self.open_map)
            time.sleep(3)  # 3秒延迟

    def read_maps(self):
        # 从'./map'目录获取地图文件列表（排除'old'）
        map_dir = './map'
        json_files = [f for f in os.listdir(map_dir) if f.endswith('.json') and not f.startswith('old')]
        json_files = sorted(json_files, key=lambda x: [int(y) for y in x.replace('-','_').replace('.','_').split('_')[1:-1]])
    
        self.map_list = json_files
        self.map_list_map.clear()
    
        for map_ in json_files:
            map_data = read_json_file(f"map/{map_}")
            key1 = map_[map_.index('_') + 1:map_.index('-')]
            key2 = map_[map_.index('-') + 1:map_.index('.')]
            value = self.map_list_map.get(key1)
        
            if value is None:
                value = {}
        
            value[key2] = map_data["name"]
            self.map_list_map[key1] = value
    
        log.debug(self.map_list)
        log.debug(self.map_list_map)


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

    def auto_map(self, start):
        total_processing_time = 0
        teleport_click_count = 0  

        if f'map_{start}.json' in self.map_list:
            map_list = self.map_list[self.map_list.index(f'map_{start}.json'):len(self.map_list)]
            for map_ in map_list:
                # 选择地图
                map_ = map_.split('.')[0]
                map_data = read_json_file(f"map/{map_}.json")
                webhook_and_log(f"\033[0;96;40m{map_data['name']}\033[0m")
                self.calculated.monthly_pass()
                log.info(f"路线领航员：\033[1;95m{map_data['author']}\033[0m 感谢她(们)的无私奉献")
                for start in map_data['start']:
                    key = list(start.keys())[0]
                    log.debug(key)
                    value = start[key]
                    if key == 'map':
                        self.map_init()
                    else:
                        time.sleep(value)
                        self.calculated.click_target(key, 0.93)
                        teleport_click_count += 1 
                        log.info(f'传送点击（{teleport_click_count}）')
                        time.sleep(2)  # 传送点击后等待3秒

                start_time = time.time()  
                count = 0
                while self.calculated.is_blackscreen():
                    count += 1
                    time.sleep(1)
                end_time = time.time()  # 记录地图加载完成的时间
                loading_time = end_time - start_time + 3  
                log.info(f'地图载毕，用时 {loading_time:.1f} 秒')
                time.sleep(2)  # 增加2秒等待防止人物未加载错轴
                teleport_click_count = 0  # 在每次地图循环结束后重置计数器
                start_time = time.time()
                self.calculated.auto_map(map_, False)
                end_time = time.time()
                processing_time = end_time - start_time
                formatted_time = self.format_time(processing_time)
                total_processing_time += processing_time
                log.info(f"{map_}用时\033[1;92m『{formatted_time}』\033[0m,总计:\033[1;92m『{self.format_time(total_processing_time)}』\033[0m")

        else:
            log.info(f'地图编号 {start} 不存在，请尝试检查地图文件')
