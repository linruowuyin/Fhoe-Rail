# utils/ 测试套件

用 pytest 覆盖 `utils/` 下的全部 32 个模块，**不需要游戏在运行、不需要 1920x1080 窗口**。

## 运行

```bash
py -m pytest tests/
```

只跑某个模块：

```bash
py -m pytest tests/test_handle.py -v
```

依赖 `pytest`，并建议安装 `pytest-timeout`（`pytest.ini` 里配了 120 秒超时）。
`utils` 里有好几处 `while True` / `while dev_restart` 循环，替身写得不当时会静默挂死，
超时能把这种情况变成一条失败而不是一个卡住的 CI：

```bash
py -m pip install pytest pytest-timeout
```

## 设计约定

**不接触真实环境。** 所有窗口、截图、键鼠调用都用替身替换。测试在临时目录里跑，
并在收集阶段就把 cwd 切走，所以不会在仓库根目录留下 `config.json` / `logs/`。

**依赖注入优先于伪造构造链。** `Handle`、`MapOperations`、`Calculated` 这类对象的
`__init__` 会连锁构造 `Window()`（需要游戏窗口），因此单测用 `make_instance` 夹具
直接注入依赖、跳过 `__init__`：

```python
def test_something(make_instance):
    instance = make_instance(Handle, cfg=..., img=...)
```

**单例之间互相隔离。** `utils` 大量使用 `SingletonMeta`，`conftest.py` 的 autouse
夹具会在每个用例前后清空 `SingletonMeta._instances`、`MapInfo._maps_cache`
和图片缓存（`vision.images.clear_cache()`），否则上一个用例的配置对象会泄漏到下一个。

**改配置要用 `set_config` 夹具，别直接写 `cfg.config_file[...]`。**
那改的是内存缓存，而 `ConfigurationManager` 会在文件 mtime 变化时整体重读，
把内存改动丢掉。Windows 上 `time.time()` 只有约 15.6ms 粒度，这个比较会**偶发**
为真 —— 于是套件会在毫不相干的用例上随机变红。`set_config` 写磁盘再让管理器
重读，与生产路径（`modify_json_file`）一致，结果确定：

```python
def test_something(self, game_map, set_config):
    set_config(game_map.cfg, forbid_map=["1"])
```

（`test_config.py` 里直接操作缓存的三处是例外，它们本身就是专门测缓存行为的。）

## xfail 是缺陷清单，不是"跳过"

失败的用例用 `@pytest.mark.xfail(strict=True)` 标记，`reason` 里写清缺陷本身。
这套标记的作用是：

- 现在：测试套件保持绿色，缺陷被记录在案、可检索
- 修好之后：用例会 XPASS，`strict=True` 会把它报成**失败**，提醒你删掉标记

所以如果看到 XPASS，正确做法是**删掉 xfail 标记**，而不是放宽断言。

`-rx` 可以列出全部 xfail 及其原因：

```bash
py -m pytest tests/ -q -rx
```

## 覆盖分布

测试集中放在 `tests/`，**不跟着源码分层**。测试文件名与被测模块同名，靠名字定位：
`test_handle.py` ↔ `utils/flows/handle.py`。测试是一道统一的门禁，分到各层会变成多次运行；
`conftest.py` 是共享基建，只能有一份。真正需要跟代码放一起的是**样板图**，
那个放 `utils/vision/golden/`——它是被代码消费的资源，不是测试数据。

| 测试文件 | 覆盖模块 |
| --- | --- |
| `test_singleton.py` | `utils/core/singleton` |
| `test_exceptions.py` | `utils/core/exceptions` |
| `test_time_utils.py` | `utils/core/time_utils` |
| `test_log.py` | `utils/core/log` |
| `test_requests.py` | `utils/core/requests` |
| `test_notify.py` | `utils/core/notify` |
| `test_map_info.py` | `utils/core/map_info` |
| `test_report.py` | `utils/core/map_statu` + `utils/flows/report` |
| `test_config.py` | `utils/config/config` |
| `test_window.py` | `utils/drivers/window` |
| `test_mouse_event.py` | `utils/drivers/mouse_event` |
| `test_keyboard_event.py` | `utils/drivers/keyboard_event` |
| `test_img.py` | `utils/vision/img`（Img 门面） |
| `test_matcher.py` | `utils/vision/matcher` |
| `test_pause.py` | `utils/ui/pause` |
| `test_blackscreen.py` | `utils/vision/blackscreen` |
| `test_get_angle.py` | `utils/vision/get_angle` |
| `test_mini_asu.py` | `utils/vision/mini_asu` |
| `test_handle.py` | `utils/flows/handle`（含战斗簇，见 `utils/flows/combat`） |
| `test_calculated.py` | `utils/flows/calculated` |
| `test_monthly_pass.py` | `utils/flows/monthly_pass` |
| `test_map.py` | `utils/flows/map` + `utils/core/map_move` |
| `test_map_operations.py` | `utils/flows/map_operations` |
| `test_setting.py` | `utils/ui/setting` |
| `test_map_selector.py` | `utils/ui/map_selector` |
| `test_text_window.py` | `utils/ui/text_window` |
| `test_record.py` | `utils/ui/record` |
| `test_convert.py` | `tools/convert` |
| `test_update_file.py` | `tools/update_file` |
| `test_install_requirements.py` | `tools/install_requirements` |
| `test_shutdown.py` | `tools/shutdown`（只做静态检查，见下） |

## 三个例外

**`tests/test_architecture.py` 不是模块测试，是架构契约。**
它扫描源码的 AST，强制两件事：

1. **硬规则**（今天即成立，没有豁免名单）：依赖必须单向向下；`utils/core/` 不得
   import `cv2/win32*/pyautogui/pynput`；各层 `__init__.py` 必须为空。
2. **棘轮**（现有违规登记在名单里，**只减不增**）：谁可以 import OS 输入库、谁可以
   import `cv2`、谁有 import 期副作用、谁有星号导入。

每个棘轮名单都配了一条 `test_allowlist_has_no_stale_entries`：你修好某个文件后，
它会提醒你从名单里删掉那一行。**名单长度就是技术债的刻度尺。**
规则与迁移顺序见仓库根目录的 `CLAUDE.md` §2。

**`tools/` 不是包。** 它是按路径调用的脚本目录（没有 `__init__.py`），
`test_architecture.py` 里有一条专门守护这一点——一旦它变成包，就会诱导别人 import 那些脚本。

**`tools/shutdown.py` 不允许被 import。** 它跑的是 Tk 事件循环。
2026-09 之前它在模块级创建根窗口并调用 `mainloop()`，导致任何
`import tools.shutdown` 都永久阻塞、30 秒后还会启动关机倒计时；
现在 GUI 全部收在 `main()` 里、加了 `__main__` 守卫。
`test_shutdown.py` 除了 AST 静态分析，还会**用子进程真跑一次 import**
（那才是当初出问题的行为），并守护"没有任何模块 import 它"。
