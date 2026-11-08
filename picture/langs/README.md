# 多语言识图模板 · 预留目录

非简体中文客户端的识图模板统一收在本目录下，按语言分目录管理：

```
picture/langs/tw/   繁體中文客户端
picture/langs/en/   英文客户端
picture/langs/ja/   日文客户端
picture/langs/kr/   韩文客户端
```

## ✅ 待替换清单已预置（占位文件）

每个语言目录下已按 `picture/` 的结构**预置同名占位文件**（内容为说明文本，
不是图片）。占位文件本身就是完整的待替换清单：

- `picture/ui/confirm.webp` ↔ `picture/langs/en/ui/confirm.webp` —— 打开语言
  目录即可看到**全部需要替换的文件**，贡献时用真图**同名覆盖占位文件**即可。
- **需要替换的模板 = 115 张 / 372**：含中文文字的模板（地点名称、按钮文字、
  界面提示等，其他语言客户端匹配会失败）。
- **无需替换的 257 张**：纯图形模板（标记点图标、方向罗盘、数字楼层号等），
  跨语言通用——它们不在占位清单里。
- 判定方法：OCR 扫描 + 逐张人工复核。边缘个案（极小文字、艺术字）可能存在
  误差，以对应语言客户端实际匹配效果为准：若某个不在清单里的模板匹配失败，
  欢迎一并提交。

## ⚠️ 当前状态

**本目录中的模板暂未被程序加载。** 运行时索引只覆盖 `picture/` 下的中文模板
（`langs/` 是扫描豁免目录，见 `utils/vision/assets.py` 的 `SCAN_SKIP_DIRS`），
按客户端语言切换模板目录的支持尚未实现。这里先收攒贡献，配套加载支持落地后
启用。

## 贡献规则（提交前逐条核对）

1. **文件名必须与 `picture/` 下的同名模板完全一致**。
   `picture/ui/xxx.png` ↔ `picture/langs/en/ui/xxx.png`（子目录分类也保持
   一致）。地图 JSON 里的 `picture\xxx.png` 是资源 ID，运行时按文件名（stem）
   查找，语言靠目录本身区分，因此**文件名一个字符都不能变**。
2. **分辨率与截图区域必须与 `picture/` 对应模板一致**（现有模板按 1080p 截取）。
   差一个像素的裁剪区域都会导致匹配失败。
3. 格式：`.png` 或 `.webp` 均可（同一语言目录内统一用一种）。
4. **必须附实测记录**：用对应语言客户端实际跑通至少一张含图片步骤的地图
   （如 `map/default/map_1-1_1.json`），并在 PR 描述中说明验证结果。

## 提交方式

- 直接提 PR 到本仓库，或在
  [Fhoe-Rail-Maps 讨论区](https://github.com/linruowuyin/Fhoe-Rail-Maps) 先行沟通。

---

# Multilingual recognition templates · reserved directory

Templates captured from **non-Simplified-Chinese clients** are managed under
this directory, one sub-directory per language (`picture/langs/tw/`,
`picture/langs/en/`, `picture/langs/ja/`, `picture/langs/kr/`).

## ✅ Placeholder list is pre-built

Each language directory already contains **same-path placeholder files**
mirroring `picture/` (placeholders are text files, not images). The
placeholders ARE the to-replace list:

- `picture/ui/confirm.webp` ↔ `picture/langs/en/ui/confirm.webp` — open a
  language directory to see **every file that needs replacing**; contribute by
  overwriting the placeholder with the real capture (same name).
- **Needs replacement = 115 / 372**: templates containing Chinese text
  (location names, button labels, UI prompts) which will fail template
  matching on other-language clients.
- **Language-neutral 257**: pure graphics (map markers, compass arrows, numeric
  floor labels) — not in the placeholder list.
- Classification was done via OCR plus manual review of every candidate; tiny
  or stylized text may have slipped through. If a template not in the list
  fails to match on your client, please submit it too.

## ⚠️ Current status

**Templates in this directory are NOT loaded by the program yet.** Only the
Chinese templates under `picture/` are indexed (`langs/` is a scan-skip
directory, see `SCAN_SKIP_DIRS` in `utils/vision/assets.py`); per-client-language
template switching is not implemented. Contributions are collected here first.

## Rules

1. Filenames must exactly match the corresponding file in `picture/`,
   including sub-directory categories (`picture/ui/xxx.png` ↔
   `picture/langs/en/ui/xxx.png`) — map JSON references are resource IDs
   resolved by stem, so the stem cannot change.
2. Resolution and capture region must match the `picture/` counterpart
   (existing templates are captured at 1080p).
3. Format: `.png` or `.webp` (be consistent within one language directory).
4. Attach a real run log: run at least one map containing picture steps with
   the target-language client and include the result in your PR.
