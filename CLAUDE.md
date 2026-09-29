# Fhoe-Rail —— 工程规则（给 AI 与人类协作者）

本项目的本质：**截图 → 模板匹配 → 模拟键鼠 → 驱动一个我们完全无法控制的外部进程（游戏）**。

所有规则都从这一条约束推出来：被测系统不可控、不可重置、不可快照、且每隔几周就会被官方更新打碎一次。
这不是普通的 Python 项目，常规的 TDD / 分层经验需要改造后才成立。

> 现状快照（2026-09）：`utils/` 已按 core / drivers / vision / flows / ui 分层，
> 独立脚本收在 `tools/`；`handle.py` 已从 1173 行拆到 466 行（三簇全出，
> 且已不直接依赖任何 OS 库）；
> 129 处 `time.sleep`；44 处宽泛 `except`（含 5 处 `BaseException`）；
> 15 个模块直接 import `win32*/pyautogui/pynput`；10 个直接 import `cv2`。
> 分层本身已由 `tests/test_architecture.py` 强制；库耦合仍是棘轮，见 §2.3。

---

## §1 开发顺序

### 1.1 一条核心原则

> **测量的顺序：不确定性从高到低。实现的顺序：可验证性从高到低。**

图像识别是全项目不确定性最高的部分——阈值多少才算匹配上、游戏更新后还剩多少余量，**只能从真实画面里量出来**。
所以它必须被**最先测量**，却**最后实现**。反过来，键值分发、路径解析、时间计算这些能确定性验证的，
**最先实现**，因为它们是你后面所有工作的地基。

违反这条顺序的典型症状：先写了 800 行编排，最后发现"传送点图标在夜间场景下匹配度只有 0.82"，
于是所有阈值和分支条件全部推倒重来。

### 1.2 阶段 0 — 可行性探针（一次性，可以不合并）

在写任何架构之前，先量数字。抓真实截图，跑真实的匹配，记录**实测匹配度区间**。

产出物是一张表，不是代码：

| 元素 | 样板图 | 正样本匹配度 | 负样本最高匹配度 | 选定阈值 | 余量 |
| --- | --- | --- | --- | --- | --- |
| 主界面灯泡 | `main_ui.png` | 0.97–0.99 | 0.61 | 0.90 | 0.07 |
| 传送点 | `transfer.png` | 0.94–0.98 | 0.83（相似图标） | 0.93 | 0.01 ⚠️ |

**规则**：探针代码不合并，只合并它量出来的数字。余量 < 0.03 的行要标警告——那是随时会碎的阈值。

### 1.3 阶段 1 — 契约与资源（先于代码）

**先定数据模型，再写逻辑。** 这一步的产物是：

1. `core/models.py`：`MapStep` / `Route` / `Detection` / `RunStats` 等类型
2. `core/schema.py`：地图 JSON 的**校验器**——目前完全没有，任何手写错的 JSON 都能一路跑进游戏才炸
3. `core/thresholds.py`：阶段 0 量出的所有阈值常量，**每条注明来源与实测值**
4. `vision/golden/`：样板图入库

**规则**：
- 没有 schema 的地图 JSON 不允许进仓库
- 没有样板图的检测器不允许写
- 没有标明来源的阈值不允许写进代码

### 1.4 阶段 2 — 纯逻辑（严格 TDD）

**只有这一层配得上"测试驱动开发"这个说法**，也**必须**先写测试。

适用：步骤键值分发、周几判定、路径拼接、配置解析、阈值衰减、报告格式化、时间窗口计算。

这些函数的特征：**输入输出都是纯数据，不碰画面、不碰时钟、不碰文件系统**。
`tests/test_map_operations.py::TestStartStepDispatch` 是这一层的范例——它把 30 多个步骤键的
分发逐条钉死，改动路由表时会立刻报错。

### 1.5 阶段 3 — 检测器（黄金图测试）

每个 UI 元素一个检测器，输入是录下来的截图，输出是 `Detection(value, position)`。

**测试要求**：每个检测器至少 1 个正样本 + **2 个负样本**。
负样本必须是"看起来像但不是"的画面——**只测正样本的检测器等于没测**，
它会对任何输入返回高匹配度而你毫无察觉。

