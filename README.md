<div align="center">

# Fhoe-Rail · 崩坏：星穹铁道 锄大地自动化

[![GitHub release](https://img.shields.io/github/v/release/linruowuyin/Fhoe-Rail?label=Release&color=blue)](https://github.com/linruowuyin/Fhoe-Rail/releases)
[![GitHub stars](https://img.shields.io/github/stars/linruowuyin/Fhoe-Rail?label=Stars&color=yellow)](https://github.com/linruowuyin/Fhoe-Rail/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/linruowuyin/Fhoe-Rail?label=Forks&color=green)](https://github.com/linruowuyin/Fhoe-Rail/network)
[![License](https://img.shields.io/github/license/linruowuyin/Fhoe-Rail?label=License&color=orange)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)

**图片识别驱动的《崩坏：星穹铁道》每日锄大地脚本** — StarRailAssistant 轻量化分支，免费开源，仅供学习交流。

**本项目为 [March7thAssistant](https://github.com/moesnow/March7thAssistant)（三月七小助手）的子集，可独立部署运行（也可在三月七聚合使用）**，共用 onepush 通知推送方案与 StarRail.exe 路径配置约定；本体是 [StarRailAssistant](https://github.com/Starry-Wind/StarRailAssistant) 的轻量化分支。

</div>

---

<div align="center">

**简体中文** | [繁體中文](./docs/README_TW.md) | [English](./docs/README_EN.md) | [日本語](./docs/README_JA.md) | [한국어](./docs/README_KR.md)

</div>

---

## 目录

<table align="center">
<tr>
<td>

- [这是什么](#这是什么)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
  - [环境要求](#环境要求)
  - [运行须知](#运行须知)
  - [启动方式](#启动方式)
  - [命令行参数](#命令行参数)
  - [已知限制](#已知限制)

</td>
<td>

- [WebUI 控制面板](#webui-控制面板)
- [通知推送](#通知推送)
- [配置](#配置)
- [地图](#地图)
  - [地图版本](#地图版本)
  - [选择地图](#选择地图)
  - [录制新地图](#录制新地图)
  - [地图 JSON 格式](#地图-json-格式)

</td>
<td>

  - [主界面检测](#主界面检测)
- [键位映射](#键位映射)
- [开发](#开发)
  - [目录结构](#目录结构)
  - [架构与分层](#架构与分层)
  - [测试与 CI](#测试与-ci)
  - [贡献指南](#贡献指南)

</td>
<td>

- [全自动锄地（进阶）](#全自动锄地进阶)
- [相关项目](#相关项目)
- [贡献者](#贡献者)
- [许可与免责声明](#许可与免责声明)

</td>
</tr>
</table>

---

## 这是什么

Fhoe-Rail 是一个运行在 **Windows** 上的《崩坏：星穹铁道》**锄大地（每日清委托/打材料）自动化脚本**。

它不读取、不修改任何游戏文件或游戏代码，而是像真人一样操作：**截取游戏画面 → 模板匹配（OpenCV）识别传送点/交互点 → 模拟键鼠**执行预录制的路线。所有跑图路线由社区人工录制并开源共享。

> **🌐 语言说明**：识图模板（`picture/` 目录）均截取自**简体中文客户端**。游戏语言不同时，按钮/对话框上的文字也不同，模板匹配会失败——**目前仅保证简体中文客户端可用**。
> 如需支持其他语言：使用对应语言客户端重新截取**全部同名模板**，放入 `picture/langs/` 下的语言目录（英文对应 `picture/langs/en/`，其他语言按 `picture/langs/<语言代码>/` 命名；文件名与子目录分类须与 `picture/` 现有模板一致）。注意：语言目录中的模板**暂未被程序加载**（扫描豁免，随多语言加载支持一同启用）——规则详见 [picture/langs/README.md](picture/langs/README.md)；欢迎提交 PR，或在 [Fhoe-Rail-Maps](https://github.com/linruowuyin/Fhoe-Rail-Maps) 讨论区反馈。

**这不是什么：**

- ❌ 不是外挂/修改器，不注入进程、不修改内存或游戏文件
- ❌ 不是跨平台工具，仅支持 Windows（依赖 pywin32 / PyAutoGUI / PyGetWindow）
- ❌ 不是商业化产品，免费、开源、仅供学习交流
- ⚠️ 使用第三方脚本存在**封号风险**，请阅读文末[免责声明](#许可与免责声明)

---

## 功能特性

| 功能 | 说明 |
| --- | --- |
| 每日锄地 | 图片识别传送点 + 预录线路，免配置即可启动 |
| 疾跑 | 锄地过程全程疾跑，减少运行时间、提升效率 |
| 云星铁 | 支持云星铁，需运行在 1920×1080 显示器并设为全屏 |
| 白名单/黑名单 | 仅允许 / 禁止指定地图运行 |
| 代币获取 | 自动购买/获得 过期邮包 · 艾迪恩代币 · 翁法罗斯记忆代币 |
| 黄泉专用地图 | 加速锄地，消耗奇巧零食（可自动合成） |
| 4 点续锄 | 运行一次后等待至凌晨 4 点继续，跨日连续锄地 |
| 秘技 | 可配置使用秘技 |
| 收尾动作 | 锄地结束后自动关机 / 注销 / 关闭指定进程 |
| 定时运行 | 可配置定时后自动运行 |
| WebUI | 内置零依赖本地控制面板，可视化管理与监控 |

---

## 快速开始

### 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows（脚本依赖 Win32 API） |
| 游戏分辨率 | **1920×1080**；云星铁必须在该分辨率显示器下**全屏** |
| 游戏帧数 | **60 帧** |
| Python | 3.11+（从源码运行时；发布包为独立 exe，无需安装 Python） |
| 网络 | 可选：通知推送、自动更新检查 |

### 运行须知

- 本程序属于**录制按键 + 图像识别**性质，跑图路线均为人工公益录制
- **1 号位**为跑图角色，必须是**远程角色**；使用黄泉专用地图时必须为**黄泉**，使用银狼 LV.999 专用地图时必须为**银狼 LV.999**
- 远程角色建议选择**成年模型**且攻击无位移，少女模型可能卡图（见[跑图模型分类](#地图版本)）
- 请事先开启**全部传送锚点**，并完成地图上可能干扰图片识别传送锚点的任务，否则可能卡图（本项目不予处理）
- 其他地方卡住的，请留意是否有未开启的机关或地图上的任务标识等影响识别
- **黑名单设置**：以 `--debug` 启动后在设置中新增禁止运行的地图。禁闭舱段未开启的，新增「禁闭舱段」；绥园未开启的，新增「绥园」，以此类推
- **请不要修改默认键位**，由此造成的卡图请自行解决
- 识图为截取游戏画面，因此屏幕上**不能有任何覆盖物**（小心各类弹窗）
- 运行过程中请勿在非自动战斗状态时移动鼠标或操作键盘

### 启动方式

| 方式 | 操作 |
| --- | --- |
| 菜单（推荐） | 双击 `1点这里.bat` 或 `Fhoe-Rail.bat`，按菜单提示运行 |
| 免配置 | 直接运行 `Fhoe-Rail.exe` |
| WebUI | 双击 `Start-WebUI.bat`，浏览器自动打开 <http://127.0.0.1:8666> |
| 从源码 | `pip install -r requirements.txt` 后运行 `python fhoe.py` |

### 命令行参数

`fhoe.py` / `Fhoe-Rail.exe` 支持以下参数：

| 参数 | 说明 |
| --- | --- |
| `--debug` | 三级选图菜单（含设置） |
| `--dev` | 同 `--debug`，且每轮跑完自动重新选图 |
| `--white` | 白名单模式 |
| `--record` | 录制新地图 |
| `--test` | 测试模式 |
| `--config` | 配置模式 |
| `--map <ID>` | 只跑单张地图，如 `--map 3-5_1` |
| `--range <start> <end>` | 按地图列表顺序从起点跑到终点（**含两端**），如 `--range 3-5_1 3-5_2` |
| `--map-version <名>` | 临时指定地图版本，如 `--map-version HuangQuan`（可配合上面两者） |
| `--webui-server` | 启动内置 WebUI 服务器（端口 8666） |

> **单图 / 区间运行的约束**：区间起终点必须在**同一地图版本**里，且终点不能排在起点之前。

### 已知限制

- 识图依赖截屏，任何覆盖物（弹窗、其他窗口、鼠标提示）都可能影响识别
- 部分屏幕无法识别全屏，请切换非全屏重试
- 使用有封号风险，请知悉并自行评估

---

## WebUI 控制面板

内置本地 WebUI，**零第三方依赖**（仅 Python 标准库），用于查看运行状态、管理地图与配置。

- **启动**：双击 `Start-WebUI.bat`（自动请求管理员权限），浏览器自动打开 <http://127.0.0.1:8666>
- **重复启动**：端口被自家 WebUI 占用时，新实例会让旧实例优雅退出后接管（无需手动关闭）；被其他程序占用则仅报错，不会杀进程
- **指挥台**：运行状态与统计（战斗次数 / 总用时 / 疾跑节约 / 卡顿），自动汇总本次运行锄图数与耗时
- **运行控制**：从浏览器启动/停止锄地，支持 默认 / 白名单 / 单图 / 区间 / 开发者单图 / 录制 / 安装依赖 七种模式，实时输出
- **地图图鉴**：按版本 / 星球浏览全部路线，支持名称 / 编号 / 作者搜索
- **地图编辑器**：在线新建 / 编辑地图——动作键与图片 stem 自动补全，保存前自动校验格式，不合法直接拒绝落盘
- **参数设置**：`config.json` 全部配置项可视化编辑，支持保存 / 复制 / 下载
- **航行日志**：实时查看运行日志
- **新图注意**：浏览新图注意事项图片

---

## 通知推送

支持 **19 种通知渠道**，在 WebUI「参数设置 → 通知推送」中配置：

> Windows 桌面通知（零配置，默认） · Server酱 · Server酱³ · PushPlus · Telegram · Bark · 钉钉 · 企业微信机器人/应用 · 飞书 · Discord · Gotify · Ntfy · PushDeer · Qmsg · SMTP 邮件 · QQ 机器人 · 自定义请求 · 通用 Webhook

- **通知时机**：开始锄地 / 锄地完成（含统计摘要）/ 运行出错，可分别开关
- **测试**：WebUI 中可直接发送测试通知验证配置

---

## 配置

配置文件为仓库 / 运行目录下的 `config.json`。对应项 `true` 为开启，`false` 为关闭。

| 配置项 | 默认 | 说明 |
| --- | --- | --- |
| `auto_final_fight_e` | false | 是否允许每个地图最后一击改为秘技攻击 |
| `auto_final_fight_e_cnt` | — | 每个地图最后一击为秘技攻击的上限次数 |
| `allow_fight_e_buy_prop` | false | 是否允许自动吃秘技零食（黄泉地图会自动设为允许） |
| `auto_run_in_map` | false | 是否允许在地图中疾跑 |
| `detect_fight_status_time` | 5 | 识别是否进入战斗的时间（秒） |
| `map_version` | — | 使用的地图文件夹 |
| `main_map` | — | 优先星球：1-空间站 / 2-雅利洛VI / 3-仙舟 / 4-匹诺康尼 |
| `allow_run_again` | false | 是否每次运行连续锄地 2 次避免漏怪 |
| `allow_run_next_day` | false | 是否等待至下一个凌晨 4 点继续从头锄地 |
| `allow_map_buy` | false | 是否允许购买 代币 与 过期邮包 |
| `allow_snack_buy` | false | 是否允许购买并合成秘技零食的制作材料 |
| `allow_memory_token` | false | 是否允许获得翁法罗斯记忆代币 |
| `allowlist_mode_once` | false | 是否仅此次运行白名单地图 |
| `auto_shutdown` | 0 | 锄地结束系统操作：0-无 / 1-关机 / 2-注销 / 3-关闭指定进程 |
| `taskkill_name` | — | `auto_shutdown=3` 时关闭的进程名 |
| `webhook_url` | — | 通用 Webhook 通知地址 |
| `notify_enabled` | false | 是否启用通知推送 |
| `notify_channel` | — | 通知渠道（windows桌面通知/serverchan/pushplus/telegram/dingtalk 等） |
| `notify_key` | — | 通知渠道密钥 |
| `notify_chat_id` | — | 通知目标参数（如 Telegram 的 chat_id） |
| `notify_params` | — | 通知渠道高级参数（JSON） |
| `notify_on_start` | false | 开始锄地时通知 |
| `notify_on_end` | false | 锄地完成时通知（含统计） |
| `notify_on_error` | false | 运行出错时通知 |

---

## 地图

### 地图版本

地图以 JSON 文件按版本目录组织（`map/<版本>/`）。当前内置版本：

| 版本目录 | 说明 |
| --- | --- |
| `default` | 默认地图，适配大部分远程角色 |
| `default_lite` | 精简版地图 |
| `technique` | 已无人维护（<del>加入较多紫色秘技且战斗中多用秘技</del>） |
| `HuangQuan` | 黄泉专用地图，需自行备足秘技零食 |
| `SilverWolfLv999` | 银狼 LV.999 专用地图（由黄泉地图转换，不使用 E 秘技） |
| `reward` | 特殊物品领取路线 |

> **跑图模型分类**：小部分角色可能因体型原因莫名卡住。远程角色优先选择**成年模型**且攻击无位移者；少女模型可能卡图。

### 选择地图

以 `--debug` 模式运行（或直接运行 `自选地图.bat`），选择【设置】，即可选择对应地图。

### 录制新地图

> 感谢 [@AlisaCat](https://github.com/AlisaCat-S) 的贡献。

**操作限制：**

- 禁止使用鼠标移动视角
- 录制过程中**每次只能按下一个有效按键**，不能同时按多个
- 录制支持的按键：`W`/`S`/`A`/`D`（移动）、`F`（交互）、`R`（匹诺康尼搭建梦泡桥梁）、`E`（秘技，多用于黄泉地图砍怪）、`X`（进入战斗）、鼠标右键（打障碍物 / 疾跑后顶墙取消冲刺）、`v`（等待 N 秒）
- 需要其他按键需手动修改配置文件

**录制规则：**

- 脚本仅记录按键按下的时间和视角移动，**不记录停顿时间**
- 推荐逐个按键慢速录制，以确保准确性

**录制完成：** 按 `F9` 停止并保存，生成 `output(时间).json`。

**输出与配置：**

1. 将 `output(时间).json` 重命名为目标地图的 JSON 文件名
2. 将传送点截图重命名后保存到 `picture` 文件夹
3. 新地图可提交到 [Fhoe-Rail-Maps](https://github.com/linruowuyin/Fhoe-Rail-Maps) 仓库（CI 自动校验通过后合并），或交由管理员提交

**截图图片要求：**

- 截图文字识别，尽量避免有重复字样（如「支援舱段」「禁闭舱段」应只截支援和禁闭，否则一定识别不到就会乱点）
- 尽量不截文字，便于以后适配多种语言版本
- 截图范围尽量小（图片会越加越多，适当缩小截图范围）

### 地图 JSON 格式

地图同时支持 **v1（旧格式）** 与 **v2（推荐）** 两种编写格式：顶层写 `"v": 2` 即为 v2，不写则按 v1 解析（完全兼容）。两种格式运行时等价，校验器对两者都生效。

**v2（推荐）**——图片引用改为命名字段、支持步骤注释与连击折叠：

```json
{
    "v": 2,
    "name": "乌拉乌拉-1",
    "author": "Starry-Wind",
    "start": [
        {"map": 1},                                   // 动作键与 v1 完全一致
        {"img": "orientation_1", "delay": 1.5},       // 等价 v1 的 {"picture\\orientation_1.jpg": 1.5}
        {"img": "transfer", "delay": 1.5, "wait": 3}  // wait：点击后等画面静止满 3 秒再继续（加载慢的机器更稳）
    ],
    "map": [
        {"a": 0.2, "rep": 3}                          // 等价 v1 的 {"a": 0.2} 写 3 遍
    ]
}
```

字段说明：`img` 图片资源名（不带路径与后缀，仅限 `start`）· `delay` 点击后停顿秒数（默认 0.8）· `rep` 重复次数 · `c` 行内注释（运行时忽略）· `wait` 点击后等待画面静止（秒，0-30，可选）。

**v1（旧格式，完全兼容）**：

```json
{
    "name": "乌拉乌拉-1",                     // 地图 JSON 文件名为 1-1_1.json
    "author": "Starry-Wind",                 // 作者名称（第二作者不得覆盖第一作者）
    "start": [                                 // 开局传送地图操作步骤
        {"map": 1},                            // 按下 m 键打开地图
        {"picture\\orientation_1.jpg": 1.5}, // 识别 orientation_1.jpg 后移动鼠标到图片中间并按键
        {"picture\\map_1.jpg": 2},           // 识别区域名对应图片，例如 "乌拉乌拉"
        {"picture\\map_1_point_1.jpg": 1.5}, // 第一个传送点的图片
        {"picture\\transfer.jpg": 1.5},      // "传送"文字的图片
        {"space": 1},                          // 按下 space 键
        {"b": 1},                              // 按下 b 键
        {"await": 5}                           // 等待 5 秒
    ]
}
```


> 完整字段与校验规则见 [docs/MAP_FORMAT.md](./docs/MAP_FORMAT.md)。WebUI 编辑器保存前会自动校验两种格式。
### 主界面检测

每张地图在开始执行 `map` 里的步骤前，脚本都会固定执行一次 `back_to_main`
（效果等同于在 `start` 末尾写 `{"main": 1}`，但不需要地图自己写）：

1. 先识别主界面（左上角灯泡图标）
2. 不在主界面时按 `ESC` 返回；遇到「是否放弃游玩？」确认框会先点掉；最多等待 120 秒，超时终止本轮并提示检查游戏界面

所以 `map` 的第一步只有两个前提：**当前一定在主界面**，且**这个状态能从主界面按 `ESC` 到达**。编辑或录制地图时请注意：

- 不要把「传送落地后残留的对话 / 菜单 / 战斗」当作第一步的前提。需要处理这类残留时，把它放在 `start` 的末尾（主界面检测之前），或确认按 `ESC` 能回到主界面后再写进 `map`
- `map` 开头不需要再重复写 `{"main": 1}`；也不要在开头写 `{"esc": 1}` —— 此时已在主界面，多余的 `ESC` 会打开 ESC 菜单，后续步骤会从菜单里开始

---

## 键位映射

| 键位 | 映射 |
| --- | --- |
| `other` | 未列出的任意键都视为移动键，后面的数字代表按下的时间长短 |
| `x` | 进入战斗，map 映射为 `fighting=1` |
| 鼠标左键 | 打障碍物，map 映射为 `fighting=2` |
| `f` | 交互键，后面的数字代表按下 F 键后等待的时间，默认 15 秒 |
| `r` / `space` | 交互键，后面的数字代表反复按键的次数，间隔随机 |
| `shutdown` | 关机标志，键值无意义，控制开关在配置文件中 |
| `mouse_move` | 视角转动，因数值计算复杂（不同设备数值不同），已被弃用 |
| `scroll` | 鼠标滚轮滚动数值，同样较复杂，未被启用 |
| `e` | 键值为 1 时，使用秘技并追加普通攻击 |
| `e` | 键值为 2 时，仅使用秘技；适用于强化型秘技角色 |
| `esc` | 只有键值为 1 时有意义，等同于按一次 Esc 键 |
| `v` | 等待 N 秒，map 映射为 `await=N` 秒 |

---

## 开发

### 目录结构

| 目录 / 文件 | 说明 |
| --- | --- |
| `fhoe.py` | 主入口（命令行解析 + 各模式调度） |
| `get_width.py` | 屏幕宽度检测工具 |
| `map/` | 地图路线 JSON（按版本分子目录，共 875 张） |
| `picture/` | 模板匹配截图 |
| `utils/` | 核心逻辑分层（core / drivers / vision / flows / ui） |
| `tests/` | pytest 测试（全替身，无需游戏窗口） |
| `tools/` | 开发辅助：地图/图片校验与格式化脚本 |
| `webui/` | 内置 WebUI 服务器与前端 |
| `新图注意事项/` | 新图注意事项说明图片 |
| `docs/` | 说明文档（MAP_FORMAT.md 地图格式规范 + 各语言 README） |
| `CLAUDE.md` | 工程规则与 AI 协作指引（开发顺序/分层/硬规则/测试） |
| `requirements.txt` | Python 依赖 |
| `LICENSE` | GPL-3.0 |

### 架构与分层

项目按 **core → drivers → vision → flows → ui** 分层，依赖方向单向（`tests/test_architecture.py` 强制校验）。

关键约束（详见 `CLAUDE.md` §3）：

- 时间、输入、画面、状态、结构、资源更新均有硬规则
- 地图 JSON 支持 v1/v2 双编写格式，运行时统一归一为 v1（docs/MAP_FORMAT.md）
- 预置与死代码有专门清理约定
- 地图执行契约、ESC 前的界面修复有明确约定

### 测试与 CI

**测试**：`pytest`（全替身，无游戏窗口；`xfail` 标记的是已记录的真实缺陷），配合三个静态校验工具：

| 工具 | 作用 |
| --- | --- |
| `tools/validate_maps.py` | 地图 JSON 结构校验，出错退出码 1 |
| `tools/validate_pictures.py` | 图片文件名全局唯一 + `picture` 引用可解析 |
| `tools/migrate_maps_v2.py` | v1 → v2 地图格式迁移（默认干跑，`--write` 落盘） |
| `tools/format_maps.py --base <ref>` | R22 写盘格式校验，只拦截本次改动的地图 |

**CI**（`.github/workflows/run.yml`，`windows-latest` + Python 3.11.5）：

- **test** 作业：pytest + 地图校验 + 图片校验 + 格式校验
- **build** 作业：PyInstaller 打包 `Fhoe-Rail.exe` 与 `Start-WebUI.exe`，生成各 `.bat`，拷贝资源进 `dist`，打 tag 时经 `softprops/action-gh-release` 发布 `Fhoe-Rail.zip` 并写 `version.txt`

触发：push 到任意分支/标签（`paths` 限 `**.py` + `map/**.json`；标签 push 不受 `paths` 过滤）。`fetch-depth: 0`（浅克隆拿不到基线）。

### 贡献指南

欢迎提交优化/新版本的路线地图，以及代码改进：

- 新地图：录制后按[录制新地图](#录制新地图)规范产出 JSON + 截图，提交到 [Fhoe-Rail-Maps](https://github.com/linruowuyin/Fhoe-Rail-Maps) 仓库（CI 自动校验），或交由管理员
- 代码：遵循 `CLAUDE.md` 的开发顺序（可行性探针 → 契约与资源 → 纯逻辑严格 TDD → 检测器黄金图 → 编排替身假时钟 → 回放端到端），并确保本地 `pytest` + 三个校验工具通过
- 提交前请跑一遍完整 CI（本地可用 `tools/` 下脚本复现）

---

## 全自动锄地（进阶）

仅提供思路参考：

1. 进入电脑 BIOS 开启**来电自启**
2. 准备**智能插座**×1（如米家智能插座 3），定时开启电源（推荐峰谷电的谷电时间）
3. 将星铁的游戏快捷方式（不是启动器）放到 map 文件夹与开机自启动文件夹
4. 开启「跑完关机」

**缺点**：遇到更新或网络卡顿会卡死（脚本未设计点击方案），建议再设定一个定时关闭电源（时间可参考之前跑完全图后的日志计时）。

---

## 相关项目

| 项目 | 说明 | 状态 |
| --- | --- | --- |
| [StarRailAssistant](https://github.com/Starry-Wind/StarRailAssistant) | 原项目 | 停更 |
| [March7thAssistant](https://github.com/moesnow/March7thAssistant) | 聚合使用 · 三月七小助手 | 活跃 |
| [StarRailAutoProxy](https://github.com/DoctorReid/StarRailAutoProxy) | 锄大地项目 · 一条龙 | 活跃 |
| [StarRail-FastRun](https://github.com/Souloco/StarRail-FastRun) | 锄大地项目 · FastRun | 停更 |
| [StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot) | 模拟器项目 · 星铁速溶茶 | 活跃 |
| [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) | 模拟宇宙项目 | 活跃 |

---

## 贡献者

感谢以下贡献者对本项目做出的贡献

<a href="https://github.com/linruowuyin/Fhoe-Rail/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=linruowuyin/Fhoe-Rail" />

</a>

---

## 许可与免责声明

**许可**：本项目以 [GPL-3.0](LICENSE) 开源，免费，仅供学习交流使用。开发者团队拥有本项目最终解释权。使用本软件产生的所有问题与本项目及开发者团队无关。禁止使用本软件进行大规模商业化行为；若您遇到商家使用本软件代练并收费，可能是设备与时间等费用，产生的问题及后果与本软件无关。本软件为非商业化项目，故与其他软件/游戏/程序并不构成也不可能会构成不正当竞争以及著作权侵权，特此声明。

**免责声明（原文）**：

> 本软件是一个外部工具，旨在自动化崩坏：星穹铁道的游戏玩法。它被设计成仅通过现有用户界面与游戏交互，并遵守相关法律法规。该软件包旨在为用户提供简化、便捷的功能交互，并且不打算以任何方式破坏游戏平衡或提供任何不公平的优势。该软件包不会以任何方式修改任何游戏文件或游戏代码。

请注意，根据 miHoYo 的 [崩坏：星穹铁道的公平游戏宣言](https://sr.mihoyo.com/news/111246?nav=news&type=notice)：

> 「严禁使用外挂、加速器、脚本或其他破坏游戏公平性的第三方工具。」
>
> 「一经发现，米哈游（下亦称"我们"）将视违规严重程度及违规次数，采取扣除违规收益、冻结游戏账号、永久封禁游戏账号等措施。」

---

<div align="center">

**Fhoe-Rail** · 免费开源 · 仅供学习交流 · 请勿用于商业用途

</div>
