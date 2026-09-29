"""战斗判定与处理 —— 从 Handle 拆出来的第一簇。

它拥有这一轮运行的战斗计数（`total_fight_cnt` / `total_fight_time` /
`error_fight_cnt` …），`Handle` 通过 `self.combat` 持有它。

拆分理由：这一簇有明确的边界（战斗的识别、进入、计时、记账），
内部只依赖 `cfg` / `img` / `mouse_event` 三个注入项，不碰 Handle 的其余状态。
`map_operations` 只通过 `handle_fighting` / `handle_e` 两个入口调它。
"""

import time

from utils.core.exceptions import CustomException
from utils.core.log import log
from utils.core.thresholds import (
    ACTION_BAR,
    AUTO_OFF_ICON,
    CANCEL_BUTTON,
    CONTINUE_FIGHTING,
    DEFEAT,
    DOUBT_ICON,
    MAIN_INTERFACE,
    MAIN_INTERFACE_STRICT,
    QIQIAO_ICON,
    QIQIAO_LAB,
    ROUND_DISABLE,
    ROUND_ICON,
    SNACK_CRAFT_BUTTON,
    TECHNIQUE_DIALOG,

)
from utils.drivers.keyboard_event import KeyboardEvent
from utils.vision.img import Img


class Combat:
    """战斗判定与结算。

    :param cfg: ConfigurationManager
    :param img: 识图对象（Img 门面）
    :param mouse_event: 鼠标动作执行者
    """

    def __init__(self, cfg, img, mouse_event):
        self.cfg = cfg
        self.img = img
        self.mouse_event = mouse_event

        self.current_fighting_index = 0
        self.fighting_count = 0
        self.auto_final_fight_e_cnt = 0
        self.attack_once = 0
        self.total_fight_cnt = 0
        self.total_no_fight_cnt = 0
        self.total_fight_time = 0
        self.error_fight_cnt = 0
        self.error_fight_threshold = 3  # 战斗时间小于此值记为「异常战斗」
        self.snack_used = 0
        self.fight_in_map = False  # 地图内意外战斗


    def reset(self):
        """重置一轮锄地的战斗计数（Map.reset_round_count 调它）。"""
        self.current_fighting_index = 0
        self.fighting_count = 0
        self.auto_final_fight_e_cnt = 0
        self.attack_once = False
        self.total_fight_cnt = 0
        self.total_no_fight_cnt = 0
        self.total_fight_time = 0
        self.error_fight_cnt = 0
        self.snack_used = 0

    def handle_fighting(self, value):
        """
        处理战斗
        """
        if value == 1:  # 战斗
            self.current_fighting_index += 1
            auto_final_fight_e_cnt_max = self.cfg.config_file.get(
                "auto_final_fight_e_cnt"
            )
            if (
                self.cfg.config_file.get("auto_final_fight_e", False)
                and self.current_fighting_index == self.fighting_count
                and self.auto_final_fight_e_cnt < auto_final_fight_e_cnt_max
            ):
                self.auto_final_fight_e_cnt += 1
                log.info("地图最后一个fighting:1，改为使用e")
                self.handle_e(value)
            else:
                self.fighting()
        elif value == 2:  # 打障碍物
            self.mouse_event.click_at_cursor()  # 打障碍物：点击当前目标
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
        KeyboardEvent.keyboard_press("e")
        time.sleep(0.25)
        self.technique_points_dialog()

        if value == 1:
            time.sleep(1)
            self.mouse_event.click_center()
            fight_status = self.fight_elapsed()
            if not fight_status:
                log.info("未进入战斗")
        elif value == 2:
            pass

        time.sleep(0.05)

    def technique_points_dialog(self):
        """
        秘技点数对话框
        """
        if not self.img.on_main_interface(timeout=0.0, allow_log=True):
            time.sleep(0.5)
            image_a = Img.get_img("./picture/eat.png")
            result_a = self.img.scan_screenshot(image_a)
            if result_a["max_val"] > TECHNIQUE_DIALOG:
                allow_fight_e_buy_prop = self.cfg.config_file.get(
                    "allow_fight_e_buy_prop", False
                )
                if allow_fight_e_buy_prop:
                    allow_buy = False
                    round_disable = Img.get_img("./picture/round_disable.png")
                    if self.img.on_interface(
                        check_list=[round_disable],
                        timeout=0.5,
                        interface_desc="无法购买",
                        threshold=ROUND_DISABLE,
                    ):
                        pass
                    else:
                        food_lab = Img.get_img("./picture/qiqiao_lab.png")
                        food_icon = Img.get_img("./picture/qiqiao.png")
                        find = False
                        drag = 0
                        while not find and drag < 4:
                            if self.img.on_interface(
                                check_list=[food_icon],
                                timeout=2,
                                interface_desc="奇巧零食图片",
                                threshold=QIQIAO_ICON,
                                offset=(900, 300, -400, -300),
                            ):
                                find = True
                                for _ in range(2):
                                    self.img.click_target(
                                        "./picture/qiqiao.png",
                                        QIQIAO_ICON,
                                        True,
                                        2,
                                        (900, 300, -400, -300),
                                        False,
                                    )
                                    if self.img.on_interface(
                                        check_list=[food_lab],
                                        timeout=2,
                                        interface_desc="奇巧零食",
                                        threshold=QIQIAO_LAB,
                                    ):
                                        time.sleep(0.1)
                                        self.img.click_target(
                                            "./picture/round.png", SNACK_CRAFT_BUTTON, timeout=8
                                        )
                                        self.snack_used += 1
                                        time.sleep(0.5)
                                        allow_buy = True
                            else:
                                log.info("下滑查找零食")
                                self.mouse_event.mouse_drag(1460, 450, 1460, 330)
                                time.sleep(0.5)
                                drag += 1
                        time.sleep(1)
                    self.img.click_target(
                        "./picture/cancel.png", CANCEL_BUTTON, timeout=2
                    )
                    time.sleep(0.1)
                    if allow_buy:
                        log.info("补E")
                        time.sleep(0.25)
                        KeyboardEvent.keyboard_press("e")
                        log.info("补E结束")
                        time.sleep(0.25)
                else:
                    self.img.click_target(
                        "./picture/cancel.png", CANCEL_BUTTON, timeout=2
                    )
                    time.sleep(0.1)

    def no_in_fight_status(self) -> bool:
        """必定不在战斗的图片，以完善战斗检测

        Returns:
            bool: 是否不在战斗
        """

        img_list = []
        img_list.append(Img.get_img("./picture/round.png"))
        for img in img_list:
            result = self.img.scan_screenshot(img)
            log.info(f"未战斗识别，匹配度{result['max_val']:.3f}，需要{ROUND_ICON}")
            if result["max_val"] > ROUND_ICON:
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
                self.img.main_ui, offset=(0, 0, -1630, -800)
            )
            doubt_result = self.img.scan_temp_screenshot(self.img.doubt_ui)
            # warn_result = self.img.scan_temp_screenshot(self.img.warn_ui)
            if main_result["max_val"] < MAIN_INTERFACE:
                return True
            elif doubt_result["max_val"] > DOUBT_ICON:
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
            if main_result["max_val"] < MAIN_INTERFACE:
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
            "detect_fight_status_time", 15
        )
        fight_status = self.detect_fight_status(timeout=detect_fight_status_time)
        if not fight_status:
            # 结束识别，此处可能无敌人
            return False

        start_time = time.time()
        log.info("战斗开始")
        not_auto = Img.get_img("./picture/auto.png")
        not_auto_c = Img.get_img("./picture/not_auto.png")
        auto_switch = False
        auto_switch_clicked = False
        auto_check_cnt = 0
        first_auto_check = False
        screenshot_auto_check = None
        while True:
            result = self.img.scan_screenshot(self.img.main_ui)
            elapsed_time = time.time() - start_time
            if result["max_val"] > MAIN_INTERFACE_STRICT:
                points = self.img.img_center_point(result, self.img.main_ui.shape)
                log.info(f"识别点位{points}")
                self.total_fight_time += elapsed_time
                self.fight_error_cnt(elapsed_time)
                elapsed_minutes = int(elapsed_time // 60)
                elapsed_seconds = elapsed_time % 60
                formatted_time = f"{elapsed_minutes}分钟{elapsed_seconds:.2f}秒"
                self.total_fight_cnt += 1
                colored_message = (
                    f"战斗完成,单场用时\033[1;92m『{formatted_time}』\033[0m"
                )
                log.info(colored_message)
                match_details = (
                    f"匹配度: {result['max_val']:.2f} ({points[0]}, {points[1]})"
                )
                log.info(match_details)

                # self.rotate()
                while not self.img.on_main_interface(timeout=2):
                    time.sleep(0.1)
                time.sleep(1)
                return True

            if not auto_switch and elapsed_time > 5:
                not_auto_result = self.img.scan_screenshot(not_auto)
                if not_auto_result["max_val"] > AUTO_OFF_ICON:
                    KeyboardEvent.keyboard_press("v")
                    log.info("开启自动战斗")
                    time.sleep(1)
                    auto_switch_clicked = True

                auto_switch = True

            if elapsed_time > 10 and auto_check_cnt < 2:
                if screenshot_auto_check is None:
                    screenshot_auto_check, *_ = self.img.take_screenshot(
                        offset=(40, 20, -1725, -800)
                    )
                if elapsed_time > 15:
                    if auto_check_cnt == 0:
                        first_auto_check = self.img.on_interface(
                            check_list=[screenshot_auto_check],
                            timeout=1,
                            threshold=ACTION_BAR,
                            offset=(40, 20, -1725, -800),
                            allow_log=False,
                        )
                        auto_check_cnt += 1
                    if elapsed_time > 20 and first_auto_check and auto_check_cnt == 1:
                        auto_check_cnt += 1
                        if self.img.on_interface(
                            check_list=[screenshot_auto_check],
                            timeout=1,
                            threshold=ACTION_BAR,
                            offset=(40, 20, -1725, -800),
                            allow_log=False,
                        ):
                            KeyboardEvent.keyboard_press("v")
                            log.info("开启自动战斗（通过行动条识别）")
                            time.sleep(1)
                            auto_switch_clicked = True

            if auto_switch_clicked and auto_switch and elapsed_time > 10:
                not_auto_result_c = self.img.scan_screenshot(not_auto_c)
                while not_auto_result_c["max_val"] > AUTO_OFF_ICON:
                    log.info(
                        f"开启自动战斗，识别'C'，匹配值：{not_auto_result_c['max_val']}"
                    )
                    KeyboardEvent.keyboard_press("v")
                    time.sleep(2)
                    not_auto_result_c = self.img.scan_screenshot(not_auto_c)

            if elapsed_time > 90:
                # self.img.click_target("./picture/auto.png", 0.98, False)
                self.img.click_target(
                    "./picture/continue_fighting.png", CONTINUE_FIGHTING, False
                )
                self.img.click_target("./picture/defeat.png", DEFEAT, False)
                # self.img.click_target("./picture/map_4-2_point_3.png", 0.98, False)
                # self.img.click_target("./picture/orientation_close.png", 0.98, False)
                if elapsed_time > 600:
                    log.info("战斗超时")
                    return True
            time.sleep(0.5)

    def fighting(self):
        self.mouse_event.click_center()
        fight_status = self.fight_elapsed()

        if not fight_status:
            self.total_no_fight_cnt += 1
            log.info("未进入战斗")
            time.sleep(0.5)
