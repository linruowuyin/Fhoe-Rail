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
        def no_window(name, threshold, search_offset=None):
            raise RuntimeError("没检测到游戏窗口，先把游戏打开再探针")

        monkeypatch.setattr(server, "run_image_probe", no_window)

        status, body = request(f"{webui}/api/probe", "POST", {"name": "transfer.webp"})

        assert status == 503
        assert "没检测到游戏窗口" in body["error"]

    def test_404_when_the_picture_cannot_be_read(self, webui, monkeypatch):
        def unreadable(name, threshold, search_offset=None):
            raise FileNotFoundError(f"图片读不出来：{name}")

        monkeypatch.setattr(server, "run_image_probe", unreadable)

        status, body = request(f"{webui}/api/probe", "POST", {"name": "ghost.webp"})

        assert status == 404
        assert "读不出来" in body["error"]

    def test_400_for_a_bad_threshold_value(self, webui, monkeypatch):
        def bad(name, threshold, search_offset=None):
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
        monkeypatch.setattr(server, "run_image_probe", lambda name, threshold, search_offset=None: measurement)
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

        monkeypatch.setattr(server, "run_image_probe", lambda name, threshold, search_offset=None: dict(MEASUREMENT))
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
            server, "list_probe_images", lambda fragment, limit=None, directory=None: [f"{fragment}.webp"]
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
            lambda fragment, limit=None, directory=None: [f"i{index}.webp" for index in range(500)],
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

    def test_offset_returns_the_next_slice(self, webui, monkeypatch):
        """滚到底再加载更多：同一份匹配结果按 offset 往后取。"""
        monkeypatch.setattr(
            server,
            "list_probe_images",
            lambda fragment, limit=None, directory=None: [f"i{index}.webp" for index in range(500)],
        )

        status, body = request(f"{webui}/api/probe/images?limit=10&offset=20")

        assert status == 200
        assert body["images"] == [f"i{index}.webp" for index in range(20, 30)]
        assert body["total"] == 500, "总数始终报全集，前端才知道还有没有下一页"
        assert body["offset"] == 20

    def test_offset_past_the_end_is_an_empty_page(self, webui, monkeypatch):
        monkeypatch.setattr(
            server, "list_probe_images", lambda fragment, limit=None, directory=None: ["a.webp"]
        )

        status, body = request(f"{webui}/api/probe/images?offset=5")

        assert status == 200
        assert body["images"] == []
        assert body["total"] == 1

    def test_a_bad_offset_falls_back_to_zero(self, webui, monkeypatch):
        """列表浏览而已，参数坏了回退默认值，不打断用户。"""
        monkeypatch.setattr(
            server,
            "list_probe_images",
            lambda fragment, limit=None, directory=None: ["a.webp", "b.webp"],
        )

        status, body = request(f"{webui}/api/probe/images?offset=abc")

        assert status == 200
        assert body["offset"] == 0
        assert body["images"] == ["a.webp", "b.webp"]

    def test_a_negative_offset_is_clamped_to_zero(self, webui, monkeypatch):
        monkeypatch.setattr(
            server, "list_probe_images", lambda fragment, limit=None, directory=None: ["a.webp"]
        )

        status, body = request(f"{webui}/api/probe/images?offset=-7")

        assert status == 200
        assert body["offset"] == 0
        assert body["images"] == ["a.webp"]


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

    def test_includes_subdirectories(self, tmp_path, monkeypatch):
        (tmp_path / "map_ui").mkdir()
        (tmp_path / "map_ui" / "transfer.webp").write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))

        assert server.list_probe_images("trans") == ["transfer.webp"]

    def test_sample_output_directory_is_ignored(self, tmp_path, monkeypatch):
        folder = tmp_path / "new_pic" / "20261024"
        folder.mkdir(parents=True)
        (folder / "transfer.webp").write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))

        assert server.list_probe_images() == []

    def test_missing_directory_yields_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path / "nope"))

        assert server.list_probe_images() == []

    def test_directory_filter_keeps_only_that_subtree(self, tmp_path, monkeypatch):
        """点左侧目录树某个节点时，只列这个目录（含子目录）里的图。"""
        (tmp_path / "ui").mkdir()
        (tmp_path / "ui" / "a.webp").write_bytes(b"")
        (tmp_path / "map_points" / "1").mkdir(parents=True)
        (tmp_path / "map_points" / "1" / "x.webp").write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))

        assert server.list_probe_images(directory="ui") == ["a.webp"]
        assert server.list_probe_images(directory="map_points") == ["x.webp"]
        assert server.list_probe_images() == ["a.webp", "x.webp"]