阈值全部从 `core/thresholds.py` 取，测试里断言"在样板图上 ≥ 阈值"，
并**顺带记录当前实测值**，这样游戏更新后余量收窄能被立刻看见。

### 1.6 阶段 4 — 编排（替身 + 假时钟）

流程层。测试用替身检测器 + **可注入的时钟**，断言的是：

- **动作序列**：按了什么键、点了哪里、顺序对不对
- **时间预算**：这一步最多等多久、超时后走哪条分支
- **退出条件**：任何 `while` 都必须能退出

**绝不断言像素。** 编排层的测试不该知道画面长什么样。

### 1.7 阶段 5 — 回放 / 端到端

断言对象是**日志与运行报告**，不是画面。例如"这次跑图战斗次数 > 0 且未出现 F 键错误"。

回放优先于实机：把一次真实运行录下来的输入轨迹重放，能覆盖大量分支而不需要游戏在前台。

### 1.8 修改既有行为时的顺序

> **先写能复现问题的测试，再改代码。**

复现测试可以是：一段录制的截图、一个替身、或一个纯数据用例。
`tests/` 里已有的 31 个 `xfail` 就是这类测试的标准形式——它们把已知缺陷钉住，
修好之后会自动 XPASS 报错，提醒你更新标记。

---

## §2 目录结构与依赖方向

### 2.1 当前结构（分层已建立，2026-09）

```
Fhoe-Rail/
├─ fhoe.py                    # 入口：参数解析、装配、顶层异常
│
├─ utils/                     # 全部产品代码
│  ├─ core/                   # 【底层】纯逻辑 + 基础设施
│  │  ├─ singleton.py         #   单例元类
│  │  ├─ exceptions.py        #   CustomException
│  │  ├─ time_utils.py        #   时间格式化 / 刷新点计算
│  │  ├─ log.py               #   loguru 配置 + webhook 转发
│  │  ├─ requests.py          #   httpx 封装
│  │  ├─ notify.py            #   多渠道通知
│  │  ├─ map_info.py          #   地图元数据解析
│  │  ├─ map_statu.py         #   单轮运行状态容器
│  │  ├─ map_move.py          #   地图拖动坐标常量表
│  │  ├─ schema.py            #   地图 JSON 校验器
│  │  ├─ json_io.py           #   地图 JSON 写盘格式（R22）
│  │  ├─ map_names.py         #   版本 / 星球 / 区域的中文展示名（R23）
│  │  └─ thresholds.py        #   识图阈值常量表（R11）
│  ├─ config/                 # 配置读写 + 完整性修复
│  │  └─ config.py
│  ├─ drivers/                # 【适配层】唯一允许碰 win32/pyautogui/pynput 的地方
│  │  ├─ screen.py            #   截图（PrintWindow / ImageGrab），不 import cv2
│  │  ├─ window.py            #   窗口查找 / 激活 / 矩形
│  │  ├─ mouse_event.py       #   鼠标与键盘输入原语（只做设备操作）
│  │  └─ keyboard_event.py    #   按键按下/释放
│  ├─ vision/                 # 【识别层】
│  │  ├─ img.py               #   Img 门面：组合下面三者，全项目 129 处调用它
│  │  ├─ matcher.py           #   模板匹配、界面判定、找到图就点它
│  │  ├─ images.py            #   模板图加载与缓存
│  │  ├─ arrow.py             #   小地图箭头（HSV 取色 + 360 度匹配）
│  │  ├─ colors.py            #   色域判定（按 HSV 区间找颜色）
│  │  ├─ viewer.py            #   调试图片窗口（cv2 显示接口）
│  │  ├─ blackscreen.py       #   黑屏判定
│  │  ├─ get_angle.py         #   箭头朝向
│  │  └─ mini_asu.py          #   小地图方向
│  ├─ flows/                  # 【编排层】
│  │  ├─ handle.py            #   动作分发门面（466 行）
│  │  ├─ combat.py            #   战斗判定与结算
│  │  ├─ movement.py          #   移动、疾跑检测、系统卡顿识别
│  │  ├─ orientation.py       #   视角设置 / 重置 / 旋转 / 校准
│  │  ├─ map_operations.py    #   跑图主流程
│  │  ├─ map.py               #   地图拖动 / 传送点查找
│  │  ├─ calculated.py        #   加载检测 / 购买 / 1 号位
│  │  ├─ monthly_pass.py      #   月卡
│  │  └─ report.py            #   运行报告
│  └─ ui/                     # 顶层（与 flows 平级）：交互入口
│     ├─ setting.py           #   设置菜单
│     ├─ map_selector.py      #   选图菜单
│     ├─ text_window.py       #   开发者调试窗口
│     ├─ pause.py             #   F7~F10 热键 + 调试图片显示
│     └─ record.py            #   --record 录制模式（被 fhoe.py import）
│
├─ tools/                     # 按路径调用的独立脚本（不是包，没有 __init__.py）
│  ├─ convert.py              #   地图 JSON 字段批量替换
│  ├─ update_file.py          #   资源更新
│  ├─ install_requirements.py #   依赖安装（bat / WebUI 按路径调用）
│  ├─ shutdown.py             #   倒计时关机 GUI（GUI 收在 main() 内，见 §3.5 R16）
│  ├─ validate_maps.py        #   地图 JSON 校验（CI 门）
│  ├─ format_maps.py          #   地图写盘格式：检查 / --write 重排（CI 门，R22）
│  └─ convert_to_webp.py / map_res_list.py / map_simplify.py / test.py
│
├─ data/                      # 运行时资源：map/ picture/
└─ tests/                     # 测试集中一处，不跟着源码分层
   ├─ test_<模块名>.py        #   与被测模块同名，靠名字定位
   └─ fixtures/               #   （规划中）截图样例、地图 JSON 样例
```

