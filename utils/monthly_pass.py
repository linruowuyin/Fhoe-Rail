import time
from datetime import datetime, timedelta
from typing import Optional

import cv2

from utils.log import log
from utils.config.config import ConfigurationManager
from utils.img import Img
from utils.mouse_event import MouseEvent


class MonthlyPass:
    WAIT_INTERVAL = timedelta(minutes=5)
    REFRESH_THRESHOLD = timedelta(seconds=30)

    class Status:
        CLAIMED = 1
        NO_PASS = 2
        NOT_FOUND = 3

    def __init__(self):
        self.cfg = ConfigurationManager()
        self.img = Img()
        self.mouse_event = MouseEvent()

        # 配置相关
        self.refresh_hour = self.cfg.config_file.get("refresh_hour", 4)
        self.refresh_minute = self.cfg.config_file.get("refresh_minute", 0)

        # 状态管理
        self.next_check_time: Optional[datetime] = None  # 下次检查时间
        self.last_check_time: Optional[datetime] = None  # 月卡检测时间
        self.monthly_pass_status: Optional[int] = None  # 月卡状态，0未检测，1有月卡并领取，2无月卡，3找不到与月卡图片相符的图
        self.have_monthly_pass = False  # 标志是否领取完月卡

    @staticmethod
    def _calculate_next_check(base_time: datetime, hour: int, minute: int) -> datetime:
        """计算下次检查时间"""
        next_time = base_time.replace(
            hour=hour, minute=minute, second=0, microsecond=0)
        return next_time if next_time > base_time else next_time + timedelta(days=1)

    def monthly_update_check_time(self):
        """更新下次检查时间"""
        self.next_check_time = self._calculate_next_check(
            datetime.now(), self.refresh_hour, self.refresh_minute
        )

    def monthly_pass_check(self):
        """执行月卡检查主逻辑"""
        current_time = datetime.now()
        self.refresh_hour = self.cfg.config_file.get("refresh_hour", 4)
        self.refresh_minute = self.cfg.config_file.get("refresh_minute", 0)

        if self._need_wait_before_check(current_time):
            self._wait_until_refresh_time()
            current_time = datetime.now()

        if self._should_perform_check(current_time):
            self._execute_check_flow(current_time)
            self._update_check_timestamps(current_time)

    def _need_wait_before_check(self, current: datetime) -> bool:
        """
        判断是否需要提前等待（修正跨天问题版本）
        生成最近的下一个目标时间，当剩余时间小于等待间隔时返回True
        """
        # 生成基准目标时间（当日）
        target_time = current.replace(
            hour=self.refresh_hour,
            minute=self.refresh_minute,
            second=0,
            microsecond=0
        )
        # 若当前时间已过当日目标时间
        if target_time < current:
            return False

        # 计算正数时间差
        delta = target_time - current
        # log.info(f"当前时间：{current}，下一个目标时间：{target_time}，时间差：{delta}")

        # 判断剩余时间是否小于等待间隔
        need_wait = delta < self.WAIT_INTERVAL
        # log.info(f"是否需要等待：{need_wait}")
        return need_wait

    def _wait_until_refresh_time(self):
        """等待到目标刷新时间"""
        log.info(f"等待至{self.refresh_hour:02d}:{self.refresh_minute:02d}后识别月卡")
        log.info(f"当前时间：{datetime.now()}")
        log.info(f"目标时间：{self.next_check_time}")
        while datetime.now() < self.next_check_time:
            time.sleep(2)

    def _should_perform_check(self, current: datetime) -> bool:
        """判断是否满足执行检查的条件"""
        # 需要执行一次月卡检查
        if self.next_check_time is None:
            self.monthly_update_check_time()

        # 1、首次检查强制执行
        if not self.last_check_time:
            return True
        # 2、当前时间大于等于下次检查时间
        return current >= self.next_check_time

    def _execute_check_flow(self, current: datetime):
        """执行检测流程"""
        time_diff = (current - self.next_check_time).total_seconds()
        if 0 <= time_diff < self.REFRESH_THRESHOLD.total_seconds():
            delay = 30
            log.info(f"等待{delay}秒后尝试识别点击月卡")
            self.try_click_pass(delay=delay)
        else:
            self.try_click_pass()

    def _update_check_timestamps(self, current: datetime):
        """更新时间记录"""
        # 更新上次检查时间
        self.last_check_time = current
        log.info(
            f"月卡检查时间更新至：{self.last_check_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 更新下次检查时间
        self.monthly_update_check_time()

    def check_for_monthly_pass(self) -> bool:
        """无月卡检测
        """
        log.info("判断是否存在月卡")
        target = cv2.imread("./picture/finish_fighting.png")
        result = self.img.scan_screenshot(target)
        if result["max_val"] > 0.92:
            points = self.img.img_center_point(result, target.shape)
            log.info(
                f"识别到主界面，无月卡，图片匹配度: {result['max_val']:.2f} ({points[0]}, {points[1]})")
            self.monthly_pass_status = self.Status.NO_PASS  # 月卡检查完成，无月卡
            return False
        else:
            return True

    def try_click_pass(self, threshold=0.91, delay=0):
        """
        说明：
            尝试点击月卡。
        """
        time.sleep(abs(delay))

        # 无月卡
        if not self.check_for_monthly_pass():
            return

        # 有月卡
        log.info("准备点击月卡")
        monthly_pass_pics = [
            ("./picture/monthly_pass_pic.png", "月卡下方文字部分"),
            ("./picture/monthly_pass_pic_2.png", "月卡动画中心图片")
        ]
        pic_data_check = cv2.imread("./picture/monthly_pass_pic_3.png")
        for pic_path, pic_desc in monthly_pass_pics:
            pic_data = cv2.imread(pic_path)
            result = self.img.scan_screenshot(pic_data)
            log.info(f"开始月卡识图{pic_path}，图片特征描述：{pic_desc}")
            if result["max_val"] > threshold:
                points = self.img.img_center_point(result, pic_data.shape)
                log.info(
                    f"点击月卡，图片匹配度: {result['max_val']:.2f} ({points[0]}, {points[1]})")
                self.mouse_event.click(points)
                time.sleep(5)  # 等待动画
                self._confirm_reward_claim()
                break
            else:
                log.info(
                    f"找不到相符的图，图片匹配度：{result['max_val']:.2f} 需要 > {threshold}")
        else:
            self.monthly_pass_status = self.Status.NOT_FOUND  # 月卡检查，找不到与月卡图片相符的图

    def _confirm_reward_claim(self):
        """确认奖励领取"""
        pic_data_check = cv2.imread("./picture/monthly_pass_pic_3.png")
        for _ in range(5):
            result = self.img.scan_screenshot(pic_data_check)
            if result["max_val"] > 0.91:
                log.info(f"找到月卡奖励图标，图片匹配度：{result['max_val']:.2f}")
                time.sleep(2)
                self.mouse_event.relative_click((50, 75))
                time.sleep(5)  # 等待动画
                break
            else:
                time.sleep(2)
        else:
            self.mouse_event.relative_click((50, 75))
            time.sleep(5)  # 等待动画
        self.have_monthly_pass = True
        self.monthly_pass_status = self.Status.CLAIMED  # 月卡检查，已领取