class TestProbeTree:
    """picture/ 的目录树：探针左侧选择用，目录即分类（R25）。"""

    def _make_tree(self, tmp_path, monkeypatch):
        (tmp_path / "ui").mkdir()
        (tmp_path / "ui" / "a.webp").write_bytes(b"")
        (tmp_path / "ui" / "b.webp").write_bytes(b"")
        (tmp_path / "map_points" / "1").mkdir(parents=True)
        (tmp_path / "map_points" / "1" / "x.webp").write_bytes(b"")
        (tmp_path / "map_points" / "2").mkdir()
        (tmp_path / "map_points" / "2" / "y.webp").write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))

    def test_counts_include_subdirectories(self, tmp_path, monkeypatch):
        self._make_tree(tmp_path, monkeypatch)

        tree = server.probe_tree()

        assert [node["name"] for node in tree] == ["map_points", "ui"]
        map_points = tree[0]
        assert map_points["count"] == 2, "父目录的 count 要含子目录里的图"
        assert map_points["own"] == 0
        assert [child["name"] for child in map_points["children"]] == ["1", "2"]
        assert tree[1]["count"] == 2 and tree[1]["own"] == 2

    def test_empty_directories_do_not_show_up(self, tmp_path, monkeypatch):
        (tmp_path / "empty").mkdir()
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))

        assert server.probe_tree() == []

    def test_route_is_403_without_dev_mode(self, webui, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {})

        status, body = request(f"{webui}/api/probe/tree")

        assert status == 403

    def test_route_returns_the_tree_and_total(self, webui, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {"webui_dev_mode": True})
        self._make_tree(tmp_path, monkeypatch)

        status, body = request(f"{webui}/api/probe/tree")

        assert status == 200
        assert body["total"] == 4
        assert [node["path"] for node in body["tree"]] == ["map_points", "ui"]


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


class TestRunImageProbeSearchOffset:
    """`run_image_probe` 的搜索区域：没传时取登记表，显式 None 表示只看全屏。"""

    def _stub(self, tmp_path, monkeypatch):
        from utils.drivers.window import Window
        from utils.vision import images as image_library
        from utils.vision import probe as probe_module

        (tmp_path / "probe_target.webp").write_bytes(b"")
        monkeypatch.setattr(server, "PICTURE_DIR", str(tmp_path))
        monkeypatch.setattr(
            image_library, "get_img", lambda path: np.zeros((4, 4, 3), np.uint8)
        )
        monkeypatch.setattr(
            image_library, "search_offset_of", lambda template: (1843, 0, -35, 0)
        )
        monkeypatch.setattr(Window, "find_window_hwnd", staticmethod(lambda: 7788))
        monkeypatch.setattr(Window, "attach", classmethod(lambda cls, hwnd: hwnd))
        monkeypatch.setattr(
            "utils.drivers.screen.ScreenSource", lambda window=None: object()
        )
        seen = {}
        monkeypatch.setattr(
            probe_module, "measure", lambda *args, **kwargs: seen.update(kwargs)
        )
        return seen

    def test_uses_the_registered_region_by_default(self, tmp_path, monkeypatch):
        seen = self._stub(tmp_path, monkeypatch)

        server.run_image_probe("probe_target.webp", 0.9)

        assert seen["search_offset"] == (1843, 0, -35, 0)

    def test_explicit_none_means_full_screen_only(self, tmp_path, monkeypatch):
        seen = self._stub(tmp_path, monkeypatch)

        server.run_image_probe("probe_target.webp", 0.9, None)

        assert seen["search_offset"] is None

    def test_an_explicit_region_overrides_the_registered_one(
        self, tmp_path, monkeypatch
    ):
        seen = self._stub(tmp_path, monkeypatch)

        server.run_image_probe("probe_target.webp", 0.9, (10, 20, -30, -40))

        assert seen["search_offset"] == (10, 20, -30, -40)