样板图放 `utils/vision/golden/`（随代码版本化），不放 `tests/`——它是**被代码消费的资源**，
不是测试数据。

### 2.2 依赖方向（已由测试强制）

```
   flows/   ui/                ← 顶层：可以依赖下面全部（ui 要展示识别结果、响应热键）
      │      │
      ↓      ↓
   vision/  drivers/            ← vision 可以依赖 drivers（识别要拿帧）；drivers 不能反向依赖
      ↘      ↙
      core/  +  config/         ← 最底层，被各层共用
```

| 规则 | 状态 | 拦法 |
| --- | --- | --- |
| 依赖单向向下，`core` 不依赖上层 | ✅ **已强制** | `tests/test_architecture.py::TestLayerDirection` |
| `core/` 不 import `cv2 / win32* / pyautogui / pynput` | ✅ **已强制** | `::TestCoreIsPure` |
| 各层 `__init__.py` 保持为空 | ✅ **已强制** | `::TestLayerDirection` |
| 只有 `drivers/` import `win32* / pyautogui / pynput` | ⏳ 棘轮 | `::TestOsCouplingRatchet` |
| 只有 `vision/` import `cv2` | ✅ **已强制** | `::TestVisionIsolation` |
| 禁止 import 时产生副作用 | ⏳ 棘轮 | `::TestImportTimeSideEffects` |
| 禁止星号导入 | ⏳ 棘轮 | `::TestStarImports` |

"✅ 已强制"= 没有豁免名单，违反即失败。"⏳ 棘轮"= 现有违规登记在名单里，**只减不增**。

### 2.3 剩余迁移（按收益 / 风险排序）

已完成：
- ✅ 分层目录建立
- ✅ `tools/` 收纳独立脚本
- ✅ 修 `Img` 单例问题：`Img` 收为单例（7 处 `Img()` 现在共用一个实例），
  重试标志改由 `MouseEvent.last_search_allow_retry` 承载，`retry_in_map`
  重试分支恢复生效
- ✅ 阈值集中到 `core/thresholds.py`（48 个常量，数值为实机验证过的当前最佳值）
- ✅ `tools/shutdown.py` 加 `__main__` 守卫（导入不再阻塞）
- ✅ 拆 `drivers/img.py`：截图 → `drivers/screen.py`，图片资源 → `vision/images.py`，
  匹配与「找到图就点它」→ `vision/matcher.py`，`Img` 变成组合三者的门面。
  `MouseEvent` 相应退回纯输入层，`drivers/pause.py` 移到 `ui/`。

