import os
from utils.config import ConfigurationManager


class MapInfo:
    def __init__(self):
        self.map_versions = self.read_maps_versions()
        self.cfg = ConfigurationManager()
        self.map_list = MapInfo.read_maps(
            self.cfg.config_file.get("map_version", "default"))[0]
        self.map_list_map = MapInfo.read_maps(
            self.cfg.config_file.get("map_version", "default"))[1]
        self.map_version = MapInfo.read_maps(
            self.cfg.config_file.get("map_version", "default"))[2]

    @staticmethod
    def read_maps_versions(map_dir: str = "./map") -> list:
        """
        读取地图版本
        """
        map_versions = [
            f for f in os.listdir(map_dir) if os.path.isdir(os.path.join(map_dir, f))
        ]
        return map_versions

    @staticmethod
    def read_maps(map_version: str, map_dir: str = './map') -> tuple:
        """
        读取地图文件
        """
        map_version_dir = os.path.join(map_dir, map_version)
        json_files = MapInfo.get_json_files(map_version_dir)
        map_list_map = MapInfo.process_json_files(
            map_version, json_files, map_dir)
        return json_files, map_list_map, map_version

    @staticmethod
    def get_json_files(map_version_dir: str) -> list:
        """
        获取指定目录下的 JSON 文件列表
        """
        json_files = [f for f in os.listdir(
            map_version_dir) if f.endswith('.json')]
        return MapInfo.sort_json_files(json_files)

    @staticmethod
    def sort_json_files(json_files: list) -> list:
        """
        对 JSON 文件列表进行排序
        """
        return sorted(json_files, key=lambda x: [int(y) for y in x.replace('-', '_').replace('.', '_').split('_')[1:-1]])

    @staticmethod
    def process_json_files(map_version: str, json_files: list, map_dir: str) -> dict:
        """
        处理 JSON 文件并生成 map_list_map
        """
        map_list_map = {}
        for map_file in json_files:
            map_data = MapInfo.read_map_data(map_version, map_file, map_dir)
            key1, key2 = MapInfo.extract_keys(map_file)
            key2_front = key2[:key2.index('_')]
            value = map_list_map.get(key1, {})
            format_map_data_first_name = MapInfo.format_map_data_first_name(
                key1, key2_front, map_data["name"])
            value[key2] = [map_data["name"], format_map_data_first_name]
            map_list_map[key1] = value
        return map_list_map

    @staticmethod
    def read_map_data(map_version: str, map_file: str, map_dir: str) -> dict:
        """
        读取单个地图文件的数据
        """
        return ConfigurationManager.read_json_file(f"{map_dir}/{map_version}/{map_file}")

    @staticmethod
    def extract_keys(map_file: str) -> tuple:
        """
        从文件名中提取 key1 和 key2
        """
        key1 = map_file[map_file.index('_') + 1:map_file.index('-')]
        key2 = map_file[map_file.index('-') + 1:map_file.index('.')]
        return key1, key2

    @staticmethod
    def format_map_data_first_name(key1: str, key2_front: str, map_name: str) -> str:
        """
        格式化地图数据的第一个名称
        """
        map_data_first_name = map_name.replace(' ', '')
        map_data_first_name = map_data_first_name[:map_data_first_name.index(
            '-')]
        return f"{key1}-{key2_front} {map_data_first_name}"
