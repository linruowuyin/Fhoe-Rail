# report.py
from utils.handle import Handle
from utils.log import log
from utils.map_utils.map_info import MapInfo
from utils.map_utils.map_statu import MapStatu
from utils.mouse_event import MouseEvent
from utils.time_utils import TimeUtils


class Report:
    def __init__(self, map_statu: MapStatu, map_info: MapInfo, handle: Handle, mouse_event: MouseEvent, time_utils: TimeUtils):
        """
        初始化 Report 类

        :param map_statu: MapStatu 实例，用于获取地图状态信息
        :param map_info: MapInfo 实例，用于获取地图信息
        :param handle: Handle 实例，用于获取战斗和疾跑信息
        :param mouse_event: MouseEvent 实例，用于获取鼠标事件信息
        :param time_mgr: TimeMgr 实例，用于时间格式化
        """
        self.map_statu = map_statu
        self.map_info = map_info
        self.handle = handle
        self.mouse_event = mouse_event
        self.time_mgr = time_utils

    def output_report(self):
        """输出报告"""

        # 总时间与总战斗时间
        log.info(
            f"结束该阶段的锄地，总计用时 {self.time_mgr.format_time(self.map_statu.total_time)}，总计战斗用时 {self.time_mgr.format_time(self.map_statu.total_fight_time)}")

        # 疾跑节约时间
        log.info(
            f"疾跑节约的时间为 {self.time_mgr.format_time(self.handle.tatol_save_time)}")

        # 地图信息
        log.info(
            f"开始地图：{self.map_statu.start_map_name}，结束地图：{self.map_statu.end_map_name}")

        # 战斗次数信息
        log.info(f"战斗次数：{self.handle.total_fight_cnt}")
        log.info(f"未战斗次数：{self.handle.total_no_fight_cnt}")
        log.info("未战斗次数在非黄泉地图首次锄地参考值：70-80，不作为漏怪标准，漏怪具体请在背包中对材料进行溯源查找")

        # 奇巧零食使用次数
        log.info(f"奇巧零食使用次数：{self.handle.snack_used}")

        # 异常相关信息
        # 异常战斗信息
        log.info(
            f"异常战斗识别（战斗时间 < {self.handle.error_fight_threshold} 秒）次数：{self.handle.error_fight_cnt}")

        # 筑梦机关检查
        if hasattr(self.map_statu, 'error_check_point') and self.map_statu.error_check_point:
            log.info("筑梦机关检查不通过，请将机关调整到正确的位置上")

        # 系统卡顿信息
        log.info(f"系统卡顿次数：{self.handle.time_error_cnt}")

        # 黄泉模式异常战斗
        if self.map_info.map_version == "HuangQuan" and hasattr(self.map_statu, 'fight_in_map_list'):
            log.info(f"黄泉模式，异常进入战斗：{self.map_statu.fight_in_map_list}")

        # 异常图片识别
        log.debug(f"匹配值小于0.99的图片：{self.mouse_event.img_search_val_dict}")

        # 异常 F 键地图
        if hasattr(self.map_statu, 'map_f_key_error'):
            log.info(f"异常 F 键地图：{self.map_statu.map_f_key_error}")
