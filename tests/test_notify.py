"""utils/core/notify.py —— 多渠道通知的参数映射与发送分支。"""

import pytest

from utils.config.config import ConfigurationManager
from utils.core.notify import CHANNEL_NAMES, CHAT_PARAM, KEY_PARAM, WEBHOOK_PARAM, Notify
from utils.core.notify import get_error_summary


@pytest.fixture
def cfg():
    return ConfigurationManager()


@pytest.fixture
def notify(cfg):
    return Notify()


def set_config(notify, cfg, **values):
    """同时更新 Notify 持有的快照与 ConfigurationManager 的缓存。

    Notify.__init__ 会把当时的 config dict 存下来（见 TestConfigSnapshot），
    而 ConfigurationManager 在文件 mtime 变化时会整体替换这个 dict。这里显式
    同步，避免用例结果取决于 Windows 上 time.time() 的 15.6ms 粒度是否恰好
    让 mtime 比较判定为“配置已更新”。
    """
    notify.config.update(values)
    cfg.config_file.update(values)


class TestChannelMetadata:
    def test_aliases_do_not_override_real_channels(self):
        from utils.core.notify import CHANNEL_ALIASES

        assert not (set(CHANNEL_ALIASES) & set(CHANNEL_NAMES))

    def test_param_maps_only_reference_known_channels(self):
        known = set(CHANNEL_NAMES)
        for mapping in (KEY_PARAM, CHAT_PARAM, WEBHOOK_PARAM):
            assert set(mapping) <= known, "参数映射表里出现了不存在的渠道"

    def test_channels_list_matches_names(self):
        assert Notify.CHANNELS == list(CHANNEL_NAMES.keys())


class TestEnabled:
    def test_disabled_by_default(self, notify):
        assert notify.enabled is False

    def test_reads_flag_from_config(self, notify, cfg):
        set_config(notify, cfg,notify_enabled=True)
        assert notify.enabled is True


class TestChannelResolution:
    def test_legacy_winotify_is_aliased(self, notify, cfg):
        set_config(notify, cfg,notify_channel="winotify")
        assert notify._channel() == "windows"

    def test_unknown_channel_falls_back_to_webhook(self, notify, cfg):
        set_config(notify, cfg,notify_channel="不存在的渠道")
        assert notify._channel() == "webhook"

    def test_missing_channel_defaults_to_webhook(self, notify, cfg):
        notify.config.pop("notify_channel", None)
        assert notify._channel() == "webhook"

    def test_valid_channel_passes_through(self, notify, cfg):
        set_config(notify, cfg,notify_channel="telegram")
        assert notify._channel() == "telegram"


class TestBuildParams:
    def test_maps_key_to_channel_specific_name(self, notify, cfg):
        set_config(notify, cfg,notify_channel="serverchan", notify_key="SCT123")
        assert notify._build_params("serverchan") == {"sendkey": "SCT123"}

    def test_maps_chat_id(self, notify, cfg):
        set_config(notify, cfg,notify_key="tok", notify_chat_id="42")
        params = notify._build_params("telegram")
        assert params == {"token": "tok", "chat_id": "42"}

    def test_webhook_channels_use_key_as_url(self, notify, cfg):
        set_config(notify, cfg,notify_key="https://example.invalid/hook")
        assert notify._build_params("lark") == {"webhook": "https://example.invalid/hook"}

    def test_bark_gets_default_server(self, notify, cfg):
        set_config(notify, cfg,notify_key="K")
        assert notify._build_params("bark")["server"] == "api.day.app"

    def test_empty_key_is_omitted(self, notify, cfg):
        set_config(notify, cfg,notify_key="")
        assert notify._build_params("serverchan") == {}

    def test_extra_params_json_is_merged(self, notify, cfg):
        set_config(notify, cfg,notify_key="tok", notify_params='{"extra": 1}')
        assert notify._build_params("telegram")["extra"] == 1

    def test_extra_params_override_mapped_values(self, notify, cfg):
        set_config(notify, cfg,notify_key="tok", notify_params='{"token": "override"}')
        assert notify._build_params("telegram")["token"] == "override"

    def test_non_dict_extra_params_is_ignored(self, notify, cfg):
        set_config(notify, cfg,notify_key="tok", notify_params="[1, 2, 3]")
        assert notify._build_params("telegram") == {"token": "tok"}

    def test_invalid_json_warns_and_is_ignored(self, notify, cfg, log_records):
        set_config(notify, cfg,notify_key="tok", notify_params="{ broken")
        assert notify._build_params("telegram") == {"token": "tok"}
        assert any("notify_params" in r["message"] for r in log_records)