- ✅ 拆 `Handle` 第三簇：移动 → `flows/movement.py`（`handle_move` 117 行 +
  疾跑线程一族，含 2 个 async）。与战斗的交叉用注入 `combat` 解决；
  `fight_in_map` 归 `Combat`。pynput 调用转经 `KeyboardEvent.press_key/release_key`，
  因此名单没有增长。`handle.py` 698 → 466 行。

  至此 `Handle` 从 1173 → 466 行，**棘轮名单没有一次因拆分而变长**。
- ✅ 拆 `Handle` 第二簇：视角 → `flows/orientation.py`（编排）+
  `vision/arrow.py`（HSV 取箭头、360 度匹配）。**按职责而不是按调用关系切**：
  cv2 部分留在 vision，flows 不新增图像库依赖。`Handle` 698 行。
- ✅ 拆 `Handle` 第一簇：战斗 → `flows/combat.py`（10 个方法 + 战斗计数）。
  `Handle` 保留装配与 `handle_fighting` / `handle_e` 两个委派入口；
  计数改由 `handle.combat.X` 访问（map / map_operations / report 共 5 处）。
  拆的过程中顺手把 `win32api.GetCursorPos` 与 5 处 `pyautogui.press` 也赶进了 drivers，
  所以 `flows/combat.py` **没有**进入 OS 棘轮名单 —— 名单长度前后不变。

- ✅ 清 `flows/handle.py` 的 OS 调用：`pyautogui.press` → `KeyboardEvent.keyboard_press`、
  `win32api.keybd_event` → `KeyboardEvent.tap_escape`、`pyautogui.scroll` →
  `MouseEvent.scroll`。**`handle.py` 已出 OS 棘轮名单**（8 → 7 条）。

  注意 `tap_escape` 保留了 `keybd_event` 注入路径而**没有**合并到 pynput —— 同一个
  文件里 ESC 有两种按法，那个是原作者的明确选择，两种 API 送的 scancode 不同，
  没有实机验证前不要合并。

- ✅ 清 `flows/` 里剩下的 cv2 跨层用法：`map.py` 的取反色 → `Img.invert`、
  `calculated.py` 的 HSV 色域判定 → `vision/colors.py`、`monthly_pass.py`
  的 `import cv2` 是死导入直接删。
- ✅ `ui/pause.py` 的调试图片显示 → `vision/viewer.py`。

  **VISION 名单已清空（10 → 0）**，于是这条从棘轮升级成硬规则
  （`TestVisionIsolation`，没有豁免名单）。至此 `flows/` 与 `ui/` 下不再出现 cv2。

- ✅ 清 `flows/` 剩余的直接 OS 调用：`map.py` / `calculated.py` /
  `map_operations.py` 的 `pyautogui.press` / `keyDown` / `keyUp` / `click` 全部
  转经 `KeyboardEvent` / `MouseEvent`。**`flows/` 下已无任何 OS 库直接依赖**，
  OS 名单 7 → 4 条。

  剩下的 4 条性质不同，不是同一类债：`get_angle.py`（pynput 截图）、
  `ui/pause.py`（keyboard 热键）、`ui/record.py`（pynput 录制）、`fhoe.py`（入口）。
  它们各自就是"监听设备"的本职，要动得单独设计，不该硬塞进 drivers。

至此 `CLAUDE.md` 的迁移清单走完。
2. **清 `flows/` 里剩下的 cv2 / pyautogui 跨层用法**：`calculated.py` /
   `map.py` / `monthly_pass.py`。
3. **给 `core/thresholds.py` 逐条补余量标注**（§1.2 的那张表）。
   48 个常量的**值**已经是对的，但"哪条余量大、哪条一碰就碎"没有写下来。
   余量小的阈值在游戏更新后最先碎，标出来才知道该先怀疑谁。

**关于棘轮**：名单在 2026-09 改成了只登记**跨层**违规 —— `drivers/` 碰 OS、
`vision/` 用 cv2 是那两层存在的理由，不算债。改完当场从 12/10 条降到 8/5 条。
真正要还的是 `flows/` 与 `ui/` 里剩下那些：`map.py` / `calculated.py` /
`monthly_pass.py` 直接用 cv2 或 pyautogui。

