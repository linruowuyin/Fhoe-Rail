"""WebUI 的图片探针（webui/server.py::/api/probe*）。

门禁在**服务端**：探针能读到你的游戏画面，只把前端按钮藏起来挡不住直接 fetch。
所以这里起一个真跑在 127.0.0.1 上的 server，验 403 / 409 / 503 / 404 / 400 / 200 各条路。
抓帧那一段换成替身，不碰游戏、不碰屏幕。
"""

import base64
import importlib.util
import json
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_server():
    """加载 webui/server.py（webui/ 不是包，只能按路径加载）。"""
    spec = importlib.util.spec_from_file_location(
        "webui_server_under_test_probe", REPO_ROOT / "webui" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load_server()


def free_port():
    """要一个当前空闲的端口号（只借它的号，不占着）。"""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def webui():
    """一个只监听回环的 webui Server，用完关掉。"""
    httpd = server.Server(("127.0.0.1", free_port()), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def request(url, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


MEASUREMENT = {
    "region": (0, 0, 1920, 1080),
    "template_shape": (20, 50, 3),
    "box": (812, 640, 862, 660),
    "padded_box": (807, 635, 867, 665),
    "center": (837, 650),
    "score": 0.9312,
    "second": 0.8901,
    "threshold": 0.93,
    "margin": 0.0012,
    "passed": True,
    "exact_offset": (812, 640, -1058, -420),
    "fuzzy_offset": (807, 635, -1053, -415),
    "fuzzy_padding": 5,
    "pad_applied": 5,
    "capture_source": "printwindow",
}


class TestDevModeGate:
    """开关没开时接口必须是 403 —— 前端隐藏只是 UX，不是门禁。"""

    @pytest.fixture(autouse=True)
    def dev_off(self, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {})

    def test_image_list_is_403(self, webui):
        status, body = request(f"{webui}/api/probe/images")

        assert status == 403
        assert body["error"] == "开发者模式未开启"

    def test_probe_is_403(self, webui):
        status, body = request(f"{webui}/api/probe", "POST", {"name": "transfer.webp"})

        assert status == 403
        assert body["ok"] is False

    def test_dev_mode_is_off_unless_the_key_is_exactly_true(self, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {"webui_dev_mode": "yes"})

        assert server.dev_mode_enabled() is False

    def test_dev_mode_on(self, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {"webui_dev_mode": True})

        assert server.dev_mode_enabled() is True


class TestProbeRoute:
    @pytest.fixture(autouse=True)
    def dev_on(self, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {"webui_dev_mode": True})
        monkeypatch.setattr(server, "run_status", lambda: {"running": False})

    def test_refuses_while_a_run_is_in_progress(self, webui, monkeypatch):
        """跑图时截图线程正忙，抓到的帧也可能正好卡在过场/黑屏。"""
        monkeypatch.setattr(server, "run_status", lambda: {"running": True})

        status, body = request(f"{webui}/api/probe", "POST", {"name": "transfer.webp"})

        assert status == 409
        assert "正在跑图" in body["error"]

    def test_503_when_there_is_no_game_window(self, webui, monkeypatch):
        def no_window(name, threshold):
            raise RuntimeError("没检测到游戏窗口，先把游戏打开再探针")

        monkeypatch.setattr(server, "run_image_probe", no_window)

        status, body = request(f"{webui}/api/probe", "POST", {"name": "transfer.webp"})

        assert status == 503
        assert "没检测到游戏窗口" in body["error"]

    def test_404_when_the_picture_cannot_be_read(self, webui, monkeypatch):
        def unreadable(name, threshold):
            raise FileNotFoundError(f"图片读不出来：{name}")

        monkeypatch.setattr(server, "run_image_probe", unreadable)

        status, body = request(f"{webui}/api/probe", "POST", {"name": "ghost.webp"})

        assert status == 404
        assert "读不出来" in body["error"]

    def test_400_for_a_bad_threshold_value(self, webui, monkeypatch):
        def bad(name, threshold):
            raise ValueError("阈值应落在 0~1")

        monkeypatch.setattr(server, "run_image_probe", bad)

        status, body = request(
            f"{webui}/api/probe", "POST", {"name": "transfer.webp", "threshold": 1.5}
        )

        assert status == 400
        assert "阈值" in body["error"]

    def test_400_for_a_non_numeric_threshold(self, webui):
        status, _ = request(
            f"{webui}/api/probe", "POST", {"name": "transfer.webp", "threshold": "abc"}
        )

        assert status == 400

    def test_200_returns_the_numbers_and_the_preview(self, webui, monkeypatch):
        from utils.vision import probe as probe_module

        measurement = dict(MEASUREMENT)
        measurement["frame"] = np.zeros((1080, 1920, 3), np.uint8)
        monkeypatch.setattr(server, "run_image_probe", lambda name, threshold: measurement)
        monkeypatch.setattr(probe_module, "render_preview_png", lambda m: b"\x89PNG-fake")

        status, body = request(
            f"{webui}/api/probe", "POST", {"name": "transfer.webp", "threshold": 0.93}
        )

        assert status == 200
        assert body["ok"] is True
        assert body["box"] == [812, 640, 862, 660], "元组过 JSON 会变成数组"
        assert body["fuzzy_offset"] == [807, 635, -1053, -415]
        assert "frame" not in body, "几 MB 的 ndarray 不能进 JSON"
        assert base64.b64decode(body["preview_png_b64"]) == b"\x89PNG-fake"

    def test_200_without_a_preview_when_there_is_nothing_to_crop(self, webui, monkeypatch):
        from utils.vision import probe as probe_module

        monkeypatch.setattr(server, "run_image_probe", lambda name, threshold: dict(MEASUREMENT))
        monkeypatch.setattr(probe_module, "render_preview_png", lambda m: None)

        status, body = request(f"{webui}/api/probe", "POST", {"name": "transfer.webp"})

        assert status == 200
        assert body["preview_png_b64"] is None


class TestImageListRoute:
    @pytest.fixture(autouse=True)
    def dev_on(self, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {"webui_dev_mode": True})

    def test_serves_the_candidates(self, webui, monkeypatch):
        monkeypatch.setattr(
            server, "list_probe_images", lambda fragment, limit=None: [f"{fragment}.webp"]
        )

        status, body = request(f"{webui}/api/probe/images?q=trans")

        assert status == 200
        assert body["images"] == ["trans.webp"]
        assert body["total"] == 1

    def test_reports_the_total_separately_from_the_truncated_list(self, webui, monkeypatch):
        """前端要能分清「就这么多」和「被上限截断了」。"""
        monkeypatch.setattr(
            server,
            "list_probe_images",
            lambda fragment, limit=None: [f"i{index}.webp" for index in range(500)],
        )

        status, body = request(f"{webui}/api/probe/images?limit=10")

        assert status == 200
        assert len(body["images"]) == 10
        assert body["total"] == 500
        assert body["limit"] == 10

    def test_limit_is_clamped_to_the_ceiling(self, webui):
        status, body = request(f"{webui}/api/probe/images?limit=99999")

        assert status == 200
        assert body["limit"] == server.PROBE_IMAGE_LIMIT

    def test_a_bad_limit_falls_back_to_the_default(self, webui):
        status, body = request(f"{webui}/api/probe/images?limit=abc")

        assert status == 200
        assert body["limit"] == server.PROBE_IMAGE_LIMIT


class TestPictureFiles:
    def test_dedupes_by_extension_priority(self, tmp_path, monkeypatch):
        for name in ("a.webp", "a.png", "b.jpg"):
            (tmp_path / name).write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))

        assert server.list_probe_images() == ["a.webp", "b.jpg"]

    def test_filters_by_substring_case_insensitively(self, tmp_path, monkeypatch):
        for name in ("F_Teleport.webp", "transfer.webp"):
            (tmp_path / name).write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))

        assert server.list_probe_images("teleport") == ["F_Teleport.webp"]

    def test_ignores_files_that_are_not_pictures(self, tmp_path, monkeypatch):
        (tmp_path / "notes.txt").write_bytes(b"")
        (tmp_path / "1.ico").write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))

        assert server.list_probe_images() == []

    def test_missing_directory_yields_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path / "nope"))

        assert server.list_probe_images() == []


