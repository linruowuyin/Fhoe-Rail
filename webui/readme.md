# Fhoe-Rail WebUI —— 星穹锄地指挥舱

星空风格的本地控制面板,覆盖软件的**全部配置项**与**运行控制**功能。

## 运行方式

**推荐**:双击项目根目录的 `Start-WebUI.bat`(自动以管理员权限启动,避免锄地时弹 UAC)。

**或手动**:在项目根目录执行:

```
python webui/server.py
```

启动后自动打开浏览器访问 <http://127.0.0.1:8666>。停止服务:`Ctrl+C` 或关闭 bat 窗口。

> 依赖:仅 Python 3 标准库。安全:只监听本机 127.0.0.1,不联网、不上传数据。

## 功能

| 页面 | 功能 |
|---|---|
| 🛰️ 指挥台 | 地图统计、日志解析运行统计(战斗/用时/疾跑节约/卡顿/零食)、配置速览、最近锄地地图 |
| 🚀 运行控制 | 从浏览器启动/停止锄地进程(默认锄地 / 白名单模式),实时输出流,启动前自动保存配置 |
| 🗺️ 地图图鉴 | 4 版本 × 628 路线,按星球分组,**支持名称/编号搜索**,步骤详情可展开全部 |
| ⚙️ 参数设置 | **全部 config.json 键**可视化编辑（含🔔通知推送：19 种渠道、三个触发时机、测试按钮）:基础 / 战斗 / 地图行为 / 购买 / 时间 / 高级(含 GitHub 代理、一次性白名单、视角校准按钮、只读信息),支持保存/复制/下载/原始 JSON |
| 📜 航行日志 | 实时读取日志(3 秒轮询,切页自动暂停),按级别过滤,清屏 |
| ⭐ 关于 | 项目信息 |

## API

| 端点 | 说明 |
|---|---|
| `GET /api/config` / `POST /api/config` | 读取 / 保存 config.json |
| `GET /api/maps` | 地图树(版本 → 星球 → 地图) |
| `GET /api/map?file=..&version=..` | 单张地图 JSON(路径安全校验) |
| `GET /api/logs?lines=N` | 日志尾部 N 行(大文件 seek 读取) |
| `GET /api/stats` | 汇总:配置 + 地图统计 + 日志解析 |
| `GET /api/run` | 锄地进程状态 + 最近输出(单例) |
| `POST /api/run` | 启动锄地 `{mode: "normal" \| "white"}` |
| `POST /api/run/stop` | 停止锄地进程 |
| `POST /api/notify/test` | 发送测试通知（需先在配置页保存） |

## 修改指南

- **页面文案 / 颜色 / 布局**:`webui/index.html`(`:root` 变量改主题色;`CONFIG_DEFS` 数组改配置项)
- **新增配置项**:`index.html` 的 `CONFIG_DEFS` 加一项(`bool` / `number` / `text` / `text-arr` / `select` / `select-main`)
- **运行模式**:`webui/server.py` 的 `RUN_MODES` 字典
- **端口**:`webui/server.py` 顶部 `PORT`
- **星球名称**:`webui/server.py` 的 `PLANET_NAMES`

## 已知说明

- 交互式模式(`--debug` / `--dev` / `--record`)依赖终端交互,WebUI 不提供(运行控制页有说明)
- 日志统计为尽力解析,无日志或格式变化时显示 "—"
- 通过 `Start-WebUI.bat` 启动时以管理员权限运行,锄地子进程不会弹 UAC
