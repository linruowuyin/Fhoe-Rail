import time
import datetime

from utils.config.config import ConfigurationManager
from utils.log import log



class TimeUtils:
    def __init__(self):
        self.now = datetime.datetime.now()
        self.cfg = ConfigurationManager()

    @staticmethod
    def format_time(seconds):
        # 格式化时间
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours:.0f}小时{minutes:.0f}分{seconds:.1f}秒"
        elif minutes > 0:
            return f"{minutes:.0f}分{seconds:.1f}秒"
        else:
            return f"{seconds:.1f}秒"

    @staticmethod
    def day_init(days: list = None):
        """
        判断是否在指定天数内
        """
        if days is None:
            days = []
        today_weekday_num = datetime.datetime.now().weekday()
        in_day = today_weekday_num in days

        return in_day

    @staticmethod
    def get_target_datetime(hour, minute, second):
        now = datetime.datetime.now()
        target_date = now.date()
        target_time = datetime.datetime.combine(
            target_date, datetime.time(hour, minute, second))  # 设置目标时间

        return target_time

    @staticmethod
    def get_valid_hour():
        """
        获取有效的小时数
        """
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
                    log.debug("输入的小时数不合法，请输入0-23之间的数字。")
            except ValueError:
                log.debug(f"未输入一个有效的数字。使用默认值 {default_hour}")
                return default_hour

    @staticmethod
    def wait_and_run(minute=1, second=0):
        """
        等待并运行
        """
        hour = TimeUtils.get_valid_hour()
        target_time = TimeUtils.get_target_datetime(
            hour, minute, second)  # 计算目标时间
        time_diff = target_time - datetime.datetime.now()  # 计算目标时间与当前时间的时间差
        if time_diff.total_seconds() < 0:  # 如果目标时间已经过去，则设置为明天的这个时间
            target_time += datetime.timedelta(days=1)
            time_diff = target_time - datetime.datetime.now()
        wait_time = time_diff.total_seconds()  # 等待到目标时间
        log.info(f"将在 {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        log.info(f"需要等待 {wait_time:.0f} 秒")
        time.sleep(wait_time)

    def has_crossed_4am(self, start: datetime.datetime, end: datetime.datetime) -> bool:
        """
        检查是否从开始时间到结束时间跨越了凌晨4点
        """
        refresh_hour = self.cfg.config_file.get("refresh_hour", 4)
        refresh_minute = self.cfg.config_file.get("refresh_minute", 0)
        # 获取开始时间的凌晨4点
        start_4am = start.replace(
            hour=refresh_hour, minute=refresh_minute, second=0, microsecond=0)
        if start.hour >= refresh_hour and start.minute >= refresh_minute:
            # 如果开始时间在4点之后，则4点时间应该是下一天的4点
            start_4am += datetime.timedelta(days=1)

        return start < start_4am <= end
