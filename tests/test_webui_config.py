"""WebUI 保存 config.json 的按字段合并（webui/server.py::save_config_patch）。

回归的对象是「整份覆盖」：浏览器持有的是**打开配置页那一刻**的整份快照，保存时原样
写回，于是打开页面之后、别处写进 config.json 的改动会被静默抹掉。脚本每次启动都会写
config.json（`version` / 临时 `map_version` / `allowlist_mode_once` / `angle` …），
所以只要配置页开着跑过一次，点保存就会回滚那些值。
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_server():
    """加载 webui/server.py（webui/ 不是包，只能按路径加载）。"""
    spec = importlib.util.spec_from_file_location(
        "webui_server_under_test_config_patch", REPO_ROOT / "webui" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load_server()


@pytest.fixture
def cfg_path(tmp_path, monkeypatch):
    # 不用 config.json：conftest 的 isolated_cwd 已经在 tmp_path 放了一份
    path = tmp_path / "under-test-config.json"
    monkeypatch.setattr(server, "CONFIG_PATH", str(path))
    return path


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestSaveConfigPatch:
    def test_keeps_values_another_writer_added_after_the_page_loaded(self, cfg_path):
        """核心回归 —— 整份覆盖会让 version 退回页面打开时的旧值。"""
        cfg_path.write_text(
            json.dumps({"version": "4.5.0_260828", "allow_map_buy": False}),
            encoding="utf-8",
        )
        # 页面开着的时候，脚本把 version 更新了（print_version 每次启动都写）
        cfg_path.write_text(
            json.dumps({"version": "4.5.0_260901", "allow_map_buy": False}),
            encoding="utf-8",
        )

        # 用户只改了 allow_map_buy，提交的是相对快照的差量
        server.save_config_patch({"allow_map_buy": True}, [])

        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert data["allow_map_buy"] is True
        assert data["version"] == "4.5.0_260901", "脚本写的值不该被回滚"

    def test_untouched_keys_are_not_written(self, cfg_path):
        write(cfg_path, {"a": 1, "b": 2})
        server.save_config_patch({"a": 9}, [])
        assert json.loads(cfg_path.read_text(encoding="utf-8")) == {"a": 9, "b": 2}

    def test_removed_keys_are_dropped(self, cfg_path):
        write(cfg_path, {"a": 1, "b": 2})
        server.save_config_patch({}, ["b"])
        assert json.loads(cfg_path.read_text(encoding="utf-8")) == {"a": 1}

    def test_returns_applied_count(self, cfg_path):
        cfg_path.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
        assert server.save_config_patch({"a": 9}, ["b"]) == 2

    def test_missing_file_is_created(self, cfg_path):
        assert not cfg_path.exists()
        server.save_config_patch({"real_width": 1920}, [])
        assert json.loads(cfg_path.read_text(encoding="utf-8"))["real_width"] == 1920

    def test_unknown_key_is_rejected(self, cfg_path):
        cfg_path.write_text(json.dumps({"a": 1}), encoding="utf-8")
        with pytest.raises(ValueError, match="未知配置项"):
            server.save_config_patch({"打错的名字": 1}, [])
        assert json.loads(cfg_path.read_text(encoding="utf-8")) == {"a": 1}

    def test_corrupt_file_is_refused_instead_of_overwritten(self, cfg_path):
        """读不出来时必须报错，不能当成空配置合并 —— 那会把整份配置写没。"""
        cfg_path.write_text("{ 这不是 json", encoding="utf-8")
        with pytest.raises(ValueError, match="读不出来"):
            server.save_config_patch({"a": 1}, [])
        assert cfg_path.read_text(encoding="utf-8") == "{ 这不是 json"