class TestSend:
    def test_disabled_short_circuits(self, notify, cfg):
        set_config(notify, cfg,notify_enabled=False)

        def boom(*args, **kwargs):
            raise AssertionError("不应尝试发送")

        notify._send_webhook = boom
        assert notify.send("t", "c") is False

    def test_webhook_without_url_warns(self, notify, cfg, log_records):
        set_config(notify, cfg,notify_enabled=True, notify_channel="webhook", webhook_url="")
        assert notify.send("t", "c") is False
        assert any("webhook_url" in r["message"] for r in log_records)

    def test_webhook_uses_discord_style_payload(self, notify, cfg, monkeypatch):
        set_config(
            notify,
            cfg,
            notify_enabled=True,
            notify_channel="webhook",
            webhook_url="https://example.invalid/h",
        )
        sent = {}

        class Response:
            def raise_for_status(self):
                return None

        def fake_post(url, json=None, timeout=None):
            sent.update(url=url, json=json, timeout=timeout)
            return Response()

        monkeypatch.setattr("requests.post", fake_post)

        assert notify.send("标题", "正文") is True
        assert sent["url"] == "https://example.invalid/h"
        assert sent["json"] == {"content": "标题\n正文"}
        assert sent["timeout"] == 5

    def test_webhook_failure_is_reported_not_raised(self, notify, cfg, monkeypatch):
        set_config(
            notify,
            cfg,
            notify_enabled=True,
            notify_channel="webhook",
            webhook_url="https://example.invalid/h",
        )

        def boom(*args, **kwargs):
            raise RuntimeError("网络不可达")

        monkeypatch.setattr("requests.post", boom)
        assert notify.send("t", "c") is False

    def test_windows_channel_uses_winotify(self, notify, cfg, monkeypatch):
        set_config(notify, cfg,notify_enabled=True, notify_channel="windows")
        shown = []

        class Notification:
            def __init__(self, **kwargs):
                shown.append(kwargs)

            def show(self):
                shown.append("shown")

        monkeypatch.setattr("winotify.Notification", Notification)

        assert notify.send("标题", "正文") is True
        assert shown[0]["app_id"] == "Fhoe-Rail"
        assert "shown" in shown

    def test_onepush_channel_receives_built_params(self, notify, cfg, monkeypatch):
        set_config(
            notify,
            cfg,
            notify_enabled=True,
            notify_channel="telegram",
            notify_key="tok",
        )
        calls = []

        class Notifier:
            def notify(self, **kwargs):
                calls.append(kwargs)

        monkeypatch.setattr("onepush.get_notifier", lambda channel: Notifier())

        assert notify.send("标题", "正文") is True
        assert calls == [{"token": "tok", "title": "标题", "content": "正文"}]

    def test_onepush_failure_is_swallowed(self, notify, cfg, monkeypatch):
        set_config(notify, cfg,notify_enabled=True, notify_channel="telegram", notify_key="tok")

        def boom(channel):
            raise RuntimeError("渠道不可用")

        monkeypatch.setattr("onepush.get_notifier", boom)
        assert notify.send("t", "c") is False


class TestConvenienceSenders:
    def test_start_notification_is_opt_in(self, notify, cfg):
        set_config(notify, cfg,notify_enabled=True, notify_on_start=False)
        assert notify.send_start("1-1_0") is False

    def test_start_notification_includes_map_name(self, notify, cfg, monkeypatch):
        set_config(notify, cfg,notify_enabled=True, notify_on_start=True)
        captured = {}
        notify.send = lambda title, content="": captured.update(
            title=title, content=content
        ) or True

        assert notify.send_start("1-1_0") is True
        assert "1-1_0" in captured["content"]

    def test_end_notification_is_on_by_default(self, notify, cfg):
        set_config(notify, cfg,notify_enabled=True)
        captured = {}
        notify.send = lambda title, content="": captured.update(content=content) or True

        notify.send_end({"战斗次数": 5})

        assert "战斗次数：5" in captured["content"]

    def test_end_notification_can_be_disabled(self, notify, cfg):
        set_config(notify, cfg,notify_enabled=True, notify_on_end=False)
        assert notify.send_end({"a": 1}) is False

    def test_error_notification_truncates_long_text(self, notify, cfg):
        set_config(notify, cfg,notify_enabled=True, notify_on_error=True)
        captured = {}
        notify.send = lambda title, content="": captured.update(content=content) or True

        notify.send_error("x" * 2000)

        assert captured["content"].count("x") == 800

    def test_test_notification(self, notify, cfg):
        set_config(notify, cfg,notify_enabled=True)
        captured = {}
        notify.send = lambda title, content="": captured.update(title=title) or True

        notify.send_test()

        assert "测试通知" in captured["title"]


class TestConfigSnapshot:
    """Notify 在构造时抓取 config dict，之后 ConfigurationManager 换掉整个 dict。"""

    def test_notify_reads_from_its_snapshot(self, cfg):
        notify = Notify()
        notify.config["notify_enabled"] = True
        assert notify.enabled is True

    @pytest.mark.xfail(
        strict=True,
        reason="Notify.__init__ 缓存了 config dict 的引用，而 ConfigurationManager "
        "刷新时会整体替换 _config；于是运行期（例如 WebUI 里）改通知配置在本次进程内不生效",
    )
    def test_runtime_config_change_is_picked_up(self, notify, cfg, isolated_cwd):
        import json

        path = isolated_cwd / "config.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["notify_enabled"] = True
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        cfg._update_config()  # 模拟 ConfigurationManager 因文件变更而刷新

        assert notify.enabled is True


class TestGetErrorSummary:
    def test_returns_last_lines_of_current_traceback(self):
        try:
            raise ValueError("boom")
        except ValueError as exc:
            summary = get_error_summary(exc)
        assert "ValueError: boom" in summary
        assert len(summary.splitlines()) <= 6

    def test_outside_except_block_returns_none_marker(self):
        """在没有活跃异常时调用只会得到 'NoneType: None'。"""
        assert "NoneType: None" in get_error_summary(ValueError("boom"))
