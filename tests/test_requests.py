"""utils/core/requests.py —— httpx 封装：超时、状态码与下载行为。"""

import asyncio

import httpx
import pytest

import utils.core.requests as requests_module
from utils.core.requests import download, get, post


def run(coro):
    return asyncio.run(coro)


class RecordingClient:
    """记录构造与 stream 参数的最小 AsyncClient 替身。"""

    def __init__(self, stream, recorder):
        self._stream = stream
        self._recorder = recorder

    def __call__(self, *args, **kwargs):
        self._recorder.append(("client", kwargs))
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def stream(self, **kwargs):
        self._recorder.append(("stream", kwargs))
        return self._stream

    async def get(self, *args, **kwargs):
        self._recorder.append(("get", kwargs))
        return self._response

    async def post(self, *args, **kwargs):
        self._recorder.append(("post", kwargs))
        return self._response


class FakeStream:
    def __init__(self, chunks, status_code=200, headers=None):
        self.chunks = chunks
        self.status_code = status_code
        self.headers = headers if headers is not None else {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def aiter_bytes(self, size):
        for chunk in self.chunks:
            yield chunk

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=None, response=None
            )


@pytest.fixture(autouse=True)
def silence_tqdm(monkeypatch):
    """tqdm 的输出对断言没有价值，且会拖慢小文件的循环。"""
    monkeypatch.setattr(
        requests_module.tqdm.asyncio, "tqdm", lambda iterable, **kwargs: iterable
    )


class TestGetAndPost:
    @pytest.fixture
    def recorder(self, monkeypatch):
        entries = []
        client = RecordingClient(None, entries)
        client._response = "RESPONSE"
        monkeypatch.setattr(requests_module.httpx, "AsyncClient", client)
        return entries

    def test_get_forwards_params_and_timeout(self, recorder):
        result = run(get("https://example.invalid", params={"a": 1}))
        assert result == "RESPONSE"
        kwargs = dict(recorder)["get"]
        assert kwargs["params"] == {"a": 1}
        assert kwargs["timeout"] == 20

    def test_get_default_timeout_is_twenty_seconds(self, recorder):
        run(get("https://example.invalid", timeout=99))
        assert dict(recorder)["get"]["timeout"] == 99

    def test_post_forwards_json(self, recorder):
        run(post("https://example.invalid", json={"content": "hi"}))
        kwargs = dict(recorder)["post"]
        assert kwargs["json"] == {"content": "hi"}
        assert kwargs["timeout"] == 20


class TestDownload:
    @pytest.fixture
    def recorded(self, monkeypatch):
        entries = []
        holder = {}

        def client_factory(*args, **kwargs):
            entries.append(("client", kwargs))
            return RecordingClient(holder["stream"], entries)

        monkeypatch.setattr(requests_module.httpx, "AsyncClient", client_factory)
        return entries, holder

    def test_writes_the_full_body(self, tmp_path, recorded):
        entries, holder = recorded
        holder["stream"] = FakeStream([b"hello ", b"world"])
        target = tmp_path / "out.bin"

        run(download("https://example.invalid/file.zip", target))

        assert target.read_bytes() == b"hello world"

    def test_creates_parent_directories(self, tmp_path, recorded):
        entries, holder = recorded
        holder["stream"] = FakeStream([b"x"])
        target = tmp_path / "deep" / "nested" / "out.bin"

        run(download("https://example.invalid/file.zip", target))

        assert target.exists()

    def test_follows_redirects(self, tmp_path, recorded):
        entries, holder = recorded
        holder["stream"] = FakeStream([b"x"])

        run(download("https://example.invalid/f", tmp_path / "out.bin"))

        assert dict(entries)["stream"]["follow_redirects"] is True

    @pytest.mark.xfail(
        strict=True,
        reason="download 是全项目唯一没传 timeout 的请求（get/post 都有 20 秒），"
        "网络卡住时会永久挂起",
    )
    def test_applies_a_timeout(self, tmp_path, recorded):
        entries, holder = recorded
        holder["stream"] = FakeStream([b"x"])

        run(download("https://example.invalid/f", tmp_path / "out.bin"))

        client_kwargs = dict(entries)["client"]
        stream_kwargs = dict(entries)["stream"]
        assert "timeout" in client_kwargs or "timeout" in stream_kwargs

    @pytest.mark.xfail(
        strict=True,
        reason="没有检查状态码，404/500 的 HTML 错误体会被原样写成 zip 文件，"
        "之后才靠 BadZipFile 兜底",
    )
    def test_raises_for_error_status(self, tmp_path, recorded):
        entries, holder = recorded
        holder["stream"] = FakeStream([b"<html>404</html>"], status_code=404)
        target = tmp_path / "out.bin"

        with pytest.raises(httpx.HTTPStatusError):
            run(download("https://example.invalid/f", target))

    def test_error_body_is_currently_written_verbatim(self, tmp_path, recorded):
        """记录当前行为：错误响应被当作正常内容落盘。"""
        entries, holder = recorded
        holder["stream"] = FakeStream([b"<html>404 not found</html>"], status_code=404)
        target = tmp_path / "out.bin"

        run(download("https://example.invalid/f", target))

        assert target.read_bytes() == b"<html>404 not found</html>"
