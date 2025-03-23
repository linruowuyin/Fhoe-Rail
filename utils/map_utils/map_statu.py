class MapStatu:
    def __init__(self):
        self.total_processing_time = 0  # 总处理时间
        self.teleport_click_count = 0  # 传送点击次数
        self.error_check_point = False  # 筑梦机关错误检查初始化
        self.skip_this_map = False  # 跳过这张地图，默认为否，一般用于过期邮包购买
        self.next_map_drag = False  # 下一张地图拖动
        self.start_map_name = ""  # 开始地图名称
        self.end_map_name = ""  # 结束地图名称
        self.normal_run = False  # 禁止疾跑
        self.map_f_key_error = []  # 存储F键错误的地图列表
        self.fight_in_map_list = []  # 存储有进入战斗的地图列表
        self.temp_point = ""  # 传送点
        self.total_time = 0  # 总时间
        self.total_fight_time = 0  # 总战斗时间
