import asyncio
import random
import threading
import time
from datetime import datetime

import cv2
import numpy as np
import pyautogui
import win32api
import win32con
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key as KeyboardKey

from utils.config.config import ConfigurationManager
from utils.exceptions import CustomException
from utils.img import Img
from utils.keyboard_event import KeyboardEvent
from utils.log import log
from utils.mouse_event import MouseEvent
from utils.singleton import SingletonMeta
from utils.window import Window


class Handle(metaclass=SingletonMeta):
    def __init__(self):
        self.mouse_event = MouseEvent()
        self.img = Img()
        self.cfg = ConfigurationManager()
        self.window = Window()

        self.arrow_begin = None  # 初始箭头
        self.run_fix_time = 0  # 强制断开疾跑时间
        self.run_fixed = False  # 强制断开疾跑标志
        self.last_step_run = False  # 初始化
        self.current_fighting_index = 0  # 当前战斗次数
        self.fighting_count = 0  # 总战斗次数
        self.auto_final_fight_e_cnt = 0  # 秘技E的次数计数
        self.attack_once = False  # 检测fighting时仅攻击一次，避免连续攻击
        self.tatol_save_time = 0  # 疾跑节约时间
        self.time_error_cnt = 0  # 系统卡顿计数
        self.total_fight_cnt = 0  # 战斗次数计数
        self.total_no_fight_cnt = 0  # 非战斗次数计数
        self.total_fight_time = 0  # 总计战斗时间
        self.fight_in_map = False  # 地图内意外战斗初始化为否
        self.error_fight_cnt = 0  # 异常战斗<3秒的计数
        self.error_fight_threshold = 3  # 异常战斗为战斗时间<3秒
        self.snack_used = 0  # 奇巧零食使用次数

        self.f_key_error = False  # F键错误

        self.multi_config = 1.0

        self.running = False
        self.thread_cancel_sprint = None  # 用于保存取消疾跑任务的线程
        self.thread_check_sprint = None   # 用于保存检测疾跑任务的线程

        self.arrow_0 = cv2.imread("./picture/screenshot_arrow.png")

    def handle_space(self, value, key):
        """按下space键，延迟value秒后抬起
        """
        KeyboardEvent.keyboard_press(key, value)

    def handle_caps(self, value):
        """按下space键，延迟value秒后抬起
        """
        KeyboardEvent.keyboard_press('caps', value)

    def handle_r(self, value, key):
        """
        按下r键，延迟value秒后抬起
        """
        random_interval = random.uniform(0.3, 0.7)
        num_repeats = int(value / random_interval)
        for _ in range(num_repeats):
            KeyboardEvent.keyboard_press(key)
            time.sleep(random_interval)
        remaining_time = value - (num_repeats * random_interval)
        if remaining_time > 0:
            time.sleep(remaining_time)

    def handle_f(self, value, allow_skip=True):
        """
        按下f键，等待value秒后进行下一步
        """
        # 初始化F键错误
        self.f_key_error = False
        use_time, delay, allow_f = self._check_f_img(value)
        if allow_f:
            if use_time:
                KeyboardEvent.keyboard_press('f', delay=0.1)
                log.info(f"按下'F'，等待{delay}秒")
                time.sleep(delay)
            else:
                KeyboardEvent.keyboard_press('f', delay=0.1)
                log.info("按下'F'，等待主界面检测")
                time.sleep(2)  # 2 秒后开始检测主界面
                self.img.on_main_interface()
                time.sleep(2)  # 等待 2 秒加载人物
        else:
            if allow_skip:
                log.info("检测到非正常'F'情况，不执行并跳过'F'")
                self.f_key_error = True
            else:
                log.info("检测到非正常'F'情况，继续执行")
                self.f_key_error = False

    def _check_f_img(self, value=15, timeout=5):
        """
        检查F的交互类型。

        :return: tuple, 包含三个元素：(是否使用绝对时间, 绝对时间的值（秒）, 是否允许按下F)
        """
        images = {
            'target': cv2.imread("./picture/sw.png"),
            'dream_pop': cv2.imread("./picture/F_DreamPop.png"),
            'teleport': cv2.imread("./picture/F_Teleport.png"),
            'space_anchor': cv2.imread("./picture/F_SpaceAnchor.png"),
            'dream_module': cv2.imread("./picture/F_DreamModule.png"),
            'listen': cv2.imread("./picture/F_Listen.png"),
            'dream_scape': cv2.imread("./picture/F_DreamScape.png"),
            'go_to': cv2.imread("./picture/F_Goto.png")
        }

        start_time = time.time()
        log.info("扫描'F'图标")

        default_delay = value
        found_images = {}

        while time.time() - start_time < timeout:
            for count, (name, img) in enumerate(images.items(), start=1):
                result = self.img.scan_screenshot(
                    img) if count == 1 else self.img.scan_temp_screenshot(img)
                if result['max_val'] > 0.95:
                    found_images[name] = result['max_val']
                    log.info(f"扫描'F'：{name}，匹配度：{result['max_val']:.3f}")

            if len(found_images) == 2 or ('target' in found_images and time.time() - start_time >= 2):
                break

            time.sleep(0.5)

        return self._analyze_found_images(found_images, default_delay)

    def _analyze_found_images(self, found_images, default_delay):
        """
        分析找到的图片，决定下一步

        :param found_images: dict, 找到的图片及其匹配度
        :param default_delay: int, 默认延迟时间
        :return: tuple, 包含三个元素：(是否使用绝对时间, 绝对时间的值（秒）, 是否允许按下F)
        """
        use_absolute_time = True
        delay = default_delay
        allow_press_f = True
        if 'target' in found_images:
            if 'dream_pop' in found_images:
                log.info('扫描到 梦泡充能')
                delay = 3
            elif 'teleport' in found_images:
                log.info('扫描到 入画')
                use_absolute_time = False
                delay = 0
            elif 'space_anchor' in found_images:
                log.info('扫描到 界域定锚')
                use_absolute_time = False
                delay = 0
                allow_press_f = False
            elif 'dream_module' in found_images:
                log.info('扫描到 筑梦模块')
                delay = 4
            elif 'listen' in found_images:
                log.info('扫描到 旁听')
                use_absolute_time = False
                delay = 0
                allow_press_f = False
            elif 'dream_scape' in found_images:
                log.info('扫描到 梦境空间')
                delay = 5
            elif 'go_to' in found_images:
                log.info('扫描到 前往')
                use_absolute_time = False
                delay = 0
            else:
                log.info("扫描到 'F'")
        else:
            log.info("扫描失败！")
            allow_press_f = False

        return use_absolute_time, delay, allow_press_f

    def handle_allow_skip_f(self, value):
        """
        按下f键，等待value秒后进行下一步
        F异常时不跳过地图
        """
        self.handle_f(value, allow_skip=False)

    def handle_check(self, value, today_weekday_str):
        """
        检查是否在指定日期购买
        """
        if value is None:
            value = []
        elif value == 1:
            value = [0, 1, 2, 3, 4, 5, 6]
        today_weekday_num = datetime.now().weekday()
        in_day = today_weekday_num in value

        if in_day:
            log.info(f"今天{today_weekday_str}，尝试购买")
        else:
            log.info(f"今天{today_weekday_str}，跳过")

        return in_day

    def handle_fighting(self, value):
        """
        处理战斗
        """
        if value == 1:  # 战斗
            self.current_fighting_index += 1
            auto_final_fight_e_cnt_max = self.cfg.config_file.get(
                "auto_final_fight_e_cnt")
            if self.cfg.config_file.get("auto_final_fight_e", False) and self.current_fighting_index == self.fighting_count and self.auto_final_fight_e_cnt < auto_final_fight_e_cnt_max:
                self.auto_final_fight_e_cnt += 1
                log.info("地图最后一个fighting:1，改为使用e")
                self.handle_e(value)
            else:
                self.fighting()
        elif value == 2:  # 打障碍物
            self.mouse_event.click(win32api.GetCursorPos())
            time.sleep(1)
        else:
            raise CustomException("map数据错误, fighting参数异常")

    def handle_e(self, value):
        """
        按下e键，等待delay秒后抬起
        """
        if value == 1:
            self.fight_e(value=1)
        elif value == 2:
            self.fight_e(value=2)

    def fight_e(self, value):
        """
        使用'E'攻击，补充秘技点数
        """
        pyautogui.press('e')
        time.sleep(0.25)
        self.technique_points_dialog()

        if value == 1:
            time.sleep(1)
            self.mouse_event.click_center()
            fight_status = self.fight_elapsed()
            if not fight_status:
                log.info('未进入战斗')
        elif value == 2:
            pass

        time.sleep(0.05)

    def technique_points_dialog(self):
        """
        秘技点数对话框
        """
        if not self.img.on_main_interface(timeout=0.0, allow_log=True):
            time.sleep(0.5)
            image_a = cv2.imread("./picture/eat.png")
            result_a = self.img.scan_screenshot(image_a)
            if result_a["max_val"] > 0.9:
                allow_fight_e_buy_prop = self.cfg.config_file.get(
                    "allow_fight_e_buy_prop", False)
                if allow_fight_e_buy_prop:
                    allow_buy = False
                    round_disable = cv2.imread("./picture/round_disable.png")
                    if self.img.on_interface(check_list=[round_disable], timeout=0.5, interface_desc='无法购买', threshold=0.95):
                        pass
                    else:
                        food_lab = cv2.imread("./picture/qiqiao_lab.png")
                        food_icon = cv2.imread("./picture/qiqiao.png")
                        find = False
                        drag = 0
                        while not find and drag < 4:
                            if self.img.on_interface(check_list=[food_icon], timeout=2, interface_desc='奇巧零食图片', threshold=0.95, offset=(900, 300, -400, -300)):
                                find = True
                                for _ in range(2):
                                    self.mouse_event.click_target(
                                        "./picture/qiqiao.png", 0.95, True, 2, (900, 300, -400, -300), False)
                                    if self.img.on_interface(check_list=[food_lab], timeout=2, interface_desc='奇巧零食', threshold=0.97):
                                        time.sleep(0.1)
                                        self.mouse_event.click_target(
                                            "./picture/round.png", 0.9, timeout=8)
                                        self.snack_used += 1
                                        time.sleep(0.5)
                                        allow_buy = True
                            else:
                                log.info("下滑查找零食")
                                self.mouse_event.mouse_drag(
                                    1460, 450, 1460, 330)
                                time.sleep(0.5)
                                drag += 1
                        time.sleep(1)
                    self.mouse_event.click_target(
                        "./picture/cancel.png", 0.95, timeout=2)
                    time.sleep(0.1)
                    if allow_buy:
                        log.info("补E")
                        time.sleep(0.25)
                        pyautogui.press('e')
                        log.info("补E结束")
                        time.sleep(0.25)
                else:
                    self.mouse_event.click_target(
                        "./picture/cancel.png", 0.95, timeout=2)
                    time.sleep(0.1)

    def back_to_main(self, delay=2.0):
        """
        检测并回到主界面
        """
        while not self.img.on_main_interface(timeout=2):  # 检测是否出现左上角灯泡，即主界面检测
            pyautogui.press('esc')
            time.sleep(delay)
            if self.img.on_interface(check_list=[self.img.battle_esc_check], timeout=0.0, threshold=0.97, offset=(0, 0, -1800, -970), allow_log=True):
                pyautogui.press('esc')
                time.sleep(2)
                self.fight_elapsed()

    def handle_esc(self, value):
        """
        按下esc键，等待3秒后抬起
        """
        if value == 1:
            win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
            time.sleep(random.uniform(0.09, 0.15))
            win32api.keybd_event(win32con.VK_ESCAPE, 0,
                                 win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(3)
        else:
            raise CustomException("map数据错误, esc参数只能为1")

    def handle_num(self, value, key):
        """
        按下数字键，等待value秒后抬起
        """
        time.sleep(value)
        KeyboardController().press(key)
        time.sleep(0.3)
        KeyboardController().release(key)

    def handle_main(self, value):
        """
        返回主界面
        """
        time.sleep(value)
        self.back_to_main(delay=0.1)
        time.sleep(2)

    def handle_view_set(self, value):
        """设置初始视角
        """
        time.sleep(value)
        self.arrow_begin = self.take_arrow()

    def handle_view_reset(self, value):
        """重置视角
        """
        time.sleep(value)
        sub = 0
        cnt = 0
        self.handle_move(value=0.01, key="w")  # 重置箭头指向为视角方向
        time.sleep(0.6)
        while cnt < 4:
            arrow_temp = self.take_arrow()
            ang = self.cal_ang(arrow_temp, self.arrow_begin)
            sub = 360 - ang
            sub = (sub + 180) % 360 - 180
            sub = sub if sub != 0 else 1e-9
            log.info(f"开始重置视角，计算角度ang:{ang}，旋转角度sub:{sub}")
            # KeyboardEvent.keyboard_press("caps_lock", 0.2)
            # time.sleep(1)
            self.mouse_event.mouse_move(sub)
            self.handle_move(value=0.01, key="w")
            cnt += 1
            if abs(sub) <= 1:
                break
            time.sleep(0.6)

    def cal_ang(self, arrow_img, arrow_begin_img):
        """计算与初始蓝色箭头相差的角度
        """
        mx_acc = 0
        ang = 0
        for i in range(360):
            rt = self.img.image_rotate(arrow_img, i)
            result = cv2.matchTemplate(
                arrow_begin_img, rt, cv2.TM_CCORR_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            if max_val > mx_acc:
                mx_acc = max_val
                mx_loc = (max_loc[0] + 12, max_loc[1] + 12)
                ang = i

        return ang
    # 不同电脑鼠标移动速度、放缩比、分辨率等不同，因此需要校准
    # 基本逻辑：每次正反转60度，然后计算实际转了几度，计算出误差比

    def set_angle(self, ang=None):
        """校准视角旋转"""
        if ang is None:
            ang = [1, 1, 3]

        log.info("开始校准")
        move_list = [60, -60]
        offset_list = []

        for move_num in move_list:
            self.handle_move(0.01, "w")
            time.sleep(0.6)
            self.handle_view_set(0.1)
            init_ang = self.cal_ang(self.arrow_begin, self.arrow_begin)
            log.debug(f"init_ang: {init_ang}")
            last_ang = init_ang

            for repeat in ang:
                if last_ang != init_ang and repeat == 1:
                    continue

                ang_list = []
                for _ in range(repeat):
                    self.mouse_event.mouse_move(
                        move_num, fine=3 // repeat, align=True)
                    time.sleep(0.2)
                    self.handle_move(0.01, "w")
                    time.sleep(0.6)
                    arrow_temp = self.take_arrow()
                    now_ang = self.cal_ang(arrow_temp, self.arrow_begin)
                    log.debug(f"now_ang: {now_ang}")
                    sub = now_ang - last_ang
                    sub = sub + 360 if (move_num >= 0 and sub < 0) else sub - \
                        360 if (move_num < 0 and sub > 0) else sub
                    ang_list.append(sub)
                    last_ang = now_ang

                valid_angles = [a for a in ang_list if abs(
                    a - np.median(ang_list)) <= 5]
                if valid_angles:
                    ax = sum([move_num for _ in valid_angles])
                    ay = sum(valid_angles)

                    if ay != 0:
                        offset_list.append(ax / ay)
                    else:
                        log.info("疑似校准错误")
                        offset_list.append(1)

        if offset_list:
            self.multi_config = np.median(offset_list)
            self.cfg.modify_json_file(
                filename=self.cfg.CONFIG_FILE_NAME, key="angle", value=str(self.multi_config))
            self.cfg.modify_json_file(
                filename=self.cfg.CONFIG_FILE_NAME, key="angle_set", value=True)
            log.info(f"校准完成，angle: {self.multi_config}")
        else:
            log.info("校准失败")

        time.sleep(1)

    def handle_view_rotate(self, value):
        """
        旋转视角至value度，顺时针
        """
        time.sleep(1)
        sub = 0
        cnt = 0
        self.handle_move(value=0.01, key="w")  # 重置箭头指向为视角方向
        time.sleep(0.6)
        arrow_temp = self.arrow_0
        final_arrow = self.img.image_rotate(arrow_temp, -value)
        while cnt < 4:
            arrow_temp = self.take_arrow()
            ang = self.cal_ang(arrow_temp, final_arrow)
            sub = 360 - ang
            sub = (sub + 180) % 360 - 180
            sub = sub if sub != 0 else 1e-9
            log.info(f"开始旋转视角，计算角度ang:{ang}，旋转角度sub:{sub}")
            # KeyboardEvent.keyboard_press("caps_lock", 0.2)
            # time.sleep(1)
            self.mouse_event.mouse_move(sub)
            self.handle_move(value=0.01, key="w")
            cnt += 1
            if abs(sub) <= 1:
                break
            time.sleep(0.6)

    def take_arrow(self):
        """
        截取小地图蓝色箭头，进行HSV颜色过滤
        """
        img = self.take_screenshot_arrow()
        # 转换到HSV颜色空间
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([93, 120, 60])
        upper_blue = np.array([97, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        result_img = cv2.bitwise_and(img, img, mask=mask)

        return result_img

    def take_screenshot_arrow(self):
        """
        截取小地图蓝色箭头
        """
        # 小地图中心 460-320=140,345-194=151
        screenshot = self.img.take_screenshot(
            offset=(125, 136, -1765, -914))[0]

        return screenshot

    def scroll(self, clicks: float):
        """
        说明：
            控制鼠标滚轮滚动
        参数：
            :param clicks 滚动单位，正数为向上滚动
        """
        pyautogui.scroll(clicks)
        time.sleep(0.5)

    def handle_move(self, value, key, normal_run=False, last_key: str = ""):
        """
        移动，并处理疾跑
        """
        if normal_run:
            log.info(f"强制关闭疾跑normal_run:{normal_run}")
        if last_key == "e":
            self.technique_points_dialog()
            if not self.img.on_main_interface(timeout=0.2):
                fight_status = self.fight_elapsed()
                if not fight_status:
                    log.info('未进入战斗')
                else:
                    log.info('进入战斗')
                    self.fight_in_map = True

        self.run_fix_time = 0
        KeyboardController().press(key)
        # 固定ctrl两次取消疾跑
        log.info(f"last_step_run: {self.last_step_run}")
        if self.last_step_run:
            self.start_cancel_sprint_task()
            self.stop_cancel_sprint_task()

        start_time = time.perf_counter()
        allow_run = self.cfg.config_file.get("auto_run_in_map", False)
        add_time = True
        run_in_road = False
        temp_time = 0
        self.run_fixed = False  # 强制断开初始化为否

        value_before = value
        while time.perf_counter() - start_time < value:
            if value_before > 2 and not run_in_road and allow_run and not normal_run:
                self.move_run_fix(start_time)
                if time.perf_counter() - start_time > 1:
                    self.enable_run()
                    self.start_check_sprint_task()
                    run_in_road = True
                    temp_value = value_before
                    value = round((value_before - 1) / 1.53, 4) + 1
                    self.tatol_save_time += (temp_value - value)
                    self.last_step_run = True
            elif value_before <= 1 and allow_run and add_time and self.last_step_run:
                value = value_before + 0.07
                self.move_run_fix(start_time)
                add_time = False
                self.last_step_run = False
            elif value_before <= 2:
                self.move_run_fix(start_time)
                self.last_step_run = False
        self.stop_check_sprint_task()
        temp_time = time.perf_counter() - start_time
        KeyboardController().release(KeyboardKey.shift)
        KeyboardController().release(key)
        if allow_run:
            time.sleep(0.03)

        # 系统卡顿识别
        time_error_check = True
        if time_error_check and value >= 0.2:
            extra_time = temp_time - value
            if extra_time > 0.05:
                log.info(f"警告，此处出现系统卡顿，实际多移动{extra_time:.4f}秒，可能造成路线错误")
                self.time_error_cnt += 1

        # 暂不启用
        extra_fix = False
        if extra_fix:
            extra_time = temp_time - value
            extra_time = extra_time if not run_in_road else round(
                extra_time*1.53, 4)
            if extra_time > 0.05:
                log.info("强制断开疾跑")
                fix_start_time = time.perf_counter()
                key_dict = {'w': 's', 's': 'w', 'a': 'd', 'd': 'a'}
                if key in key_dict:
                    KeyboardController().press(key_dict.get(key))
                    while time.perf_counter() - fix_start_time < extra_time:
                        pass
                    KeyboardController().release(key_dict.get(key))
                    KeyboardController().press(key)
                    KeyboardController().release(key)

    async def async_cancel_sprint(self):
        """异步按下 Ctrl 两次，用于取消疾跑"""
        loop = asyncio.get_event_loop()
        for _ in range(2):
            if self.window.client == "客户端":
                await asyncio.sleep(0.03)
            else:
                await asyncio.sleep(0.08)
            await loop.run_in_executor(None, KeyboardController().tap, KeyboardKey.ctrl)
            log.info("按下 Ctrl")

    def start_cancel_sprint_task(self):
        """启动取消疾跑任务"""
        if self.thread_cancel_sprint and self.thread_cancel_sprint.is_alive():
            log.warning("取消疾跑任务已在运行，跳过启动")
            return
        self.ctrl_press = True
        self.thread_cancel_sprint = threading.Thread(
            target=self._run_async_cancel_sprint, daemon=True
        )
        self.thread_cancel_sprint.start()

    def stop_cancel_sprint_task(self):
        """停止取消疾跑任务"""
        self.ctrl_press = False
        if self.thread_cancel_sprint and self.thread_cancel_sprint.is_alive():
            self.thread_cancel_sprint.join()
            self.thread_cancel_sprint = None

    def _run_async_cancel_sprint(self):
        """运行异步任务，处理取消疾跑的逻辑"""
        asyncio.run(self.async_cancel_sprint())

    def is_running(self):
        """
        判断是否在疾跑状态
        """
        result = self.img.scan_screenshot(
            self.img.switch_run, (1720, 930, 0, 0))
        return result['max_val'] > 0.996

    async def async_check_sprint_status(self):
        """异步检测疾跑状态"""
        loop = asyncio.get_event_loop()
        count = 0
        while self.running and count < 2:
            await asyncio.sleep(0.12)
            is_running = await loop.run_in_executor(None, self.is_running)
            if not is_running:
                log.warning(f"疾跑未能成功开启，再尝试一次，当前{count + 1}次")
                await loop.run_in_executor(None, KeyboardController().press, KeyboardKey.shift)
                log.info("开启疾跑")
            else:
                log.info("疾跑已成功开启")
                break
            count += 1
        self.running = False

    def start_check_sprint_task(self):
        """启动检测疾跑任务"""
        if self.thread_check_sprint and self.thread_check_sprint.is_alive():
            log.warning("检测疾跑任务已在运行，跳过启动")
            return
        self.running = True
        self.thread_check_sprint = threading.Thread(
            target=self._run_async_check_sprint, daemon=True
        )
        self.thread_check_sprint.start()

    def stop_check_sprint_task(self):
        """停止检测疾跑任务"""
        self.running = False
        if self.thread_check_sprint and self.thread_check_sprint.is_alive():
            self.thread_check_sprint.join()
            self.thread_check_sprint = None
        log.info("检测任务已停止")

    def _run_async_check_sprint(self):
        """运行异步任务，处理检测疾跑的逻辑"""
        asyncio.run(self.async_check_sprint_status())

    def enable_run(self):
        """强制开启疾跑"""
        log.info("调用enable_run")
        if not self.is_running():
            KeyboardController().press(KeyboardKey.shift)
            log.info("开启疾跑")

    def move_run_fix(self, start_time, time_limit=0.3):
        '''
        用于修复2.6更新后连续移动时，疾跑意外打开的情况。

        该方法用于检测当前疾跑状态，并在检测到疾跑意外激活时，模拟按下和释放 Shift 键来强制关闭疾跑。
        为了避免多次触发关闭操作，确保每次循环内只执行一次关闭操作。

        参数:
        - start_time: 循环开始时间。
        - time_limit: 限制检测逻辑的时间窗口，默认为 0.3 秒。
        '''
        # 测试
        return
        if not self.run_fixed:
            current_time = time.perf_counter()
            elapsed_time = current_time - start_time

            # 仅在前 0.3 秒内执行检测逻辑
            if elapsed_time <= time_limit:
                # 检查 run_fix_time 是否为 None 或时间差大于 0.1 秒
                if not self.run_fix_time or (current_time - self.run_fix_time) > 0.1:
                    # for _ in range(4):  # 强制断开检查最多4次，避免误判
                    result_run = self.img.scan_screenshot(
                        self.img.switch_run, (1720, 930, 0, 0))
                    # log.info(f"疾跑匹配度: {result_run['max_val']}")  # Testlog 用于测试图片匹配度
                    # 如果匹配度超过 0.996，强制断开疾跑
                    if result_run['max_val'] > 0.996:
                        log.info(f"疾跑匹配度: {result_run['max_val']}")
                        log.info("强制断开疾跑")
                        KeyboardController().press(KeyboardKey.shift)
                        time.sleep(0.05)
                        KeyboardController().release(KeyboardKey.shift)
                        self.run_fix_time = current_time  # 更新修复时间
                        self.run_fixed = True
            else:
                self.run_fixed = True

    def no_in_fight_status(self) -> bool:
        """必定不在战斗的图片，以完善战斗检测

        Returns:
            bool: 是否不在战斗
        """

        img_list = []
        img_list.append(cv2.imread("./picture/round.png"))
        for img in img_list:
            result = self.img.scan_screenshot(img)
            log.info(f"未战斗识别，匹配度{result['max_val']:.3f}，需要0.95")
            if result['max_val'] > 0.95:
                log.info("不在战斗中")
                return True
        return False

    def detect_fight_status(self, timeout=5.0):
        start_time = time.time()
        action_executed = False
        self.attack_once = False  # 检测fighting时仅攻击一次，避免连续攻击
        log.info("开始识别是否进入战斗")
        if self.no_in_fight_status():
            return False
        while time.time() - start_time < timeout:
            main_result = self.img.scan_screenshot(
                self.img.main_ui, offset=(0, 0, -1630, -800))
            doubt_result = self.img.scan_temp_screenshot(self.img.doubt_ui)
            # warn_result = self.img.scan_temp_screenshot(self.img.warn_ui)
            if main_result['max_val'] < 0.9:
                return True
            elif doubt_result["max_val"] > 0.92:
                action_executed = self.click_action(is_warning=False)
            # elif warn_result["max_val"] > 0.9:
            #     action_executed = self.click_action(is_warning=True)
            if action_executed:
                return action_executed
            time.sleep(0.5)
        log.info(f"结束识别，识别时长{timeout}秒，此处可能无敌人")
        return False

    def click_action(self, is_warning, timeout=8):
        """
        点击攻击怪物
        """
        if is_warning:
            log.info("识别到警告，等待怪物开战")
        else:
            log.info("识别到疑问，等待怪物开战")

        time.sleep(2)
        if not self.attack_once:
            self.mouse_event.click_center()
            self.attack_once = True
        start_time = time.time()
        while time.time() - start_time < timeout:
            main_result = self.img.scan_screenshot(self.img.main_ui)
            if main_result['max_val'] < 0.9:
                return True
            time.sleep(0.5)

    def fight_error_cnt(self, elapsed_time: int):
        """
        检测异常战斗
        """
        if elapsed_time < self.error_fight_threshold:
            self.error_fight_cnt += 1

    def fight_elapsed(self):
        """战斗时间

        返回：
            是否识别到敌人
        """
        detect_fight_status_time = self.cfg.config_file.get(
            "detect_fight_status_time", 15)
        fight_status = self.detect_fight_status(
            timeout=detect_fight_status_time)
        if not fight_status:
            # 结束识别，此处可能无敌人
            return False

        start_time = time.time()
        log.info("战斗开始")
        not_auto = cv2.imread("./picture/auto.png")
        not_auto_c = cv2.imread("./picture/not_auto.png")
        auto_switch = False
        auto_switch_clicked = False
        auto_check_cnt = 0
        first_auto_check = False
        screenshot_auto_check = None
        while True:
            result = self.img.scan_screenshot(self.img.main_ui)
            elapsed_time = time.time() - start_time
            if result["max_val"] > 0.92:
                points = self.img.img_center_point(
                    result, self.img.main_ui.shape)
                log.info(f"识别点位{points}")
                self.total_fight_time += elapsed_time
                self.fight_error_cnt(elapsed_time)
                elapsed_minutes = int(elapsed_time // 60)
                elapsed_seconds = elapsed_time % 60
                formatted_time = f"{elapsed_minutes}分钟{elapsed_seconds:.2f}秒"
                self.total_fight_cnt += 1
                colored_message = (
                    f"战斗完成,单场用时\033[1;92m『{formatted_time}』\033[0m")
                log.info(colored_message)
                match_details = f"匹配度: {result['max_val']:.2f} ({points[0]}, {points[1]})"
                log.info(match_details)

                # self.rotate()
                while not self.img.on_main_interface(timeout=2):
                    time.sleep(0.1)
                time.sleep(1)
                return True

            if not auto_switch and elapsed_time > 5:
                not_auto_result = self.img.scan_screenshot(not_auto)
                if not_auto_result["max_val"] > 0.95:
                    pyautogui.press('v')
                    log.info("开启自动战斗")
                    time.sleep(1)
                    auto_switch_clicked = True

                auto_switch = True

            if elapsed_time > 10 and auto_check_cnt < 2:
                if screenshot_auto_check is None:
                    screenshot_auto_check, * \
                        _ = self.img.take_screenshot(
                            offset=(40, 20, -1725, -800))
                if elapsed_time > 15:
                    if auto_check_cnt == 0:
                        first_auto_check = self.img.on_interface(check_list=[
                            screenshot_auto_check], timeout=1, threshold=0.97, offset=(40, 20, -1725, -800), allow_log=False)
                        auto_check_cnt += 1
                    if elapsed_time > 20 and first_auto_check and auto_check_cnt == 1:
                        auto_check_cnt += 1
                        if self.img.on_interface(check_list=[screenshot_auto_check], timeout=1, threshold=0.97, offset=(40, 20, -1725, -800), allow_log=False):
                            pyautogui.press('v')
                            log.info("开启自动战斗（通过行动条识别）")
                            time.sleep(1)
                            auto_switch_clicked = True

            if auto_switch_clicked and auto_switch and elapsed_time > 10:
                not_auto_result_c = self.img.scan_screenshot(not_auto_c)
                while not_auto_result_c["max_val"] > 0.95:
                    log.info(
                        f"开启自动战斗，识别'C'，匹配值：{not_auto_result_c['max_val']}")
                    pyautogui.press('v')
                    time.sleep(2)
                    not_auto_result_c = self.img.scan_screenshot(not_auto_c)

            if elapsed_time > 90:
                # self.mouse_event.click_target("./picture/auto.png", 0.98, False)
                self.mouse_event.click_target(
                    "./picture/continue_fighting.png", 0.98, False)
                self.mouse_event.click_target(
                    "./picture/defeat.png", 0.98, False)
                # self.mouse_event.click_target("./picture/map_4-2_point_3.png", 0.98, False)
                # self.mouse_event.click_target("./picture/orientation_close.png", 0.98, False)
                if elapsed_time > 600:
                    log.info("战斗超时")
                    return True
            time.sleep(0.5)

    def fighting(self):
        self.mouse_event.click_center()
        fight_status = self.fight_elapsed()

        if not fight_status:
            self.total_no_fight_cnt += 1
            log.info('未进入战斗')
            time.sleep(0.5)

    def rotate(self):
        """
        旋转视角，废弃
        """
        if self.need_rotate:
            KeyboardEvent.keyboard_press('w')
            time.sleep(0.7)
            self.asu.screen = self.img.take_screenshot()[0]
            ang = self.ang - self.asu.get_now_direc()
            ang = (ang + 900) % 360 - 180
            # self.mouse_move(ang * 10.2)

    def handle_await(self, value):
        """
        等待value秒后进行下一步
        """
        time.sleep(abs(value))

    def handle_b(self):
        """
        按下b键
        """
        pyautogui.press('b')
        time.sleep(1)
