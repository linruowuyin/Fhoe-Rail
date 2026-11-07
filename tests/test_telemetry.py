"""utils/core/telemetry.py —— run_id 与 JSONL 运行遥测。

钉三件事：事件行格式（ts/run_id/kind/fields）、start/end_run 生命周期、
写失败静默吞掉（遥测绝不能干扰跑图 —— get_ver 的教训：埋在热路径的代码
一旦抛异常会从每个调用点冒出来）。
"""

import json

import pytest

import utils.core.telemetry as telemetry
from utils.core.telemetry import current_run_id, end_run, event, new_run_id, start_run


@pytest.fixture(autouse=True)
def _reset_run_state():
    """每个测试从无 run 状态开始，结束后也清掉，避免串味。"""
    telemetry._run_id = ""
    yield
    telemetry._run_id = ""


class TestRunId:
    def test_format_is_stamp_plus_random_suffix(self):
        rid = new_run_id()
        stamp, suffix = rid.rsplit("-", 1)
        assert len(stamp) == 15 and stamp[8] == "-"  # YYYYmmdd-HHMMSS
        assert len(suffix) == 4 and int(suffix, 16) >= 0

    def test_two_ids_differ_even_in_same_second(self):
        assert new_run_id() != new_run_id()


class TestRunLifecycle:
    def test_start_run_sets_run_id_and_writes_event(self, isolated_cwd):
        rid = start_run(mode="test")
        assert current_run_id() == rid
        rows = (isolated_cwd / "logs" / "telemetry.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        row = json.loads(rows[0])
        assert row["kind"] == "run_start"
        assert row["run_id"] == rid
        assert row["mode"] == "test"
        assert "ts" in row

    def test_end_run_writes_event_with_same_run_id(self, isolated_cwd):
        rid = start_run()
        end_run()
        rows = (isolated_cwd / "logs" / "telemetry.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        assert [json.loads(r)["kind"] for r in rows] == ["run_start", "run_end"]
        assert all(json.loads(r)["run_id"] == rid for r in rows)

    def test_second_start_run_replaces_run_id(self, isolated_cwd):
        first = start_run()
        second = start_run()
        assert first != second
        assert current_run_id() == second


class TestEvent:
    def test_event_row_shape(self, isolated_cwd):
        start_run()
        event("map_end", map="map_1-1_1", duration=12.3)
        row = json.loads(
            (isolated_cwd / "logs" / "telemetry.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[-1]
        )
        assert row["kind"] == "map_end"
        assert row["map"] == "map_1-1_1"
        assert row["duration"] == 12.3
        assert row["run_id"] == current_run_id()

    def test_event_without_run_uses_empty_run_id(self, isolated_cwd):
        event("map_load", duration=1.0)
        row = json.loads(
            (isolated_cwd / "logs" / "telemetry.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        assert row["run_id"] == ""

    def test_write_failure_is_silently_swallowed(self, isolated_cwd, monkeypatch):
        """磁盘满/权限问题都不能把异常抛进跑图主流程。"""
        start_run()
        (isolated_cwd / "logs" / "telemetry.jsonl").write_text("[]", encoding="utf-8")
        # open 指向目录，append 必然失败
        (isolated_cwd / "logs" / "blocked").mkdir()
        monkeypatch.setattr(telemetry, "TELEMETRY_PATH", str(isolated_cwd / "logs" / "blocked"))
        event("map_end", map="x")  # 不应抛出
