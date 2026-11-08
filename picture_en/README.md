# 多语言识图模板 · 预留目录

这里是**非简体中文客户端**的识图模板预留位（`picture_en/` 对应英文客户端；
其他语言按 `picture_<语言代码>/` 同样规则建目录，如 `picture_ja/`、`picture_kr/`）。

## ⚠️ 当前状态

**本目录中的模板暂未被程序加载。** 程序目前只索引 `picture/`（简体中文客户端
模板），按客户端语言切换模板目录的支持尚未实现。这里先收攒贡献，配套加载
支持落地后启用。

## 贡献规则（提交前逐条核对）

1. **文件名必须与 `picture/` 下的同名模板完全一致**（含扩展名前的部分）。
   `picture/xxx.png` ↔ `picture_en/xxx.png`。地图 JSON 里的 `picture\xxx.png`
   是资源 ID，运行时按文件名（stem）查找，语言目录靠目录本身区分，因此
   **文件名一个字符都不能变**。
2. **分辨率与截图区域必须与 `picture/` 对应模板一致**（现有模板按 1080p 截取）。
   差一个像素的裁剪区域都会导致匹配失败。
3. 格式：`.png` 或 `.webp` 均可（目录内统一用一种）。
4. **必须附实测记录**：用对应语言客户端实际跑通至少一张含图片步骤的地图
   （如 `map/default/map_1-1_1.json`），并在 PR 描述中说明验证结果。

## 提交方式

- 直接提 PR 到本仓库，或在
  [Fhoe-Rail-Maps 讨论区](https://github.com/linruowuyin/Fhoe-Rail-Maps) 先行沟通。

---

# Multilingual recognition templates · reserved directory

Reserved for templates captured from **non-Simplified-Chinese clients**
(`picture_en/` for English; other languages follow the same rule as
`picture_<lang>/`).

## ⚠️ Current status

**Templates in this directory are NOT loaded by the program yet.** Only
`picture/` (Simplified Chinese) is indexed; per-client-language template
switching is not implemented. Contributions are collected here first and will
be enabled once the loader lands.

## Rules

1. Filenames must exactly match the corresponding file in `picture/`
   (`picture/xxx.png` ↔ `picture_en/xxx.png`) — map JSON references are
   resource IDs resolved by stem, so the stem cannot change.
2. Resolution and capture region must match the `picture/` counterpart
   (existing templates are captured at 1080p).
3. Format: `.png` or `.webp` (be consistent within a directory).
4. Attach a real run log: run at least one map containing picture steps with
   the target-language client and include the result in your PR.
