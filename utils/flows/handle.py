from datetime import datetime
import random
import time


from utils.config.config import ConfigurationManager
from utils.core.exceptions import CustomException
from utils.flows.combat import Combat
from utils.flows.movement import Movement
from utils.flows.orientation import Orientation
from utils.flows.puzzle_exit import try_exit_puzzle
from utils.vision.img import Img
from utils.drivers.keyboard_event import KeyboardEvent
from utils.core.log import log
from utils.core.thresholds import (
    BATTLE_ESC_CHECK,
    F_ICON,
    SETTING_CONFIRM,
    SETTING_ICON,
    SETTING_OPTION,
    TECHNIQUE_CONSUMABLE,
)
from utils.drivers.mouse_event import MouseEvent
from utils.core.singleton import SingletonMeta
from utils.drivers.window import Window


class Handle(metaclass=SingletonMeta):
    def __init__(self):
        self.mouse_event = MouseEvent()
        self.img = Img()
        self.cfg = ConfigurationManager()
        self.window = Window()

        # 战斗计数（total_fight_cnt / error_fight_cnt / snack_used …）已归
        # self.combat 持有，见 flows/combat.py

        self.f_key_error = False  # F键错误



        #: 战斗判定与结算（见 flows/combat.py）
        self.combat = Combat(self.cfg, self.img, self.mouse_event)

        #: 移动与疾跑（见 flows/movement.py）
        self.movement = Movement(self.cfg, self.img, self.mouse_event, self.combat)

        #: 视角校准（见 flows/orientation.py；识别部分在 vision/arrow.py）
        self.orientation = Orientation(
            self.cfg, self.img, self.mouse_event, self.handle_move
        )

    def handle_space(self, value, key):
        """按下space键，延迟value秒后抬起"""
        KeyboardEvent.keyboard_press(key, value)

    def handle_caps(self, value):
        """按下space键，延迟value秒后抬起"""
        KeyboardEvent.keyboard_press("caps", value)

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
                KeyboardEvent.keyboard_press("f", delay=0.1)
                log.info(f"按下'F'，等待{delay}秒")
                time.sleep(delay)
            else:
                KeyboardEvent.keyboard_press("f", delay=0.1)
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
            "target": Img.get_img("./picture/sw.png"),
            "dream_pop": Img.get_img("./picture/F_DreamPop.png"),
            "teleport": Img.get_img("./picture/F_Teleport.png"),
            "space_anchor": Img.get_img("./picture/F_SpaceAnchor.png"),
            "dream_module": Img.get_img("./picture/F_DreamModule.png"),
            "listen": Img.get_img("./picture/F_Listen.png"),
            "dream_scape": Img.get_img("./picture/F_DreamScape.png"),
            "go_to": Img.get_img("./picture/F_Goto.png"),
        }

        start_time = time.time()
        log.info("扫描'F'图标")

        default_delay = value
        found_images = {}

        while time.time() - start_time < timeout:
            for count, (name, img) in enumerate(images.items(), start=1):
                result = (
                    self.img.scan_screenshot(img)
                    if count == 1
                    else self.img.scan_temp_screenshot(img)
                )
                if result["max_val"] > F_ICON:
                    found_images[name] = result["max_val"]
                    log.info(f"扫描'F'：{name}，匹配度：{result['max_val']:.3f}")

            if len(found_images) == 2 or (
                "target" in found_images and time.time() - start_time >= 2
            ):
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
        if "target" in found_images:
            if "dream_pop" in found_images:
                log.info("扫描到 梦泡充能")
                delay = 3
            elif "teleport" in found_images:
                log.info("扫描到 入画")
                use_absolute_time = False
                delay = 0
            elif "space_anchor" in found_images:
                log.info("扫描到 界域定锚")
                use_absolute_time = False
                delay = 0
                allow_press_f = False
            elif "dream_module" in found_images:
                log.info("扫描到 筑梦模块")
                delay = 4
            elif "listen" in found_images:
                log.info("扫描到 旁听")
                use_absolute_time = False
                delay = 0
                allow_press_f = False
            elif "dream_scape" in found_images:
                log.info("扫描到 梦境空间")
                delay = 5
            elif "go_to" in found_images:
                log.info("扫描到 前往")
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

    def back_to_main(self, delay=2.0):
        """
        检测并回到主界面
        恢复超时则停止运行，避免在未知界面继续执行路线并反复重试。
        """
        start_time = time.time()
        while not self.img.on_main_interface(
            timeout=2
        ):  # 检测是否出现左上角灯泡，即主界面检测
            if time.time() - start_time > 120:
                raise CustomException("回到主界面超时（120秒），请检查游戏界面后重试")
            # ESC 会取消已经打开的确认框，必须先处理它，再尝试按 ESC。
            if try_exit_puzzle(self.img, self.mouse_event):
                time.sleep(delay)
                continue
            KeyboardEvent.keyboard_press("esc")
            time.sleep(delay)
            if self.img.on_interface(
                check_list=[self.img.battle_esc_check],
                timeout=0.0,
                threshold=BATTLE_ESC_CHECK,
                offset=(0, 0, -1800, -970),
                allow_log=True,
            ):
                KeyboardEvent.keyboard_press("esc")
                time.sleep(2)
                self.combat.fight_elapsed()

    def handle_esc(self, value):
        """
        按下esc键，等待3秒后抬起
        """
        if value == 1:
            KeyboardEvent.tap_escape(random.uniform(0.09, 0.15))
            time.sleep(3)
        else:
            raise CustomException("map数据错误, esc参数只能为1")

    def auto_use_technique_consumable(self):
        """
        自动使用秘技消耗品（游戏内设置）
        Returns:
            bool: 是否成功设置
        """
        log.info("开始设置自动使用秘技消耗品")
        try:
            # 先返回主界面
            self.back_to_main()
            time.sleep(0.5)

            # 按下ESC打开菜单
            KeyboardEvent.keyboard_press("esc")
            time.sleep(2)

            # 通过识图，选择设置
            if not self.img.click_target("picture\\setting_icon.png", SETTING_ICON):
                log.warning("未找到设置图标")
                return False
            time.sleep(1)

            # 通过识图，选择其他设置
            if not self.img.click_target("picture\\setting_other.png", SETTING_OPTION):
                log.warning("未找到其他设置选项")
                return False
            time.sleep(0.5)

            # 向下滚动到秘技点不足时自动使用消耗品选项
            self.mouse_event.mouse_drag(
                1920 / 2, 1080 / 2, 1920 / 2, 1080 / 4, press_time=1
            )

            # 点击自动使用消耗品开关
            if not self.img.click_target(
                "picture\\auto_use_technique_consumable.png", TECHNIQUE_CONSUMABLE
            ):
                log.warning("未找到自动使用消耗品选项")
                return False
            time.sleep(1)

            # 通过识图，选择"是"确认
            if not self.img.click_target("picture\\setting_yes.png", SETTING_CONFIRM):
                log.warning("未找到确认按钮")
                return False
            time.sleep(0.5)

            log.info("自动使用秘技消耗品设置成功")
            # 返回主界面
            self.back_to_main()
            time.sleep(0.5)
            return True

        except Exception as e:
            log.error(f"设置自动使用秘技消耗品失败: {e}")
            return False

    def handle_num(self, value, key):
        """
        按下数字键，等待value秒后抬起
        """
        time.sleep(value)
        KeyboardEvent.keyboard_press(key, 0.3)

    def handle_main(self, value):
        """
        返回主界面
        """
        time.sleep(value)
        self.back_to_main(delay=0.1)
        time.sleep(2)

    # 不同电脑鼠标移动速度、放缩比、分辨率等不同，因此需要校准
    # 基本逻辑：每次正反转60度，然后计算实际转了几度，计算出误差比

    def scroll(self, clicks: float):
        """
        说明：
            控制鼠标滚轮滚动
        参数：
            :param clicks 滚动单位，正数为向上滚动
        """
        self.mouse_event.scroll(clicks)
        time.sleep(0.5)

    # 机器配置不高时，sleep时间过短，会导致误判
    # async def async_cancel_sprint(self):
    #     """异步按下 Ctrl 两次，用于取消疾跑"""
    #     loop = asyncio.get_event_loop()
    #     for _ in range(2):
    #         if self.window.client == "客户端":
    #             await asyncio.sleep(0.03)
    #         else:
    #             await asyncio.sleep(0.08)
    #         await loop.run_in_executor(None, KeyboardController().tap, KeyboardKey.ctrl)
    #         log.info("按下 Ctrl")

    # 疾跑相关逻辑回退2025.2.28版本
    # def start_cancel_sprint_task(self):
    #     """启动取消疾跑任务"""
    #     if self.thread_cancel_sprint and self.thread_cancel_sprint.is_alive():
    #         log.warning("取消疾跑任务已在运行，跳过启动")
    #         return
    #     self.ctrl_press = True
    #     self.thread_cancel_sprint = threading.Thread(
    #         target=self._run_async_cancel_sprint, daemon=True
    #     )
    #     self.thread_cancel_sprint.start()

    # 疾跑相关逻辑回退2025.2.28版本
    # def stop_cancel_sprint_task(self):
    #     """停止取消疾跑任务"""
    #     self.ctrl_press = False
    #     if self.thread_cancel_sprint and self.thread_cancel_sprint.is_alive():
    #         self.thread_cancel_sprint.join()
    #         self.thread_cancel_sprint = None

    # 疾跑相关逻辑回退2025.2.28版本
    # def _run_async_cancel_sprint(self):
    #     """运行异步任务，处理取消疾跑的逻辑"""
    #     asyncio.run(self.async_cancel_sprint())

    # 2025.6.5 疾跑依然有严重问题
    # def disable_run(self):
    #     """强制关闭疾跑"""
    #     log.info("调用disable_run")
    #     time.sleep(0.01)
    #     KeyboardController().press(KeyboardKey.shift)
    #     time.sleep(0.03)
    #     KeyboardController().release(KeyboardKey.shift)
    #     log.info("关闭疾跑")
    #     if self.is_key_pressed(0x10):
    #         log.info("当前 Shift 键状态：按下")
    #     else:
    #         log.info("当前 Shift 键状态：释放")

    def rotate(self):
        """
        旋转视角，废弃
        """
        if self.need_rotate:
            KeyboardEvent.keyboard_press("w")
            time.sleep(0.7)
            self.asu.screen = self.img.take_screenshot()[0]
            ang = self.ang - self.asu.get_now_direc()
            ang = (ang + 900) % 360 - 180
            # self.mouse_move(ang * 10.2)

    # --- 战斗：委派给 self.combat（见 flows/combat.py）----------------------

    def handle_fighting(self, value):
        """处理战斗。"""
        return self.combat.handle_fighting(value)

    def handle_e(self, value):
        """按下 e 键。"""
        return self.combat.handle_e(value)


    # --- 视角：委派给 self.orientation（见 flows/orientation.py）---------------

    def handle_view_set(self, value):
        """设置初始视角。"""
        return self.orientation.handle_view_set(value)

    def handle_view_reset(self, value):
        """重置视角。"""
        return self.orientation.handle_view_reset(value)

    def handle_view_rotate(self, value):
        """旋转视角至 value 度。"""
        return self.orientation.handle_view_rotate(value)

    def set_angle(self, ang=None):
        """校准视角旋转。"""
        return self.orientation.set_angle(ang)

    # --- 移动：委派给 self.movement（见 flows/movement.py）-------------------

    def handle_move(self, value, key, normal_run=False, last_key: str = ""):
        """移动并处理疾跑。"""
        return self.movement.handle_move(value, key, normal_run, last_key)

    def handle_await(self, value):
        """
        等待value秒后进行下一步
        """
        time.sleep(abs(value))

    def handle_b(self):
        """
        按下b键
        """
        KeyboardEvent.keyboard_press("b")
        time.sleep(1)

    def handle_click_floor(self, floor_idx: int):
        """
        点击楼层
        """
        y_base = 970
        x_ratio = 3.4
        # 计算偏移量
        y_ratio = float((y_base - floor_idx * 86) / 1080 * 100)
        self.mouse_event.relative_click((x_ratio, y_ratio))