class TestRunImageProbe:
    """参数与安全校验 —— 这几条不碰屏幕。"""

    @pytest.mark.parametrize(
        "name",
        ["../secret.webp", "sub/dir.webp", "sub\\dir.webp", "transfer", "", "a.exe"],
        ids=["上跳", "正斜杠", "反斜杠", "没后缀", "空", "非图片后缀"],
    )
    def test_rejects_a_bad_picture_name(self, name):
        with pytest.raises(ValueError):
            server.run_image_probe(name, 0.9)

    def test_rejects_a_threshold_out_of_range(self):
        with pytest.raises(ValueError):
            server.run_image_probe("transfer.webp", 1.5)

    def test_reports_a_picture_that_is_not_there(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))

        with pytest.raises(FileNotFoundError):
            server.run_image_probe("ghost.webp", 0.9)

    def test_refuses_when_the_game_is_not_running(self, tmp_path, monkeypatch):
        """构造 ScreenSource 会连带构造 Window() —— 那会挪鼠标、甚至启动游戏并连点。"""
        from utils.drivers.window import Window
        from utils.vision import images as image_library

        (tmp_path / "probe_target.webp").write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))
        monkeypatch.setattr(
            image_library, "get_img", lambda path: np.zeros((4, 4, 3), np.uint8)
        )
        monkeypatch.setattr(Window, "find_window_hwnd", staticmethod(lambda: None))
        monkeypatch.setattr(
            Window,
            "describe_missing_window",
            staticmethod(lambda names=None: "没检测到游戏窗口，先把游戏打开再探针"),
        )

        def must_not_construct(*args, **kwargs):
            pytest.fail("没找到游戏窗口就不该构造 ScreenSource")

        monkeypatch.setattr("utils.drivers.screen.ScreenSource", must_not_construct)

        with pytest.raises(RuntimeError, match="没检测到游戏窗口"):
            server.run_image_probe("probe_target.webp", 0.9)

    def test_binds_the_screen_source_to_the_found_window(self, tmp_path, monkeypatch):
        """探针必须挂在**找到的那个窗口**上抓帧。"""
        from utils.drivers.window import Window
        from utils.vision import images as image_library

        (tmp_path / "probe_target.webp").write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))
        monkeypatch.setattr(
            image_library, "get_img", lambda path: np.zeros((4, 4, 3), np.uint8)
        )
        monkeypatch.setattr(Window, "find_window_hwnd", staticmethod(lambda: 7788))
        monkeypatch.setattr(Window, "attach", classmethod(lambda cls, hwnd: f"win-{hwnd}"))
        seen = {}
        monkeypatch.setattr(
            "utils.drivers.screen.ScreenSource",
            lambda window=None: seen.setdefault("window", window),
        )

        from utils.vision import probe as probe_module

        monkeypatch.setattr(probe_module, "measure", lambda *a, **k: {"ok": True})

        server.run_image_probe("probe_target.webp", 0.9)

        assert seen["window"] == "win-7788"
