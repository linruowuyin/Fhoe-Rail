# 地图 JSON 格式：v1 / v2 双认

> 适用范围：`Fhoe-Rail` 主仓 `map/`、[Fhoe-Rail-Maps](https://github.com/linruowuyin/Fhoe-Rail-Maps)
> 地图仓、fhoe-maps-site 网页作业站。三处的校验与展示规则保持同步。

## 0. 一句话总纲

**运行时规范形永远是 v1 的「单键步骤」。** v2 是「编写格式」：它在进入任何分发表
之前就被 `utils/core/map_format.py::normalize_step` 展开成 v1，所以 runner 的
分发表、movement、既有工具**都不需要知道 v2 的存在**。全项目只有这一个解析点。

v1 文件（没有 `v` 字段）完全不变，逐字节兼容 —— 上游
StarRailAssistant 的地图互导契约不受影响。

## 1. v1 回顾（现状契约）

```jsonc
{
    "name": "区域-1",
    "author": "…",
    "start": [
        {"map": 1},
        {"picture\\transfer.png": 1.5},          // 图片步：文件名混在键名里
        {"picture\\x.png": 0.8, "click_offset": [60, 0]}  // 修饰键跟在同一对象里
    ],
    "map": [{"s": 0.5}, {"a": 0.2}, {"a": 0.2}, {"w": 2.0}]  // 重复步原样抄
}
```

要点：

* 每个步骤是**单键字典**（键 = 动作 / `picture\…` 图片引用）；`start` 条目允许
  附加修饰键（`allow_map_drag` / `allow_scene_drag` / `allow_multi_click` /
  `allow_retry_in_map` / `allow_click_offset` / `allow_drag_exact` /
  `allow_drag_offset`，从整个条目读取）
* 图片键的值 = 点击后的停顿秒数（运行时 `min(value, 0.8)`）
* `map` 里的 `fighting`：1 = 进入战斗，2 = 打障碍物

## 2. v2 步骤字段

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `v` | 顶层版本号 | 只接受 `2`；**没有 `v` 字段 = v1**（不是「未知版本」） |
| `img` | 图片资源 stem，无路径无后缀 | **只允许出现在 `start`**；大小写敏感按 stem 查表 |
| `delay` | 点击后停顿秒数 | 数字；省略 = 0.8（= v1 运行时上限） |
| `rep` | 本步总执行次数 | 整数 ≥ 1；省略 = 1；CI 拦 > 100（运行时兜底夹到 100） |
| `c` | 注释，运行时剥掉 | 字符串；写在哪一层都行 |
| `wait` | **可选**，图片步点击后等画面静止 N 秒再走下一步 | 数字 (0, 30]；**只能跟在 `img` 步上**；省略 = 不检测（老写法行为不变） |

```jsonc
// v2 写法，等价于上面的 v1 示例
{
    "v": 2,
    "name": "区域-1",
    "author": "…",
    "start": [
        {"map": 1},
        {"img": "transfer", "delay": 1.5},
        {"img": "x", "delay": 0.8, "click_offset": [60, 0]},
        {"img": "y", "delay": 0.5, "wait": 2.0}
    ],
    "map": [{"s": 0.5}, {"a": 0.2, "rep": 2}, {"w": 2.0}]
}
```

### 2.1 硬性约束（CI 会拦）

* `img` **仅限 `start`**：实测主仓 633 张（现 875 张）地图里 picture 键 3048 处
  全在 `start`，`map` 从未出现过；v2 校验在 `map` 里直接报错（`map` 步骤前固定
  `back_to_main`（CLAUDE.md R26），图片导航没有意义）
* `map` 里禁止 `img`、修饰键；`fighting` 禁止带 `rep`（打障碍物不可折叠）
* 未知键：v2 的 `start` 直接 error（v1 是 warning）—— 命名字段格式就该严
* v1 文件里出现 `img`/`rep`/`c`/`wait` = 作者想写 v2 忘加 `"v": 2`，报 error 并提示

### 2.1.1 wait：画面静止检测（可选增强）

加载时长随机器浮动，固定 `delay` 是慢机翻车、快机白等的根源。给图片步加
`wait: N` 后，点击收尾完成（含重试判定）会**截帧比较帧差**：帧差均值
低于阈值累计满 N 秒 → 放行；持续变化 → 清零重计；总等待超过兜底上限（15s，
`map_operations.py::WAIT_TIMEOUT`）→ 强制继续，**永不卡死**。等待循环
过暂停检查点，F8/F9 语义与其它检查点一致（F9 = 重跑本图）。

* 适用场景：传送/开图/菜单点击后界面加载不确定的步骤。`transfer` 步本身已有
  地图加载检测（`run_mapload_check`），无需重复添加
* 老地图**不批量迁移**：字段可省略，缺省行为逐字节不变；谁改图谁顺手加
* 阈值/采样参数是 `map_operations.py` 模块常量（`WAIT_DIFF/SAMPLE/WIDTH`），
  游戏内实测后再调；schema 侧值域见 `WAIT_MAX`
* v1 文件出现该键报 error（提示加 `"v": 2`）；`map` 数组里报 error（只跟 img 步）

### 2.2 语义不变量（normalize 承诺）

`normalize_step(step) -> list[dict]`，对一条步骤：

1. v2 → v1 展开：`img` → `"picture\\<stem>.png"` 键 + `delay` 作值；`rep: N`
   → **循环前**展开成 N 份；`c` 剥掉
2. rep 展开的 N 份互相**深拷贝**（改一份不串另一份）
3. 修饰键保持原位（跟在展开后的图片键同一对象里）
4. 非 v2 步骤原样透传（零拷贝，包括 `img` 值非法的怪输入 —— 交给 CI 报错）
5. 纯注释步（只有 `c`）→ `[]`（跳过）

**为什么 rep 必须循环前展开**：`process_single_map_handle` 依赖
`prev_key` / `next_key`（同方向续走、疾跑保持）和 `fighting_count`
（加载后按条数统计）。展开后的序列与等价 v1 **逐条一致**，这些语义零漂移；
在循环里原地循环 N 次会把 `prev/next` 关系和统计全部搞乱。

**为什么迁移合并相邻同内容步是严格等价**：顺序执行下
`[X, X, X]` 与 `[{X, rep: 3}]` 展开（不变量 1）得到逐字节相同的序列。
`fighting` 步不合并（`_NO_COLLAPSE_KEYS`），多键条目不合并，值是列表/字典不合并。

## 3. 运行时

`utils/flows/map_operations.py` 的 5 个地图加载点（`process_single_map_start`
×3、`process_single_map_handle` ×2）统一包 `normalize_map_data(...)`；
`handle` 在首次加载后立即统计 `fighting_count`（用展开后的条数）。

写盘**唯一**出口是 `json_io.dumps_map`（CLAUDE.md R22），但落盘**格式跟随文件原貌**：
录制器（record.py）只产出 v1；webui 编辑是「就地保真」—— 载入 v2 编辑保存后仍是
v2（每个条目的键原序回写），保存前会过 `schema.validate_map` 拒掉 error 级写法。
地图文件在仓库里可以停留为 v2（人写人读），运行时内存里永远是 v1。

## 4. 工具与 CI 门

| 门 | 文件 | 对 v2 |
| --- | --- | --- |
| 格式 | `tools/format_maps.py` | v2 也是规范形式输入（dumps_map 能序列化 v2） |
| 校验 | `tools/validate_maps.py` | `utils/core/schema.py` 按版本分支校验（§2.1） |
| 图片 | `tools/validate_pictures.py` | `img` stem 折算回 `picture\<stem>.png` 一起解析 |
| 迁移 | `tools/migrate_maps_v2.py` | v1 → v2 批量迁移（见下） |

迁移：

```bash
python tools/migrate_maps_v2.py map/default          # 干跑：看会改什么
python tools/migrate_maps_v2.py map/default --write  # 落盘
```

安全网：每个文件迁移后做「归一化往返校验」—— migrated 展开回规范形必须与
original 逐条相等，过不了校验拒绝写盘；已迁移（`v: 2`）自动跳过。

## 5. 版本演进

* v1（2023-06 起）：单键字典，上游 StarRailAssistant 血统
* v2（2026-11）：命名字段（`img`/`delay`/`rep`/`c`），对标 MAA 任务协议的轻量版
* 未来加字段：优先复用 v2 的「命名键 + 顶层 `v`」通道，避免再发明「键名即语义」
