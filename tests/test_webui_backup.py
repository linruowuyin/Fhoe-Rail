"""webui/server.py 的时间戳备份（`_backup_file` / `_backup_if_changed`）。

钉住：**文件名带时间戳且保留 .json 后缀**、同秒重名加序号、按份数清理、
内容没变不备份、地图备份不落进 map/（校验器会把它当版本目录）。
"""

import datetime
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_server():
    spec = importlib.util.spec_from_file_location(
        "webui_server_under_test_backup", REPO_ROOT / "webui" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load_server()


@pytest.fixture
def fixed_now(monkeypatch):
    """把备份时间钉死，文件名可断言；同秒冲突也走 -02 分支。"""

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 24, 1, 30, 5)

    monkeypatch.setattr(server, "datetime", SimpleNamespace(datetime=FixedDateTime))


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "map" / "default").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def config_path(repo, monkeypatch):
    path = repo / "config.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    monkeypatch.setattr(server, "CONFIG_PATH", str(path))
    return path


def backup_names(directory):
    return sorted(os.listdir(directory))


class TestBackupFile:
    def test_config_backup_has_timestamp_and_json_suffix(self, repo, config_path, fixed_now):
        target = server._backup_file(str(config_path), "config")

        assert target == str(
            repo / "backups" / "config" / "config.20261024-013005-01.json"
        )
        assert json.loads(Path(target).read_text(encoding="utf-8")) == {"a": 1}

    def test_same_second_collision_gets_zero_padded_serial(
        self, repo, config_path, fixed_now
    ):
        server._backup_file(str(config_path), "config")
        second = server._backup_file(str(config_path), "config")

        assert Path(second).name == "config.20261024-013005-02.json"

    def test_config_keeps_last_ten(self, repo, config_path, fixed_now):
        for _ in range(12):
            server._backup_file(str(config_path), "config")

        names = backup_names(repo / "backups" / "config")
        assert len(names) == server.CONFIG_BACKUP_KEEP == 10
        assert "config.20261024-013005-01.json" not in names, "最旧的应被清掉"
        assert "config.20261024-013005-03.json" in names, "保留窗口的第一份"
        assert "config.20261024-013005-12.json" in names, "最新的应保留"

    def test_map_backup_goes_to_version_folder_not_into_map(
        self, repo, fixed_now
    ):
        map_path = repo / "map" / "default" / "map_1-1_0.json"
        map_path.write_text('{"name": "x"}', encoding="utf-8")

        target = server._backup_file(str(map_path), "map")

        assert target == str(
            repo
            / "backups"
            / "maps"
            / "default"
            / "map_1-1_0.20261024-013005-01.json"
        )
        assert not list((repo / "map").rglob("*.2026*")), "备份不能落在 map/ 下"

    def test_map_keeps_last_five(self, repo, fixed_now):
        map_path = repo / "map" / "default" / "map_1-1_0.json"
        map_path.write_text('{"name": "x"}', encoding="utf-8")
        for _ in range(6):
            server._backup_file(str(map_path), "map")

        names = backup_names(repo / "backups" / "maps" / "default")
        assert len(names) == server.MAP_BACKUP_KEEP == 5

    def test_missing_source_is_a_noop(self, repo, fixed_now):
        assert server._backup_file(str(repo / "nope.json"), "config") is None
        assert not (repo / "backups").exists()


class TestBackupIfChanged:
    def test_identical_content_is_not_backed_up(self, repo, config_path):
        assert server._backup_if_changed(str(config_path), {"a": 1}, "config") is False
        assert not (repo / "backups").exists()

    def test_changed_content_is_backed_up(self, repo, config_path, fixed_now):
        assert server._backup_if_changed(str(config_path), {"a": 2}, "config") is True
        assert (
            repo / "backups" / "config" / "config.20261024-013005-01.json"
        ).exists()

    def test_corrupt_file_is_backed_up_not_treated_as_unchanged(self, repo):
        path = repo / "config.json"
        path.write_text("{ broken", encoding="utf-8")
        assert server._backup_if_changed(str(path), {"a": 1}, "config") is True


class TestSaveConfigPatchBackups:
    def test_noop_save_does_not_create_a_backup(self, repo, config_path):
        server.save_config_patch({"a": 1}, [])

        assert not (repo / "backups").exists()

    def test_real_save_backs_up_the_old_content(self, repo, config_path, fixed_now):
        server.save_config_patch({"a": 2}, [])

        backup = repo / "backups" / "config" / "config.20261024-013005-01.json"
        assert json.loads(backup.read_text(encoding="utf-8")) == {"a": 1}
        assert json.loads(config_path.read_text(encoding="utf-8")) == {"a": 2}
