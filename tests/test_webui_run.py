"""webui/server.py 的启动参数装配 —— 单图运行 / 区间运行。

不真的拉起进程：`Popen` 换成替身，只断言命令行参数的形状。
"""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_server():
    """按路径加载 webui/server.py（webui/ 不是包）。"""
    spec = importlib.util.spec_from_file_location(
        "webui_server_under_test_run", REPO_ROOT / "webui" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load_server()


@pytest.fixture
def spawned(monkeypatch):
    """拦下 Popen，返回它收到的命令行列表。"""
    calls = []

    class FakeProc:
        pid = 4321
        stdout = None

        def poll(self):
            return None

    def fake_popen(args, **kwargs):
        calls.append(args)
        return FakeProc()

    monkeypatch.setattr(server, "_is_admin", lambda: True)
    monkeypatch.setattr(server.subprocess, "Popen", fake_popen)
    # 强制走源码启动分支（打包分支用 exe 参数）
    monkeypatch.setattr(server, "FHOE_EXE", str(REPO_ROOT / "no-such-Fhoe-Rail.exe"))
    saved_proc = server._RUN["proc"]
    saved_mode = server._RUN["mode"]
    server._RUN["proc"] = None
    yield calls
    server._RUN["proc"] = saved_proc
    server._RUN["mode"] = saved_mode


class TestRunStartArguments:
    def test_range_mode_passes_both_ends(self, spawned):
        result = server.run_start("range", "3-5_1", "default", "3-5_2")

        assert result["ok"] is True
        args = spawned[-1]
        index = args.index("--range")
        assert args[index + 1:index + 3] == ["3-5_1", "3-5_2"]
        assert args[args.index("--map-version") + 1] == "default"

    def test_single_map_mode_is_unchanged(self, spawned):
        result = server.run_start("map", "3-5_1")

        assert result["ok"] is True
        args = spawned[-1]
        assert "--range" not in args
        assert args[args.index("--map") + 1] == "3-5_1"

    def test_range_requires_an_end(self, spawned):
        result = server.run_start("range", "3-5_1", "default", None)

        assert result["ok"] is False
        assert "终点" in result["error"]
        assert spawned == []
