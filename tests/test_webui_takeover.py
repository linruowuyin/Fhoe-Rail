"""webui/server.py 的端口接管 —— 新实例请旧实例退出后接管端口。

以前端口被占只能报错、让用户自己去关（「忘了关上一个」很常见）。接管的关键不是
"能关掉"，而是**别误杀**：只认自家 `/api/ping` 的 app 标识 + 令牌；认不出来的占用者
（别的程序、或本工具更老不带 /api/ping 的版本）一律报错退出。旧实例正在跑锄地时
也不能悄悄中断那趟。

这里用一个真跑在 127.0.0.1 上的 webui Server（只监听回环、不碰游戏）来测。
"""

import http.server
import importlib.util
import io
import json
import os
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_server():
    """加载 webui/server.py（webui/ 不是包，只能按路径加载）。"""
    spec = importlib.util.spec_from_file_location(
        "webui_server_under_test", REPO_ROOT / "webui" / "server.py"
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


class Stranger:
    """一个"别人家的"HTTP 服务：/api/ping 回 404。接管逻辑必须认不出它。"""

    def __init__(self, port):
        self.port = port
        self.hits = 0

        stranger = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                stranger.hits += 1
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.httpd = http.server.HTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def webui():
    """后台跑一个真的 webui 实例。

    serve_forever 返回后（被 /api/shutdown 停掉时）要顺手关掉监听套接字 ——
    真 main() 里那句 `finally: server.server_close()` 就是干这个的；夹具不关的话
    端口不会释放，接管路径会一直等到超时。
    """
    port = free_port()
    httpd = server.Server(("127.0.0.1", port), server.Handler)

    def serve():
        httpd.serve_forever()
        try:
            httpd.server_close()
        except OSError:
            pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield SimpleNamespace(port=port, httpd=httpd, thread=thread)
    try:
        httpd.shutdown()
        httpd.server_close()
    except OSError:
        pass


@pytest.fixture
def stranger():
    instance = Stranger(free_port())
    yield instance
    instance.close()


def post_shutdown(port, token=None, body=None):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/shutdown",
        data=json.dumps(body or {}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"X-Fhoe-Token": token} if token else {}),
        },
    )
    return urllib.request.urlopen(request, timeout=3)


class TestIdentity:
    def test_ping_identifies_our_webui(self, webui):
        info = server.probe_webui(webui.port)
        assert info is not None
        assert info["app"] == "fhoe-rail-webui"
        assert info["port"] == webui.port
        assert info["pid"] == os.getpid()
        assert info["token"] == server._SHUTDOWN_TOKEN

    def test_ping_reports_that_nothing_is_running(self, webui):
        assert server.probe_webui(webui.port)["run"] == {
            "running": False,
            "pid": None,
            "mode": None,
        }

    def test_probe_returns_none_when_nothing_listens(self):
        assert server.probe_webui(free_port()) is None

    def test_probe_returns_none_for_a_stranger(self, stranger):
        assert server.probe_webui(stranger.port, timeout=1) is None


class TestShutdownEndpoint:
    def test_without_the_token_it_is_refused_and_the_server_keeps_running(self, webui):
        with pytest.raises(urllib.error.HTTPError) as exc:
            post_shutdown(webui.port)
        assert exc.value.code == 403
        assert server.probe_webui(webui.port) is not None, "拒绝之后必须还在服务"

    def test_with_the_token_it_stops_the_server(self, webui):
        with post_shutdown(webui.port, token=server._SHUTDOWN_TOKEN) as resp:
            assert json.loads(resp.read().decode("utf-8"))["ok"] is True

        webui.thread.join(timeout=5)
        assert not webui.thread.is_alive(), "serve_forever 应该收工（真 main() 随后就退进程）"
        assert server.port_is_free(webui.port), "旧实例应把端口放掉"

    def test_foreign_host_is_refused(self, webui):
        request = urllib.request.Request(
            f"http://127.0.0.1:{webui.port}/api/ping",
            headers={"Host": "evil.example.com"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(request, timeout=3)
        assert exc.value.code == 403


class TestTakeover:
    def test_takes_the_port_from_our_own_instance(self, webui):
        httpd = server.bind_port_with_takeover(port=webui.port)
        try:
            assert httpd.server_address[1] == webui.port
        finally:
            httpd.server_close()

    def test_refuses_when_a_stranger_holds_the_port(self, stranger, capsys):
        with pytest.raises(SystemExit) as exc:
            server.bind_port_with_takeover(port=stranger.port)

        assert exc.value.code == 1
        assert "认不出是 Fhoe-Rail WebUI" in capsys.readouterr().out
        # 关键：别人还在，且我们连 /api/shutdown 都没试过
        assert stranger.hits >= 1
        assert not server.port_is_free(stranger.port)

    def test_refuses_a_running_bot_in_a_non_interactive_shell(
        self, webui, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            server,
            "probe_webui",
            lambda port=server.PORT, timeout=1.5: {
                "pid": 1234,
                "port": port,
                "token": "whatever",
                "run": {"running": True, "pid": 4321, "mode": "normal"},
            },
        )
        monkeypatch.setattr(server.sys, "stdin", io.StringIO())  # isatty() -> False
        asked = []
        monkeypatch.setattr(
            server, "ask_old_instance_to_quit", lambda *a, **k: asked.append(k) or True
        )

        # 端口真的被占着（用 fixture 里的实例），才会走到探测那一步
        with pytest.raises(SystemExit) as exc:
            server.bind_port_with_takeover(port=webui.port)

        assert exc.value.code == 1
        assert "非交互环境" in capsys.readouterr().out
        assert asked == [], "不该去请旧实例退出，更不该停人家正在跑的锄地"

    def test_asks_before_stopping_a_running_bot(self, webui, monkeypatch):
        monkeypatch.setattr(
            server,
            "probe_webui",
            lambda port=server.PORT, timeout=1.5: {
                "pid": 1234,
                "port": port,
                "token": "whatever",
                "run": {"running": True, "pid": 4321, "mode": "normal"},
            },
        )
        monkeypatch.setattr(
            server.sys, "stdin", SimpleNamespace(isatty=lambda: True)
        )
        monkeypatch.setattr("builtins.input", lambda prompt="": "")
        seen = {}

        def fake_quit(old, port=server.PORT, stop_run=False, wait=5.0):
            seen["stop_run"] = stop_run
            # 旧实例真的退出（否则接下来绑不上端口，测的就不是"确认"这条路径了）
            webui.httpd.shutdown()
            webui.httpd.server_close()
            return True

        monkeypatch.setattr(server, "ask_old_instance_to_quit", fake_quit)

        httpd = server.bind_port_with_takeover(port=webui.port)
        try:
            assert seen["stop_run"] is True, "交互确认之后才允许停掉那趟锄地"
            assert httpd.server_address[1] == webui.port
        finally:
            httpd.server_close()