class TestProbeTwoStrategies:
    # 不 stub read_config 的话，这一类的成败取决于本机 config.json 里
    # webui_dev_mode 是不是恰好开着（CI 上没这个文件 → 403）。
    @pytest.fixture(autouse=True)
    def dev_on(self, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {"webui_dev_mode": True})
        monkeypatch.setattr(server, "run_status", lambda: {"running": False})

    def test_returns_both_comparisons_and_one_preview_each(self, webui, monkeypatch):
        from utils.vision import probe as probe_module

        measurement = dict(MEASUREMENT)
        measurement["frame"] = np.zeros((1080, 1920, 3), np.uint8)
        measurement["strategy"] = "shape"
        measurement["comparisons"] = [
            {**MEASUREMENT, "strategy": "color", "label": "原始识别（颜色）",
             "description": "", "primary": False},
            {**MEASUREMENT, "strategy": "shape", "label": "轮廓识别（形状）",
             "description": "", "primary": True},
        ]
        monkeypatch.setattr(server, "run_image_probe", lambda name, threshold, search_offset=None: measurement)
        drawn = []

        def fake_preview(merged):
            drawn.append(merged["box"])
            return b"\x89PNG-fake"

        monkeypatch.setattr(probe_module, "render_preview_png", fake_preview)

        status, body = request(f"{webui}/api/probe", "POST", {"name": "setting_other.webp"})

        assert status == 200
        assert [item["strategy"] for item in body["comparisons"]] == ["color", "shape"]
        assert set(body["previews"]) == {
            "color",
            "shape",
            "full:color",
            "full:shape",
        }
        assert base64.b64decode(body["preview_png_b64"]) == b"\x89PNG-fake"
        assert len(drawn) == 2, "每种策略各画一张预览（框的位置可能不同）"


class TestProbeSearchAreaRoute:
    """搜索区域从 WebUI 进来：显式 offset / 不传 / 传空 / 参数非法。"""

    @pytest.fixture(autouse=True)
    def dev_on(self, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {"webui_dev_mode": True})
        monkeypatch.setattr(server, "run_status", lambda: {"running": False})

    def capture(self, monkeypatch):
        from utils.vision import probe as probe_module

        seen = {}
        measurement = dict(MEASUREMENT)
        measurement["frame"] = np.zeros((1080, 1920, 3), np.uint8)
        measurement["areas"] = []

        def fake(name, threshold, search_offset=None):
            seen["search_offset"] = search_offset
            return measurement

        monkeypatch.setattr(server, "run_image_probe", fake)
        monkeypatch.setattr(probe_module, "render_preview_png", lambda m: b"png")
        return seen

    def test_explicit_offset_is_passed_through(self, webui, monkeypatch):
        seen = self.capture(monkeypatch)

        status, _ = request(
            f"{webui}/api/probe",
            "POST",
            {"name": "setting_icon.webp", "offset": [1843, 0, -35, 0]},
        )

        assert status == 200
        assert seen["search_offset"] == (1843, 0, -35, 0)

    def test_absent_offset_falls_back_to_the_registered_region(self, webui, monkeypatch):
        seen = self.capture(monkeypatch)

        status, _ = request(f"{webui}/api/probe", "POST", {"name": "setting_icon.webp"})

        assert status == 200
        assert seen["search_offset"] is server._REGISTERED_SEARCH_OFFSET

    def test_an_empty_offset_means_full_screen_only(self, webui, monkeypatch):
        seen = self.capture(monkeypatch)

        status, _ = request(
            f"{webui}/api/probe",
            "POST",
            {"name": "setting_icon.webp", "offset": None},
        )

        assert status == 200
        assert seen["search_offset"] is None

    @pytest.mark.parametrize(
        "bad",
        [[1, 2, 3], [1, 2, 3, 4, 5], "1843,0,-35", [1, 2, 3, "x"]],
        ids=["少一个", "多一个", "字符串", "非数字"],
    )
    def test_a_malformed_offset_is_400(self, webui, monkeypatch, bad):
        capture = self.capture(monkeypatch)

        status, body = request(
            f"{webui}/api/probe", "POST", {"name": "setting_icon.webp", "offset": bad}
        )

        assert status == 400
        assert "4 个整数" in body["error"]
        assert "search_offset" not in capture, "参数不对就不该去抓帧"

    def test_previews_are_split_by_area_and_strategy(self, webui, monkeypatch):
        from utils.vision import probe as probe_module

        measurement = dict(MEASUREMENT)
        measurement["frame"] = np.zeros((1080, 1920, 3), np.uint8)
        measurement["strategy"] = "shape"
        full_comparisons = [
            {**MEASUREMENT, "strategy": strategy, "label": strategy,
             "description": "", "primary": strategy == "shape"}
            for strategy in ("color", "shape")
        ]
        search_comparisons = [
            {**MEASUREMENT, "strategy": strategy, "label": strategy,
             "description": "", "primary": strategy == "shape"}
            for strategy in ("color", "shape")
        ]
        measurement["comparisons"] = full_comparisons
        measurement["areas"] = [
            {"area": "full", "label": "全屏", "offset": (0, 0, 0, 0),
             "region": (0, 0, 1920, 1080), "comparisons": full_comparisons,
             "error": None},
            {"area": "search", "label": "调用点", "offset": (1843, 0, -35, 0),
             "region": (1843, 0, 1885, 1080), "comparisons": search_comparisons,
             "error": None},
        ]
        monkeypatch.setattr(
            server, "run_image_probe", lambda name, threshold, search_offset=None: measurement
        )
        regions = []

        def fake_preview(merged):
            regions.append(merged["region"])
            return b"\x89PNG-fake"

        monkeypatch.setattr(probe_module, "render_preview_png", fake_preview)

        status, body = request(
            f"{webui}/api/probe",
            "POST",
            {"name": "setting_icon.webp", "offset": [1843, 0, -35, 0]},
        )

        assert status == 200
        assert set(body["previews"]) == {
            "full:color",
            "full:shape",
            "search:color",
            "search:shape",
            "color",
            "shape",
        }
        assert body["previews"]["search:color"] == base64.b64encode(
            b"\x89PNG-fake"
        ).decode("ascii")
        assert regions[:2] == [(0, 0, 1920, 1080)] * 2
        assert regions[2:] == [(1843, 0, 1885, 1080)] * 2
        assert body["areas"][1]["area"] == "search"


