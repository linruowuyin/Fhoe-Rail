import json
import os
import sys
import time

import orjson
from utils.singleton import SingletonMeta
from utils.log import log

class ConfigurationManager(metaclass=SingletonMeta):
    CONFIG_FILE_NAME = "config.json"

    def __init__(self):
        try:
            if ConfigurationManager.normalize_file_path(self.CONFIG_FILE_NAME) is None:
                log.info("配置文件不存在，正在初始化")
                ConfigurationManager.init_config_file(0, 0)
            else:
                config_path = ConfigurationManager.normalize_file_path(self.CONFIG_FILE_NAME)
                log.info(f"配置文件已存在，路径：{config_path}")
        except Exception as e:
            log.error(f"初始化配置文件时出现错误: {e}")

        self._config = None
        self._last_updated = None

    @property
    def config_file(self):
        """
        获取配置文件
        """
        # 检查配置是否需要更新
        if self._config is None or self._config_needs_update():
            self._update_config()
        return self._config

    def _update_config(self):
        """
        更新配置文件
        """
        self._config = ConfigurationManager.read_json_file(
            ConfigurationManager.CONFIG_FILE_NAME)
        self._last_updated = time.time()

    def _config_needs_update(self):
        """
        检查配置是否需要更新
        """
        if self._last_updated is None:
            return True

        file_modified_time = os.path.getmtime(
            ConfigurationManager.CONFIG_FILE_NAME)
        return file_modified_time > self._last_updated

    @classmethod
    def save_config(cls, config: dict):
        """
        保存配置文件
        """
        with open(cls.CONFIG_FILE_NAME, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)

    @classmethod
    def load_config(cls) -> dict:
        """
        读取配置文件
        """
        try:
            with open(cls.CONFIG_FILE_NAME, "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            print(f"配置文件格式有误，请检查 JSON 格式是否正确: {e}")
            return {}
        except Exception as e:
            print(f"读取配置文件时出现未知错误: {e}")
            return {}

    @staticmethod
    def normalize_file_path(filename):
        """
        寻找文件路径，仅在当前目录下查找
        """
        # 在当前目录下读取文件
        current_dir = os.getcwd()
        file_path = os.path.join(current_dir, filename)
        return file_path if os.path.exists(file_path) else None

    @staticmethod
    def read_json_file(filename: str, path=False) -> tuple[dict, str]:
        """
        说明：
            读取文件
        参数：
            :param filename: 文件名称
            :param path: 是否返回路径
        """
        # 找到文件的绝对路径
        file_path = ConfigurationManager.normalize_file_path(filename)
        if file_path:
            with open(file_path, "rb") as f:
                content = f.read()
                if content.startswith(b'\xef\xbb\xbf'):
                    content = content[3:]
                data = orjson.loads(content)
                if path:
                    return data, file_path
                else:
                    return data
        else:
            ConfigurationManager.init_config_file(0, 0)
            return ConfigurationManager.read_json_file(filename, path)

    @staticmethod
    def modify_json_file(filename: str, key, value):
        """
        说明：
            写入文件
        参数：
            :param filename: 文件名称
            :param key: key
            :param value: value
        """
        # 先读，再写
        data, file_path = ConfigurationManager.read_json_file(
            filename, path=True)
        data[key] = value
        with open(file_path, "wb") as f:
            f.write(orjson.dumps(data))

    @staticmethod
    def config_keys(real_width=0, real_height=0):
        config_keys = {
            "version": "",
            "real_width": real_width,
            "real_height": real_height,
            "map_debug": False,
            "github_proxy": "",
            "rawgithub_proxy": "",
            "webhook_url": "",
            "start": False,
            "picture_version": "0",
            "star_version": "0",
            "open_map": "m",
            "script_debug": False,
            "auto_shutdown": 0,
            "taskkill_name": "",
            "auto_final_fight_e": True,
            "auto_final_fight_e_cnt": 20,
            "allow_fight_e_buy_prop": False,
            "auto_run_in_map": True,
            "detect_fight_status_time": 5,
            "map_version": "default",
            "main_map": "1",
            "allow_run_again": False,
            "allow_run_next_day": False,
            "allow_map_buy": False,
            "allow_snack_buy": False,
            "allow_memory_token": False,
            "refresh_hour": 4,
            "refresh_minute": 0,
            "forbid_map": [],
            "allowlist_mode": False,
            "allowlist_mode_once": False,
            "allowlist_map": [],
            "angle": "1.0",
            "angle_set": False
        }

        return config_keys

    @staticmethod
    def config_all_keys(real_width=0, real_height=0):
        all_key = ConfigurationManager.config_keys(
            real_width, real_height).keys()

        return all_key

    @classmethod
    def init_config_file(cls, real_width, real_height):
        if ConfigurationManager.normalize_file_path(cls.CONFIG_FILE_NAME) is None:
            with open(cls.CONFIG_FILE_NAME, "wb+") as f:
                f.write(
                    orjson.dumps(
                        cls.config_keys(real_width, real_height)
                    )
                )

    @classmethod
    def config_issubset(cls) -> bool:
        """检查是否配置中都包含了必要配置
        """
        all_keys = cls.config_all_keys()
        existing_keys = ConfigurationManager.read_json_file(
            cls.CONFIG_FILE_NAME, False).keys()

        return set(all_keys).issubset(existing_keys)

    @classmethod
    def ensure_config_complete(cls):
        """
        写入未找到配置的默认值
        """
        if not cls.config_issubset():
            print("配置文件不完整，正在写入默认配置")
            all_keys = cls.config_all_keys()
            existing_keys = ConfigurationManager.read_json_file(
                cls.CONFIG_FILE_NAME, False).keys()
            missing_keys = set(all_keys) - set(existing_keys)

            if missing_keys:
                initial_dict = cls.config_keys(real_width=0, real_height=0)
                for key in missing_keys:
                    ConfigurationManager.modify_json_file(
                        ConfigurationManager.CONFIG_FILE_NAME, key, initial_dict[key])

    @staticmethod
    def get_file(path, exclude, exclude_file=None, get_path=False):
        """
        获取文件夹下的文件
        """
        if exclude_file is None:
            exclude_file = []
        file_list = []

        exclude_set = set(exclude)

        for root, dirs, files in os.walk(path):
            if any(ex_dir in root for ex_dir in exclude_set):
                # 如果当前文件夹在排除列表中，则跳过该文件夹
                continue

            for file in files:
                if any(ex_file in file for ex_file in exclude_file):
                    # 如果当前文件在排除文件列表中，则跳过该文件
                    continue

                if get_path:
                    file_path = os.path.join(root, file)
                    file_list.append(file_path.replace("//", "/"))
                else:
                    file_list.append(file)

        return file_list

    @classmethod
    def main_start(cls):
        """写入未找到的默认配置"""
        cls.ensure_config_complete()

    @classmethod
    def main_start_rewrite(cls, setting):
        """写入需要询问的配置"""
        # from utils.setting import Setting
        setting.set_config(slot="start_rewrite")
        cls.ensure_config_complete()

    @classmethod
    def config_fix(cls):
        """运行前检查并修复配置"""
        config = cls.load_config()
        if config["map_version"] == "HuangQuan":
            config["allow_fight_e_buy_prop"] = True
        cls.save_config(config)