每完成一步，先看 `tests/test_architecture.py` 的棘轮名单能不能缩短——能缩短就缩短，
不能缩短也没关系：**名单长度只是技术债的一个侧面指标，不是唯一目标。**
更重要的是结构本身变清楚了（一个模块一件事、边界能被测试钉住）。

---

## §3 硬规则

每一条都对应一个已实际发生过的故障。

### 3.1 时间

**R1 — 不许用 `sleep` 对齐游戏状态。**
用"轮询等待某个状态出现 + 超时"。`sleep` 对齐在机器快时浪费、慢时出错。
现状：129 处 `time.sleep`，`handle.py` 占 65 处——这里是最大的技术债来源。

**R2 — 计时循环里必须有 `time.sleep`，否则就是忙等。**
已发生的故障：`handle_move` 的计时循环三个分支条件全假时变成 100% CPU 空转，
既费电又会跟后台截图线程抢 GIL，反过来制造出代码自己检测的"系统卡顿"。
（`tests/test_handle.py::test_does_not_burn_cpu_while_waiting`）

**R3 — 任何 `while` 必须有超时或明确退出条件。**
`handle_orientation` 的 `while True` 只有"黑屏消失"一个出口；黑屏检测持续异常时永久循环。
写 `while` 时先问：**最坏情况下它靠什么退出？**

**R4 — 时间必须可注入。**
业务代码不要直接调 `time.time()` / `time.sleep()`，用 `core/ports.py` 的 `Clock`。
否则测试只能去替换整个 `time` 模块（见 `tests/test_handle.py` 的 `TickingTime`，那是权宜之计）。

### 3.2 输入

**R5 — 按键必须成对释放，且 `press` 要在 `try` 里面。**
已发生的故障：`handle_move` 的 `press(key)` 在 `try` 之外，若它抛异常，
下面的 `finally` 不会执行，Shift 和方向键会卡在按下状态。
（`tests/test_handle.py::test_releases_direction_and_shift_keys_on_error`）

**R6 — 修饰键用状态比对，不要无条件释放。**
ALT/SHIFT 被释放前要比较初始状态，避免把用户自己按住的键给放了。
（`mouse_event.click_target_with_alt` 是正确范例）

**R7 — 前台窗口锁是常态，不是异常。**
`SetForegroundWindow` 在后台进程里经常失败，需要 `AttachThreadInput` + 重试。
任何"切到前台"的代码都要假定第一次会失败。

### 3.3 画面

**R8 — 分辨率与 DPI 必须在启动时校验并拒绝运行，而不是只打警告。**
`get_width.py` 现在只 `log.warning`，于是窗口不是 1920×1080 时，
`cal_screenshot()` 会算出一个比窗口还大的截图区域，静默拍进桌面其它内容。

**R9 — 截图失败要抛明确异常，不要返回 `None`。**
已发生的故障：`Img.take_screenshot` 在窗口不可见时隐式返回 `None`，
而 8 个调用点都在做 5 元组解包 → 用户看到 `TypeError: cannot unpack non-sequence NoneType`。
（`tests/test_img.py::test_raises_when_window_invisible`）

**R10 — 同一帧不要重复截图。**
`have_screenshot` 对列表里每张图各调一次 `scan_screenshot`，每次重新抓屏；
`find_scene` 一轮最多因此抓 12 次全窗口截图。已有 `scan_temp_screenshot` 可复用同一帧。

**R11 — 阈值集中在 `core/thresholds.py`，每条注明来源。**
散落的 `> 0.95` 无法审计。游戏更新后需要一次性重新校准全部阈值时，集中管理是唯一可行方式。

**R12 — 检测器必须能返回"没找到"，而不是抛异常。**
`Img.get_img` 返回 `None` 后，多处直接喂给 `cv2.bitwise_not` / `matchTemplate` 才炸。

### 3.4 状态

**R13 — 单例要一致：要么是单例，要么显式传递，不许"一半单例"。**
曾经的故障：`Window`/`MouseEvent`/`Handle`/`MapInfo` 是单例而 `Img` 不是，
于是 `mouse_event` 写的重试标志传不到 `map_operations`，整个 `retry_in_map`
重试机制静默失效。**这曾是全项目最贵的一个 bug**：它不报错，只是功能不再生效。
（已于 2026-09 修复：`Img` 收为单例，标志改由 `MouseEvent.last_search_allow_retry` 承载。）

