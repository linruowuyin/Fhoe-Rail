# -*- coding: utf-8 -*-
"""
多渠道通知推送模块 v2 —— 基于 onepush 聚合引擎（与 March7thAssistant 同方案）

onepush 渠道（17 个）:
    serverchan / serverchanturbo / pushplus / telegram / bark / dingtalk /
    wechatworkbot / wechatworkapp / lark(飞书) / discord / gotify / ntfy /
    pushdeer / qmsg / smtp / gocqhttp / custom

自研渠道（2 个）:
    webhook   通用 Webhook（用 config 的 webhook_url，Discord/Slack 风格）
    winotify  Windows 桌面通知（winotify 库，零配置）

配置键（config.json）:
    notify_enabled     总开关（默认 False）
    notify_channel     渠道名
    notify_key         渠道主密钥（webhook 渠道用 webhook_url）
    notify_chat_id     目标参数（telegram 的 chat_id、qmsg 的 qq 等）
    notify_params      高级参数 JSON 字符串（smtp/wechatworkapp/custom 等多参渠道用，合并覆盖默认映射）
    notify_on_start    开始锄地时通知
    notify_on_end      结束时通知（含统计摘要）
    notify_on_error    出错时通知

所有发送失败只记日志，不影响主流程。
"""
import datetime
import json
import traceback

from utils.config.config import ConfigurationManager
from utils.log import log

# onepush 渠道：notify_key 映射到的参数名
KEY_PARAM = {
    'serverchan': 'sendkey',
    'serverchanturbo': 'sendkey',
    'pushplus': 'token',
    'telegram': 'token',
    'bark': 'key',
    'dingtalk': 'token',
    'wechatworkbot': 'key',
    'gotify': 'token',
    'ntfy': 'topic',
    'pushdeer': 'pushkey',
    'qmsg': 'key',
    'gocqhttp': 'qq',
}
# notify_chat_id 映射到的参数名
CHAT_PARAM = {
    'telegram': 'chat_id',
    'qmsg': 'qq',
    'gocqhttp': 'qq',
}
# 使用 webhook 地址类参数的渠道（notify_key 直接作为 webhook URL）
WEBHOOK_PARAM = {
    'lark': 'webhook',
    'discord': 'webhook',
}

CHANNEL_NAMES = {
    'serverchan': 'Server酱',
    'serverchanturbo': 'Server酱³ Turbo',
    'pushplus': 'PushPlus',
    'telegram': 'Telegram',
    'bark': 'Bark (iOS)',
    'dingtalk': '钉钉机器人',
    'wechatworkbot': '企业微信机器人',
    'wechatworkapp': '企业微信应用',
    'lark': '飞书 / Lark',
    'discord': 'Discord',
    'gotify': 'Gotify',
    'ntfy': 'Ntfy',
    'pushdeer': 'PushDeer',
    'qmsg': 'Qmsg酱',
    'smtp': '邮件 (SMTP)',
    'gocqhttp': 'QQ 机器人 (OneBot)',
    'custom': '自定义请求',
    'webhook': '通用 Webhook',
    'windows': 'Windows 桌面通知',
}

# 旧渠道名兼容映射（winotify → windows）
CHANNEL_ALIASES = {
    'winotify': 'windows',
}


class Notify:
    CHANNELS = list(CHANNEL_NAMES.keys())

    def __init__(self):
        self.cfg = ConfigurationManager()
        self.config = self.cfg.config_file

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("notify_enabled", False))

    def _channel(self) -> str:
        ch = self.config.get("notify_channel", "webhook")
        # 兼容旧值：winotify 已更名为 windows
        ch = CHANNEL_ALIASES.get(ch, ch)
        return ch if ch in self.CHANNELS else "webhook"

    def _build_params(self, channel: str) -> dict:
        """构造 onepush 渠道参数：notify_key/notify_chat_id 自动映射 + notify_params JSON 合并覆盖"""
        params = {}
        key = self.config.get("notify_key", "")
        chat = self.config.get("notify_chat_id", "")

        if channel in KEY_PARAM and key:
            params[KEY_PARAM[channel]] = key
        if channel in CHAT_PARAM and chat:
            params[CHAT_PARAM[channel]] = chat
        if channel in WEBHOOK_PARAM and key:
            params['webhook'] = key
        if channel == 'bark':
            params.setdefault('server', 'api.day.app')

        extra = self.config.get("notify_params", "")
        if extra:
            try:
                extra_dict = json.loads(extra)
                if isinstance(extra_dict, dict):
                    params.update(extra_dict)
            except Exception as e:
                log.warning(f"notify_params JSON 解析失败，已忽略: {e}")
        return params

    def _send_webhook(self, title, content, url):
        try:
            import requests
            resp = requests.post(url, json={"content": f"{title}\n{content}"}, timeout=5)
            resp.raise_for_status()
            return True
        except Exception as e:
            log.warning(f"Webhook 通知发送失败: {e}")
            return False

    def _send_winotify(self, title, content):
        """Windows 桌面通知（零配置本地渠道）"""
        try:
            from winotify import Notification
            toast = Notification(app_id="Fhoe-Rail", title=title, msg=content, duration="short")
            toast.show()
            return True
        except Exception as e:
            log.warning(f"Windows 桌面通知发送失败: {e}")
            return False

    def send(self, title, content=""):
        """发送通知（总开关关闭时静默跳过）"""
        if not self.enabled:
            return False
        channel = self._channel()

        if channel == "webhook":
            url = self.config.get("webhook_url", "")
            if not url:
                log.warning("webhook 渠道需要配置 webhook_url")
                return False
            ok = self._send_webhook(title, content, url)
        elif channel in ("windows", "winotify"):
            ok = self._send_winotify(title, content)
        else:
            try:
                from onepush import get_notifier
                params = self._build_params(channel)
                get_notifier(channel).notify(**params, title=title, content=content)
                ok = True
            except Exception as e:
                log.warning(f"通知发送失败（{channel}）: {e}")
                ok = False

        if ok:
            log.info(f"通知发送成功（{channel}）: {title}")
        return ok

    def send_start(self, map_name=""):
        """开始锄地通知"""
        if not self.config.get("notify_on_start", False):
            return False
        title = "🚀 Fhoe-Rail 开始锄地"
        content = f"时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if map_name:
            content += f"\n地图：{map_name}"
        return self.send(title, content)

    def send_end(self, summary: dict = None):
        """结束锄地通知（含统计摘要）"""
        if not self.config.get("notify_on_end", True):
            return False
        title = "✅ Fhoe-Rail 锄地完成"
        content = f"时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if summary:
            for k, v in summary.items():
                content += f"\n{k}：{v}"
        return self.send(title, content)

    def send_error(self, error_text=""):
        """出错通知"""
        if not self.config.get("notify_on_error", True):
            return False
        title = "❌ Fhoe-Rail 运行出错"
        content = f"时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if error_text:
            content += f"\n{error_text[:800]}"
        return self.send(title, content)

    def send_test(self):
        """发送测试通知（WebUI 测试按钮用）"""
        return self.send("🧪 Fhoe-Rail 测试通知",
                         f"这是一条测试消息\n时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n如果收到说明配置正确")


def get_error_summary(exc) -> str:
    """从异常生成简短摘要"""
    tb = traceback.format_exc()
    lines = [l for l in tb.splitlines() if l.strip()]
    return "\n".join(lines[-6:])
