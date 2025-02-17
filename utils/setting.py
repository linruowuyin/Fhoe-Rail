from .config import ConfigurationManager
from .log import log
from .calculated import Calculated
from .time_utils import TimeUtils
import questionary
import re
from .map_info import MapInfo

class Setting:
    def __init__(self):
        self.cfg = ConfigurationManager()
        self.map_info = MapInfo()
        self.calculated = Calculated()
        self.time_mgr = TimeUtils()
        self.CONFIG_FILE_NAME = ConfigurationManager.CONFIG_FILE_NAME
        self.config = self.cfg.load_config()  # 加载配置文件并缓存
        self.map_versions = self.map_info.read_maps_versions()  # 加载地图版本并缓存

    def set_config(self, slot: str = "start"):
        while True:
            questions = self.get_questions_for_slot(slot)
            if not questions:
                log.info(f"错误的set_config参数: {slot}")
                return

            choices = []
            for question in questions:
                # 处理动态标题
                title = question.get('dynamic_title', lambda _: question['title'])(self.config)
                
                # 处理动态选项
                choices_dict = question['choices'](self.config, self.map_info) if callable(question['choices']) else question['choices']
                
                # 获取当前值
                current_value = self.config.get(question['config_key'])
                
                # 特殊处理
                if question['config_key'] == 'forbid_map':
                    display_value = ', '.join(current_value) if current_value else '无'
                else:
                    # 正常配置
                    inverted_choices = {v: k for k, v in choices_dict.items()}
                    display_value = inverted_choices.get(current_value, "未设置" if current_value is None else "未知值")

                choices.append(f"{title}------({display_value})")

            choices.append("【返回】")

            answer = questionary.select(
                "请选择要修改的设置:",
                choices=choices
            ).ask()

            if answer == "【返回】":
                return

            selected_title = answer.split("------")[0]
            selected_question = next(q for q in questions if 
                q.get('dynamic_title', lambda _: q['title'])(self.config) == selected_title)

            if selected_question.get('config_key') == 'forbid_map':
                self.handle_special_config(selected_question, self.config, self.map_info)
                self.config = self.cfg.load_config()
            else:
                self.handle_normal_config(selected_question, self.config)
            ConfigurationManager.save_config(self.config)

    def handle_normal_config(self, question, config):
        """处理普通配置"""
        choices_dict = question['choices'](config, self.map_info) if callable(question['choices']) else question['choices']
        
        answer = questionary.select(
            question['title'],
            choices=list(choices_dict.keys())
        ).ask()
        
        if answer:
            config[question['config_key']] = choices_dict[answer]

    def handle_special_config(self, question, config, map_instance):
        """处理特殊配置"""
        while True:
            current_choices = question['choices'](config, map_instance)
            answer = questionary.select(
                question['dynamic_title'](config),
                choices=list(current_choices.keys())
            ).ask()

            if answer in ["【返回】", "back"]:
                break
                
            action = current_choices[answer]

            if action == "add":
                self.add_forbidden_map_flow(map_instance)
                config = ConfigurationManager.load_config()
            elif action == "remove":
                handler = question['handler']['remove']
                target_choices = handler['choices'](config, map_instance)
                selected = questionary.select(
                    handler['title'],
                    choices=list(target_choices.keys())+["【返回】"]
                ).ask()
                
                if selected and selected != "【返回】":
                    config["forbid_map"].remove(selected)
                    ConfigurationManager.modify_json_file(self.CONFIG_FILE_NAME, "forbid_map", config["forbid_map"])
            

    def get_pure_map_name(self, raw_name: str) -> str:
        """提取地图名"""
        cleaned = re.sub(r'^[\d-]+\s*', '', raw_name)
        match = re.match(r'^([^\s\-—–]+.*?)(?=\s*[-—–]|$)', cleaned)
        return match.group(1).strip() if match else cleaned.strip()

    def get_questions_for_slot(self, slot: str) -> list:
        """获取配置问题"""
        map_versions = self.map_info.read_maps_versions()
        try:
            self.map_info.read_maps_versions()
        except Exception as e:
            log.error(f"地图数据加载失败: {e}")
        default_questions = [
            {
                "title": "选择地图版本，default：疾跑，HuangQuan：黄泉专用",
                "choices": {version: version for version in map_versions},
                "config_key": "map_version",
            },
            {
                "title": "锄后系统设置",
                "choices": {"无操作": 0, "关机": 1, "注销": 2},
                "config_key": "auto_shutdown",
            },
            {
                "title": "地图最后一击自动秘技（不建议龙丹、驭空开启",
                "choices": {"关闭": False, "开启": True},
                "config_key": "auto_final_fight_e",
            },
            {
                "title": "优先星球",
                "choices": {
                    "空间站": "1",
                    "雅利洛": "2",
                    "仙舟": "3",
                    "匹诺康尼": "4",
                    "翁法罗斯": "5",
                },
                "config_key": "main_map",
            },
            {
                "title": "购买代币与过期邮包",
                "choices": {"不购买": False, "购买": True},
                "config_key": "allow_map_buy",
            },
            {
                "title": "购买秘技零食并合成零食",
                "choices": {"不购买": False, "购买": True},
                "config_key": "allow_snack_buy",
            },
            {
                "title": "获得翁法罗斯记忆代币",
                "choices": {"不获得": False, "获得": True},
                "config_key": "allow_memory_token",
            },
            {
                "title": "几点月卡刷新，默认4",
                "choices": {str(refresh_hour): refresh_hour for refresh_hour in range(24)},
                "config_key": "refresh_hour",
            },
            {
                "title": "几分月卡刷新，默认0",
                "choices": {
                    str(refresh_minute): refresh_minute
                    for refresh_minute in [0, 15, 30, 45]
                },
                "config_key": "refresh_minute",
            },
            {
                "title": "跳过对应地图（当前已跳过：{}）",
                "choices": lambda config, map_info: {
                    **{map: map for map in config.get("forbid_map", [])},
                    "【新增】": "add",
                    "【删除】": "remove",
                    "【返回】": "back"
                },
                "dynamic_title": lambda config: f"跳过对应地图（当前已跳过：{len(config.get('forbid_map', []))}个）",
                "config_key": "forbid_map",
                "handler": {
                    "add": {
                        "title": "新增跳过地图",
                        "choices": self.add_forbidden_map_flow
                    },
                    "remove": {
                        "title": "移除已跳过的地图",
                        "choices": lambda config, _: {
                            map: map for map in config.get("forbid_map", [])
                        }
                    },
                    "back":{
                        "choices": self.set_config
                    }
                }
            },
            {
                "title": "[仅该次运行有效]运行前重新校准视角",
                "choices": {"否": True, "是": False},
                "config_key": "angle_set",
            },
        ]

        slot_questions = {"start": default_questions, "start_rewrite": default_questions}

        return slot_questions.get(slot, [])

    def add_forbidden_map_flow(self, map_info: MapInfo):
        """添加跳过地图的两级菜单流程"""
        # 第一级：选择星球
        planet_choice = self._h_select_planet()
        if planet_choice in (None, "back"):
            return
        # 第二级：选择地图名称
        map_choice = self._h_select_clean_map(map_info, planet_choice)
        if map_choice in (None, "back"):
            return
        # 执行添加操作
        self._add_to_forbidden(map_info, planet_choice, map_choice)

    def _h_select_planet(self):
        """星球选择菜单 (第一级)"""
        title = "选择要跳过的星球区域："
        opts = {
            "1 空间站「黑塔」": "1",
            "2 雅利洛-VI": "2", 
            "3 仙舟「罗浮」": "3",
            "4 匹诺康尼": "4",
            "5 翁法罗斯": "5",
            "返回": "back"
        }
        choice = questionary.select(title, choices=list(opts.keys())).ask()
        return opts.get(choice) if choice else None

    def _h_select_clean_map(self, map_info: MapInfo, main: str):
        """地图选择菜单 (第二级)"""
        # 获取当前星球的所有地图项
        map_version = self.config.get("map_version", "default")
        MapInfo.read_maps(map_version=map_version)
        raw_maps = map_info.map_list_map.get(main, {})

        if not raw_maps:
            log.warning(f"未找到 {main} 号星球的地图数据")
            return "back"

        # 生成选项
        unique_maps = {}
        for map_id, map_names in raw_maps.items():
            clean_name = self.get_pure_map_name(map_names[-1])
            unique_maps[clean_name] = unique_maps.get(clean_name, []) + [map_id]

        choices = [
            f"{name} ({len(ids)}个子地图)" 
            for name, ids in unique_maps.items()
        ] + ["返回上级"]

        # 显示选择菜单
        selected = questionary.select(
            "请选择要跳过的区域：",
            choices=choices
        ).ask()

        # 处理返回/退出
        if not selected or "返回" in selected:
            return "back"
        
        # 提取原始地图名称
        return selected.split(' ')[0] if ' ' in selected else selected

    def _add_to_forbidden(self, map_info: MapInfo, main: str, map_name: str):
        """将选择的地图添加到跳过列表"""
        target = [map_name]

        # 更新配置文件
        current_forbid = ConfigurationManager.read_json_file(self.CONFIG_FILE_NAME, False).get("forbid_map", [])
        updated_forbid = list(set(current_forbid + target))

        ConfigurationManager.modify_json_file(self.CONFIG_FILE_NAME, "forbid_map", updated_forbid)

        log.info(f"已添加子地图 {map_name} 到跳过列表")
