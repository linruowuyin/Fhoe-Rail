"""utils/ 测试套件的公共夹具。

设计要点：
1. **不连接游戏**——所有涉及窗口、截图、键鼠的模块都用替身替换，测试可以在
   没有星穹铁道、没有 1920x1080 窗口的机器上运行。
2. **不改动仓库**——见下面「先切 cwd 再 import」。
3. **单例隔离**——utils 里大量使用 SingletonMeta，测试之间必须清空，
   否则前一个测试的配置对象会泄漏到下一个测试。
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# 必须在 import utils.* 之前把 cwd 切到临时目录：
#   * utils/core/log.py 在 import 时就创建 logs/ 并打开日志文件
#   * tools/update_file.py 与 utils/ui/map_selector.py 在 import 时构造
#     ConfigurationManager()，它会按 os.getcwd() 找/建 config.json
# 不先切走的话，光是收集测试就会在仓库根目录留下 logs/日志文件.log 和 config.json。
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_TMP = Path(tempfile.mkdtemp(prefix="fhoe-tests-"))
os.chdir(SESSION_TMP)

import pytest  # noqa: E402

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.config.config import ConfigurationManager  # noqa: E402
from utils.vision import images as image_library  # noqa: E402
from utils.core.log import logger  # noqa: E402
from utils.core.map_info import MapInfo  # noqa: E402
from utils.core.singleton import SingletonMeta  # noqa: E402

DEFAULT_CONFIG = ConfigurationManager.config_keys(real_width=1920, real_height=1080)


def pytest_configure(config):
    """测试模块被 import 之前，补全这个临时工作目录。"""
    (SESSION_TMP / "config.json").write_text(
        json.dumps(DEFAULT_CONFIG, ensure_ascii=False), encoding="utf-8"
    )
    # utils/ui/map_selector.py 在 import 时就构造 Setting()，
    # 而 Setting.__init__ 会读地图版本目录；给一个空壳目录让它能过。
    (SESSION_TMP / "map" / "default").mkdir(parents=True, exist_ok=True)


def pytest_unconfigure(config):
    os.chdir(REPO_ROOT)
    shutil.rmtree(SESSION_TMP, ignore_errors=True)


@pytest.fixture(autouse=True, scope="session")
def _quiet_logger():
    """移除 loguru 的 stdout / 文件 handler。

    既让测试输出干净，也避免 `log.py` 的 patcher 对每条日志都去读 version.txt
    和写日志文件（那会让测试慢一个数量级）。
    """
    logger.remove()
    yield


@pytest.fixture(autouse=True)
def _reset_global_state():
    """清空单例与类级缓存，保证测试互相独立。"""
    SingletonMeta._instances.clear()
    MapInfo._maps_cache.clear()
    image_library.clear_cache()
    yield
    SingletonMeta._instances.clear()
    MapInfo._maps_cache.clear()
    image_library.clear_cache()


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    """把工作目录切到临时目录，并写好一份默认 config.json。

    ConfigurationManager.normalize_file_path() 依赖 os.getcwd()，所以任何
    构造 ConfigurationManager() 的代码都会在 cwd 里读写 config.json。
    """
    (tmp_path / "config.json").write_text(
        json.dumps(DEFAULT_CONFIG, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "version.txt").write_text("test-version", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def repo_root(monkeypatch):
    """把工作目录切回仓库根目录，供需要真实 ./map 与 ./picture 的测试使用。"""
    monkeypatch.chdir(REPO_ROOT)
    return REPO_ROOT


@pytest.fixture
def set_config(isolated_cwd):
    """在测试里修改配置：写进磁盘上的 config.json，并让 ConfigurationManager 重读。

    **不要直接写 `cfg.config_file[...]`。** 那改的是内存缓存，而
    ConfigurationManager 会在文件 mtime 变化时整体重读，把内存改动丢掉；
    Windows 上 `time.time()` 只有约 15.6ms 粒度，这个 mtime 比较会**偶发**为真，
    于是套件会在毫不相干的用例上随机变红（见 CLAUDE.md R14）。

    生产代码改配置一律走 `modify_json_file`（落盘），测试也照做就不会有这个问题。
    """

    def _set(manager, **values):
        path = isolated_cwd / "config.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(values)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        manager._config = None
        manager._last_mtime = None

    return _set


class FakeWindow:
    """Window 的替身：只实现被测代码真正用到的那几个方法。"""

    def __init__(self, rect=(0, 0, 1920, 1080), visible=True, hwnd=12345, client="客户端"):
        self.rect = rect
        self.visible = visible
        self.hwnd = hwnd
        self.client = client
        self.title = "崩坏：星穹铁道"
        self.winrect = rect

    def get_rect(self, hwnd=None):
        return self.rect

    def check_window_visibility(self, depth=0):
        return self.visible

    def switch_window(self):
        return None


def make(cls, **attrs):
    """构造实例但跳过 __init__。

    utils 里的 Handle / MapOperations / Calculated 等“上帝对象”的 __init__ 会
    连锁构造 Window()（需要游戏在运行），单元测试只关心其中一个方法时，
    直接注入依赖比伪造整条构造链更清晰。
    """
    obj = object.__new__(cls)
    for name, value in attrs.items():
        setattr(obj, name, value)
    return obj


@pytest.fixture
def make_instance():
    return make


@pytest.fixture
def fake_window_factory():
    return FakeWindow


@pytest.fixture
def log_records():
    """捕获 loguru 日志，返回 record 列表（record["message"] 是格式化后的文本）。"""
    records = []
    handler_id = logger.add(
        lambda message: records.append(message.record), level="DEBUG", format="{message}"
    )
    yield records
    logger.remove(handler_id)