**由此得到的规则：跨模块状态必须放在「读取方真正持有的那个单例」上。**
不是"放在某个单例上就行"——读的一方必须能在自己手上拿到它。
`map_operations` 持有 `self.mouse_event`，所以标志归 `MouseEvent`；
`Img` 即使变成单例也不该承载业务流程的状态。
钉住这条教训的测试：`test_map_operations.py::TestRetryFlagPlumbing`。

**R14 — 配置是全局可变状态：读取可缓存，但必须能失效。**
`ConfigurationManager.config_file` 会整体替换内部 dict，任何缓存了旧 dict 引用的对象
（如 `Notify`）在运行期改配置后不会更新。读配置请**每次取 `cfg.config_file`**，不要存引用。

**R15 — 模块级可变全局必须有明确的所有者和清理点。**
`TEXT_WINDOWS` / `_INSTALLED_HANDLERS` / `_IMG_CACHE` / `_maps_cache` 目前都是裸字典/列表。
新增时要问：谁负责清？进程退出时怎么收？

### 3.5 结构

**R16 — 禁止 import 时做事。**
曾经的故障：`tools/shutdown.py` 在模块级 `tk.Tk()` + `mainloop()`，
任何 `import tools.shutdown` 都会永久阻塞，30 秒后还会启动关机倒计时。
（已于 2026-09 修复：GUI 全部收进 `main()`，加 `__main__` 守卫。）
同一类问题还在别处：`ui/map_selector.py` 在 import 时构造 `Setting()`（会读地图目录），
`tools/update_file.py` 在 import 时构造 `ConfigurationManager()`（会在 cwd 建 config.json）。
这些由 `tests/test_architecture.py` 的 `SIDE_EFFECT_ALLOWLIST` 棘轮登记，只减不增。

**规则形式**：模块级只允许 import、`def`、`class` 和常量赋值。
需要建窗口、起线程、读文件、连外部服务的，一律推迟到函数里由入口显式调用。

**R17 — 禁止 God Object。**
`Handle` 44 个方法 / 1150 行，被 4 个模块依赖。新增功能不要往它里面塞。

**R18 — 不要吞异常，尤其不要吞 `BaseException`。**
44 处宽泛 `except`，其中 `update_file.py` 与 `fhoe.py` 的 5 处 `except BaseException`
会把 `KeyboardInterrupt` 一起吞掉——长时间下载无法用 Ctrl-C 中断。
捕获异常时必须明确"我能处理什么"。

**R19 — 独立脚本放 `tools/`，入口加 `if __name__ == "__main__":`。**

### 3.6 资源与更新

**R20 — 资源的完整性校验必须与下载源分离。**
现在的更新流程：下载 URL 由用户配置的第三方代理拼接，解压后直接 `shutil.copy` 覆盖本地文件，
而随后校验用的 MD5 列表**来自同一个远程源**——它只能检测传输损坏，挡不住被接管的代理。

**R21 — 游戏更新会打碎一切：维护一份「冒烟检测器」清单。**
版本更新后第一件事是跑冒烟：主界面、传送点、F 图标等关键检测器是否还能匹配、
匹配度余量还剩多少。这应该在启动时或 `--debug` 下自动跑，而不是等用户报告漏怪。

**R22 — 地图 JSON 只有一个写盘格式：`core/json_io.py::dumps_map`。**
实测 633 个地图文件里，用 `json.dump(indent=4)` 原样重写只有 165 个按行内容不变：
缩进有 4 / 2 / 顶格 / 7 空格四种，221 个文件里还混着 Tab（手改留下的 `\t\t},`）。
混排到这种程度，「保存时保留原格式」根本做不到——没有任何缩进设置能还原
「一半空格一半 Tab」。所以写盘一律重排成规范形式：**4 空格缩进 + 短数组内联 +
末尾不加换行**。短数组内联是 633 个文件里唯一没有例外的写法（113 处）；
`json.dump` 会把 `"click_offset": [60,0]` 拆成 5 行、`"floor": [[1,2,3],1]`
拆成 9 行，这才是保存后 diff 变脏的大头。代价是某个文件**第一次**被重写会重排
整份，收益是之后同一文件再改就只剩真正改动的那几行（实测连写三次，后两次零 diff）。

