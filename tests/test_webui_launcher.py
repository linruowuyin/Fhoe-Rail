"""WebUI 的打包布局：单入口 `Fhoe-Rail.exe --webui-server`。

以前 WebUI 是独立的 `webui-server.exe`，图片探针上线后它也要带 cv2 / numpy，
发布包里等于把同一套库打了两份（约 +50MB）。现在服务跑在主程序 exe 的
`--webui-server` 模式下，这里钉住两件事：

1. 打包版启动器优先找同目录的 `Fhoe-Rail.exe` 并带上 `--webui-server`；
2. 打包版的项目根既能从单入口 exe 找到，也兼容旧的 `webui/webui-server/` 布局。
"""

import os
import sys

from webui import server, start_webui


class TestServerCommand:
    def test_frozen_prefers_the_single_entry_exe(self, tmp_path, monkeypatch):
        exe = tmp_path / "Fhoe-Rail.exe"
        exe.write_bytes(b"")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(start_webui, "BASE", str(tmp_path))

        assert start_webui.server_command() == [str(exe), "--webui-server"]

    def test_frozen_keeps_legacy_webui_server_compatibility(
        self, tmp_path, monkeypatch
    ):
        legacy = tmp_path / "webui" / "webui-server" / "webui-server.exe"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(start_webui, "BASE", str(tmp_path))

        assert start_webui.server_command() == [str(legacy)]

    def test_source_mode_runs_server_py(self, tmp_path, monkeypatch):
        webui_dir = tmp_path / "webui"
        webui_dir.mkdir()
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.setattr(start_webui, "BASE", str(webui_dir))

        assert start_webui.server_command() == [
            sys.executable,
            os.path.join(str(tmp_path), "webui", "server.py"),
        ]


class TestFrozenBaseDir:
    def test_single_entry_exe_at_the_package_root(self, tmp_path):
        (tmp_path / "map").mkdir()
        (tmp_path / "webui").mkdir()
        exe = tmp_path / "Fhoe-Rail.exe"

        assert server._frozen_base_dir(str(exe)) == str(tmp_path)

    def test_legacy_webui_server_layout(self, tmp_path):
        (tmp_path / "map").mkdir()
        (tmp_path / "webui").mkdir()
        nested = tmp_path / "webui" / "webui-server"
        nested.mkdir()

        assert server._frozen_base_dir(str(nested / "webui-server.exe")) == str(tmp_path)

    def test_unknown_layout_falls_back_to_the_exe_directory(self, tmp_path):
        exe = tmp_path / "somewhere" / "webui-server.exe"
        exe.parent.mkdir()

        assert server._frozen_base_dir(str(exe)) == str(exe.parent)