class TestProbeMetaRoute:
    @pytest.fixture(autouse=True)
    def dev_on(self, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {"webui_dev_mode": True})

    def test_dev_mode_off_is_403(self, webui, monkeypatch):
        monkeypatch.setattr(server, "read_config", lambda: {})

        status, _ = request(f"{webui}/api/probe/meta?name=setting_icon.webp")

        assert status == 403

    def test_returns_the_registered_region_and_strategy(self, webui):
        status, body = request(f"{webui}/api/probe/meta?name=setting_icon.webp")

        assert status == 200
        assert body["search_offset"] == [1843, 0, -35, 0]
        assert body["strategy"] == "shape"
        assert body["strategy_label"]

    def test_an_asset_without_a_region_returns_null(self, webui):
        status, body = request(f"{webui}/api/probe/meta?name=transfer.webp")

        assert status == 200
        assert body["search_offset"] is None

    def test_returns_the_registered_threshold(self, webui):
        """选中模板时前端要预填这张图登记的阈值（core/thresholds.py 的常量）。"""
        from utils.core.thresholds import DEFAULT_MATCH, TRANSFER_ICON

        status, body = request(f"{webui}/api/probe/meta?name=transfer.webp")

        assert status == 200
        assert body["threshold"] == TRANSFER_ICON
        assert body["default_threshold"] == DEFAULT_MATCH

    def test_an_unregistered_threshold_returns_null_with_a_default(self, webui):
        """地图点位这类没登记阈值的图：threshold 为 null，前端沿用默认值并提示。"""
        from utils.core.thresholds import DEFAULT_MATCH

        status, body = request(f"{webui}/api/probe/meta?name=map_1.webp")

        assert status == 200
        assert body["threshold"] is None
        assert body["default_threshold"] == DEFAULT_MATCH

    def test_a_missing_picture_is_404(self, webui):
        status, _ = request(f"{webui}/api/probe/meta?name=ghost.webp")

        assert status == 404

    def test_a_bad_name_is_400(self, webui):
        status, _ = request(f"{webui}/api/probe/meta?name=../x.webp")

        assert status == 400