三个写入方 —— webui 保存、`ui/record.py` 录制、`tools/convert.py` 批量替换 ——
都调这一个序列化器，**别再各写一套**。`tests/test_map_json_format.py` 钉住这个
契约（内联规则 + 整库收敛 + 三个写入方必须都引用它）。

门在 CI：`.github/workflows/run.yml` 的 `Check changed map JSON format` →
`tools/format_maps.py`，**只拦本次改动的地图**。全库 633 张里 471 张是历史格式
（大多来自上游），卡全库等于要求一次性重排 471 个文件 —— PR 会被纯空白改动淹没，
之后上游每改一张图还会跟本地冲突。所以：碰过的图必须规范，没碰的一张都不动。
非规范时按提示跑 `python tools/format_maps.py --write`（在 webui 里把那张图
保存一次也等效）。`tests/test_format_maps.py` 钉住「只查改动的」这条门规。

**R23 — 展示名（版本 / 星球 / 区域）只在 `core/map_names.py` 一处维护。**
以前这些中文名散在四处：`webui/server.py` 的 `PLANET_NAMES` / `VERSION_NAMES`、
`ui/map_selector.py` 的 `PLANET_LABELS`（逐字重复一份）、`ui/setting.py` 提示语里手写
的一段（提到目录里**已经不存在**的 `SilverWolfLv999`）、README 的表格，外加前端
`index.html` 的 `PLANET_EMOJI`。漏项就是这么来的：磁盘上有 `default_lite`，表里没有，
图鉴标签和指挥台一直显示裸目录名。

- 新增版本目录 / 星球编号后，去 `core/map_names.py` 补一条。`tools/validate_maps.py`
  会检查覆盖（缺了 exit 1，CI 拦），`tests/test_map_names.py` 还盯住「库里有几个
  版本/星球，表里就得有几个」—— 就是这条能拦住 `default_lite` 那种漏项。
- **区域**（"主控舱段"）不用登记：633 张图的 `name` 100% 是「区域-序号」，从名字里
  派生；写歪的（如「绥  园」多打了个空格）在 `AREA_NAMES` 里覆盖显示名。名字不符合
  这个形状时校验器只提醒（它会在图鉴里自成一类）。
- 前端不再有名字表：星球名与 emoji 都由 `/api/maps` 下发。
- README 里那张版本表是**给人看的文档**，保留手写 —— 但改版本中文名时要一起改
  （它是四处副本里唯一保留的一处，因为带说明文字）。

---

## §4 测试

```bash
py -m pytest tests/          # 585 passed, 31 xfailed, utils/ 覆盖率 64%
py -m pytest tests/ -q -rx   # 列出全部 xfail 及其原因 = 已知缺陷清单
```

**规则**：

- **`xfail` 是缺陷清单，不是"跳过"。** 标记 `strict=True`，`reason` 里写清缺陷。
  修好后它会 XPASS 报错，提醒你删掉标记。
- **不要为了让测试通过而放宽断言或删除 `xfail`。** 如果断言过严，先确认是断言错了还是代码错了。
- **新功能必须带测试。** 纯逻辑放 `tests/unit/`，编排放 `tests/integration/`。
- **单测不允许连接游戏。** 所有窗口、截图、键鼠调用都要有替身。
- 提交前跑一次 `py -m pytest tests/`，以及 `py -m pyflakes <改动的文件>`。

---

## §5 给 AI 的工作流

在这个仓库里干活时：

1. **改之前先跑相关测试。** 改 `handle.py` 前跑 `tests/test_handle.py`，改路由表前跑 `TestStartStepDispatch`。
2. **新增模块前先想清楚放哪一层**——`tests/test_architecture.py` 的棘轮会拦住乱放。
   如果确实需要加进名单，在 PR 描述里说明理由。
3. **新增阈值必须进 `core/thresholds.py`**（迁移完成前，至少集中写在文件顶部并注明来源）。
4. **改既有行为前先写复现测试。**
5. **不要扩大 `utils/` 的平铺目录**——新代码按 §2.1 的目标结构放置。
6. **报告结果要如实。** 测试失败就说失败并贴输出；跳过的步骤要说明。
