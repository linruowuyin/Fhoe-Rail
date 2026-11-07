<div align="center">
# Fhoe-Rail · 崩壞：星穹鐵道 鋤大地自動化


[![GitHub release](https://img.shields.io/github/v/release/linruowuyin/Fhoe-Rail?label=Release&color=blue)](https://github.com/linruowuyin/Fhoe-Rail/releases)
[![GitHub stars](https://img.shields.io/github/stars/linruowuyin/Fhoe-Rail?label=Stars&color=yellow)](https://github.com/linruowuyin/Fhoe-Rail/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/linruowuyin/Fhoe-Rail?label=Forks&color=green)](https://github.com/linruowuyin/Fhoe-Rail/network)
[![License](https://img.shields.io/github/license/linruowuyin/Fhoe-Rail?label=License&color=orange)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)

**圖片識別驅動的《崩壞：星穹鐵道》每日鋤大地指令碼** — StarRailAssistant 輕量化分支，免費開源，僅供學習交流。

**本專案為 [March7thAssistant](https://github.com/moesnow/March7thAssistant)（三月七小助手）的子集，可獨立部署執行（也可在三月七聚合使用）**，共用 onepush 通知推送方案與 StarRail.exe 路徑配置約定；本體是 [StarRailAssistant](https://github.com/Starry-Wind/StarRailAssistant) 的輕量化分支。

</div>

---

<div align="center">

[简体中文](../README.md) | **繁體中文** | [English](README_EN.md) | [日本語](README_JA.md) | [한국어](README_KR.md)

</div>

---

## 目錄

<table align="center">
<tr>
<td>

- [這是什麼](#這是什麼)
- [功能特性](#功能特性)
- [快速開始](#快速開始)
  - [環境要求](#環境要求)
  - [執行須知](#執行須知)
  - [啟動方式](#啟動方式)
  - [命令列引數](#命令列引數)
  - [已知限制](#已知限制)

</td>
<td>

- [WebUI 控制面板](#webui-控制面板)
- [通知推送](#通知推送)
- [配置](#配置)
- [地圖](#地圖)
  - [地圖版本](#地圖版本)
  - [選擇地圖](#選擇地圖)
  - [錄製新地圖](#錄製新地圖)
  - [地圖 JSON 格式](#地圖-json-格式)

</td>
<td>

  - [主介面檢測](#主介面檢測)
- [鍵位對映](#鍵位對映)
- [開發](#開發)
  - [目錄結構](#目錄結構)
  - [架構與分層](#架構與分層)
  - [測試與 CI](#測試與-ci)
  - [貢獻指南](#貢獻指南)

</td>
<td>

- [全自動鋤地（進階）](#全自動鋤地進階)
- [相關專案](#相關專案)
- [貢獻者](#貢獻者)
- [許可與免責宣告](#許可與免責宣告)

</td>
</tr>
</table>

---

## 這是什麼

Fhoe-Rail 是一個執行在 **Windows** 上的《崩壞：星穹鐵道》**鋤大地（每日清委託/打材料）自動化指令碼**。

它不讀取、不修改任何遊戲檔案或遊戲程式碼，而是像真人一樣操作：**擷取遊戲畫面 → 模板匹配（OpenCV）識別傳送點/互動點 → 模擬鍵鼠**執行預錄製的路線。所有跑圖路線由社群人工錄製並開源共享。

**這不是什麼：**

- ❌ 不是外掛/修改器，不注入程序、不修改記憶體或遊戲檔案
- ❌ 不是跨平臺工具，僅支援 Windows（依賴 pywin32 / PyAutoGUI / PyGetWindow）
- ❌ 不是商業化產品，免費、開源、僅供學習交流
- ⚠️ 使用第三方指令碼存在**封號風險**，請閱讀文末[免責宣告](#許可與免責宣告)

---

## 功能特性

| 功能 | 說明 |
| --- | --- |
| 每日鋤地 | 圖片識別傳送點 + 預錄線路，免配置即可啟動 |
| 疾跑 | 鋤地過程全程疾跑，減少執行時間、提升效率 |
| 雲星鐵 | 支援雲星鐵，需執行在 1920×1080 顯示器並設為全屏 |
| 白名單/黑名單 | 僅允許 / 禁止指定地圖執行 |
| 代幣獲取 | 自動購買/獲得 過期郵包 · 艾迪恩代幣 · 翁法羅斯記憶代幣 |
| 黃泉專用地圖 | 加速鋤地，消耗奇巧零食（可自動合成） |
| 4 點續鋤 | 執行一次後等待至凌晨 4 點繼續，跨日連續鋤地 |
| 秘技 | 可配置使用秘技 |
| 收尾動作 | 鋤地結束後自動關機 / 登出 / 關閉指定程序 |
| 定時執行 | 可配置定時後自動執行 |
| WebUI | 內建零依賴本地控制面板，視覺化管理與監控 |

---

## 快速開始

### 環境要求

| 專案 | 要求 |
| --- | --- |
| 作業系統 | Windows（指令碼依賴 Win32 API） |
| 遊戲解析度 | **1920×1080**；雲星鐵必須在該解析度顯示器下**全屏** |
| 遊戲幀數 | **60 幀** |
| Python | 3.11+（從原始碼執行時；釋出包為獨立 exe，無需安裝 Python） |
| 網路 | 可選：通知推送、自動更新檢查 |

### 執行須知

- 本程式屬於**錄製按鍵 + 影像識別**性質，跑圖路線均為人工公益錄製
- **1 號位**為跑圖角色，必須是**遠端角色**；使用黃泉專用地圖時必須為**黃泉**，使用銀狼 LV.999 專用地圖時必須為**銀狼 LV.999**
- 遠端角色建議選擇**成年模型**且攻擊無位移，少女模型可能卡圖（見[跑圖模型分類](#地圖版本)）
- 請事先開啟**全部傳送錨點**，並完成地圖上可能干擾圖片識別傳送錨點的任務，否則可能卡圖（本專案不予處理）
- 其他地方卡住的，請留意是否有未開啟的機關或地圖上的任務標識等影響識別
- **黑名單設定**：以 `--debug` 啟動後在設定中新增禁止執行的地圖。禁閉艙段未開啟的，新增「禁閉艙段」；綏園未開啟的，新增「綏園」，以此類推
- **請不要修改預設鍵位**，由此造成的卡圖請自行解決
- 識圖為擷取遊戲畫面，因此螢幕上**不能有任何覆蓋物**（小心各類彈窗）
- 執行過程中請勿在非自動戰鬥狀態時移動滑鼠或操作鍵盤

### 啟動方式

| 方式 | 操作 |
| --- | --- |
| 選單（推薦） | 雙擊 `1點這裡.bat` 或 `Fhoe-Rail.bat`，按選單提示執行 |
| 免配置 | 直接執行 `Fhoe-Rail.exe` |
| WebUI | 雙擊 `Start-WebUI.bat`，瀏覽器自動開啟 <http://127.0.0.1:8666> |
| 從原始碼 | `pip install -r requirements.txt` 後執行 `python fhoe.py` |

### 命令列引數

`fhoe.py` / `Fhoe-Rail.exe` 支援以下引數：

| 引數 | 說明 |
| --- | --- |
| `--debug` | 三級選圖選單（含設定） |
| `--dev` | 同 `--debug`，且每輪跑完自動重新選圖 |
| `--white` | 白名單模式 |
| `--record` | 錄製新地圖 |
| `--test` | 測試模式 |
| `--config` | 配置模式 |
| `--map <ID>` | 只跑單張地圖，如 `--map 3-5_1` |
| `--range <start> <end>` | 按地圖列表順序從起點跑到終點（**含兩端**），如 `--range 3-5_1 3-5_2` |
| `--map-version <名>` | 臨時指定地圖版本，如 `--map-version HuangQuan`（可配合上面兩者） |
| `--webui-server` | 啟動內建 WebUI 伺服器（埠 8666） |

> **單圖 / 區間執行的約束**：區間起終點必須在**同一地圖版本**裡，且終點不能排在起點之前。

### 已知限制

- 識圖依賴截圖，任何覆蓋物（彈窗、其他視窗、滑鼠提示）都可能影響識別
- 部分螢幕無法識別全屏，請切換非全屏重試
- 使用有封號風險，請知悉並自行評估

---

## WebUI 控制面板

內建本地 WebUI，**零第三方依賴**（僅 Python 標準庫），用於檢視執行狀態、管理地圖與配置。

- **啟動**：雙擊 `Start-WebUI.bat`（自動請求管理員許可權），瀏覽器自動開啟 <http://127.0.0.1:8666>
- **重複啟動**：埠被自家 WebUI 佔用時，新例項會讓舊例項優雅退出後接管（無需手動關閉）；被其他程式佔用則僅報錯，不會殺程序
- **指揮台**：執行狀態與統計（戰鬥次數 / 總用時 / 疾跑節約 / 卡頓）
- **執行控制**：從瀏覽器啟動/停止鋤地，支援 預設 / 白名單 / 單圖 / 區間 / 開發者單圖 / 錄製 / 安裝依賴 七種模式，即時輸出
- **地圖圖鑑**：按版本 / 星球瀏覽全部路線，支援名稱 / 編號 / 作者搜尋
- **引數設定**：`config.json` 全部配置項視覺化編輯，支援儲存 / 複製 / 下載
- **航行日誌**：即時檢視執行日誌
- **新圖注意**：瀏覽新圖注意事項圖片

---

## 通知推送

支援 **19 種通知渠道**，在 WebUI「引數設定 → 通知推送」中配置：

> Windows 桌面通知（零配置，預設） · Server醬 · Server醬³ · PushPlus · Telegram · Bark · 釘釘 · 企業微信機器人/應用 · 飛書 · Discord · Gotify · Ntfy · PushDeer · Qmsg · SMTP 郵件 · QQ 機器人 · 自定義請求 · 通用 Webhook

- **通知時機**：開始鋤地 / 鋤地完成（含統計摘要）/ 執行出錯，可分別開關
- **測試**：WebUI 中可直接傳送測試通知驗證配置

---

## 配置

配置檔案為倉庫 / 執行目錄下的 `config.json`。對應項 `true` 為開啟，`false` 為關閉。

| 配置項 | 預設 | 說明 |
| --- | --- | --- |
| `auto_final_fight_e` | false | 是否允許每個地圖最後一擊改為秘技攻擊 |
| `auto_final_fight_e_cnt` | — | 每個地圖最後一擊為秘技攻擊的上限次數 |
| `allow_fight_e_buy_prop` | false | 是否允許自動吃秘技零食（黃泉地圖會自動設為允許） |
| `auto_run_in_map` | false | 是否允許在地圖中疾跑 |
| `detect_fight_status_time` | 5 | 識別是否進入戰鬥的時間（秒） |
| `map_version` | — | 使用的地圖資料夾 |
| `main_map` | — | 優先星球：1-空間站 / 2-雅利洛VI / 3-仙舟 / 4-匹諾康尼 |
| `allow_run_again` | false | 是否每次執行連續鋤地 2 次避免漏怪 |
| `allow_run_next_day` | false | 是否等待至下一個凌晨 4 點繼續從頭鋤地 |
| `allow_map_buy` | false | 是否允許購買 代幣 與 過期郵包 |
| `allow_snack_buy` | false | 是否允許購買併合成秘技零食的製作材料 |
| `allow_memory_token` | false | 是否允許獲得翁法羅斯記憶代幣 |
| `allowlist_mode_once` | false | 是否僅此次執行白名單地圖 |
| `auto_shutdown` | 0 | 鋤地結束系統操作：0-無 / 1-關機 / 2-登出 / 3-關閉指定程序 |
| `taskkill_name` | — | `auto_shutdown=3` 時關閉的程序名 |
| `webhook_url` | — | 通用 Webhook 通知地址 |
| `notify_enabled` | false | 是否啟用通知推送 |
| `notify_channel` | — | 通知渠道（windows桌面通知/serverchan/pushplus/telegram/dingtalk 等） |
| `notify_key` | — | 通知渠道金鑰 |
| `notify_chat_id` | — | 通知目標引數（如 Telegram 的 chat_id） |
| `notify_params` | — | 通知渠道高階引數（JSON） |
| `notify_on_start` | false | 開始鋤地時通知 |
| `notify_on_end` | false | 鋤地完成時通知（含統計） |
| `notify_on_error` | false | 執行出錯時通知 |

---

## 地圖

### 地圖版本

地圖以 JSON 檔案按版本目錄組織（`map/<版本>/`）。當前內建版本：

| 版本目錄 | 說明 |
| --- | --- |
| `default` | 預設地圖，適配大部分遠端角色 |
| `default_lite` | 精簡版地圖 |
| `technique` | 已無人維護（<del>加入較多紫色秘技且戰鬥中多用秘技</del>） |
| `HuangQuan` | 黃泉專用地圖，需自行備足秘技零食 |
| `SilverWolfLv999` | 銀狼 LV.999 專用地圖（由黃泉地圖轉換，不使用 E 秘技） |

> **跑圖模型分類**：小部分角色可能因體型原因莫名卡住。遠端角色優先選擇**成年模型**且攻擊無位移者；少女模型可能卡圖。

### 選擇地圖

以 `--debug` 模式執行（或直接執行 `自選地圖.bat`），選擇【設定】，即可選擇對應地圖。

### 錄製新地圖

> 感謝 [@AlisaCat](https://github.com/AlisaCat-S) 的貢獻。

**操作限制：**

- 禁止使用滑鼠移動視角
- 錄製過程中**每次只能按下一個有效按鍵**，不能同時按多個
- 錄製支援的按鍵：`W`/`S`/`A`/`D`（移動）、`F`（互動）、`R`（匹諾康尼搭建夢泡橋梁）、`E`（秘技，多用於黃泉地圖砍怪）、`X`（進入戰鬥）、滑鼠右鍵（打障礙物 / 疾跑後頂牆取消衝刺）、`v`（等待 N 秒）
- 需要其他按鍵需手動修改配置檔案

**錄製規則：**

- 指令碼僅記錄按鍵按下的時間和視角移動，**不記錄停頓時間**
- 推薦逐個按鍵慢速錄製，以確保準確性

**錄製完成：** 按 `F9` 停止並儲存，生成 `output(時間).json`。

**輸出與配置：**

1. 將 `output(時間).json` 重新命名為目標地圖的 JSON 檔名
2. 將傳送點截圖重新命名後儲存到 `picture` 資料夾
3. 新地圖可提交到 `map` 分支，或交由管理員提交

**截圖圖片要求：**

- 截圖文字識別，儘量避免有重複字樣（如「支援艙段」「禁閉艙段」應只截支援和禁閉，否則一定識別不到就會亂點）
- 儘量不截文字，便於以後適配多種語言版本
- 截圖範圍儘量小（圖片會越加越多，適當縮小截圖範圍）

### 地圖 JSON 格式

```json
{
    "name": "烏拉烏拉-1",                     // 地圖 JSON 檔名為 1-1_1.json
    "author": "Starry-Wind",                 // 作者名稱（第二作者不得覆蓋第一作者）
    "start": [                                 // 開局傳送地圖操作步驟
        {"map": 1},                            // 按下 m 鍵開啟地圖
        {"picture\\orientation_1.jpg": 1.5}, // 識別 orientation_1.jpg 後移動滑鼠到圖片中間並按鍵
        {"picture\\map_1.jpg": 2},           // 識別區域名對應圖片，例如 "烏拉烏拉"
        {"picture\\map_1_point_1.jpg": 1.5}, // 第一個傳送點的圖片
        {"picture\\transfer.jpg": 1.5},      // "傳送"文字的圖片
        {"space": 1},                          // 按下 space 鍵
        {"b": 1},                              // 按下 b 鍵
        {"await": 5}                           // 等待 5 秒
    ]
}
```

### 主介面檢測

每張地圖在開始執行 `map` 裡的步驟前，指令碼都會固定執行一次 `back_to_main`
（效果等同於在 `start` 末尾寫 `{"main": 1}`，但不需要地圖自己寫）：

1. 先識別主介面（左上角燈泡圖示）
2. 不在主介面時按 `ESC` 返回；遇到「是否放棄遊玩？」確認框會先點掉；最多等待 120 秒，超時終止本輪並提示檢查遊戲介面

所以 `map` 的第一步只有兩個前提：**當前一定在主介面**，且**這個狀態能從主介面按 `ESC` 到達**。編輯或錄製地圖時請注意：

- 不要把「傳送落地後殘留的對話 / 選單 / 戰鬥」當作第一步的前提。需要處理這類殘留時，把它放在 `start` 的末尾（主介面檢測之前），或確認按 `ESC` 能回到主介面後再寫進 `map`
- `map` 開頭不需要再重複寫 `{"main": 1}`；也不要在開頭寫 `{"esc": 1}` —— 此時已在主介面，多餘的 `ESC` 會開啟 ESC 選單，後續步驟會從選單裡開始

---

## 鍵位對映

| 鍵位 | 對映 |
| --- | --- |
| `other` | 未列出的任意鍵都視為移動鍵，後面的數字代表按下的時間長短 |
| `x` | 進入戰鬥，map 對映為 `fighting=1` |
| 滑鼠左鍵 | 打障礙物，map 對映為 `fighting=2` |
| `f` | 互動鍵，後面的數字代表按下 F 鍵後等待的時間，預設 15 秒 |
| `r` / `space` | 互動鍵，後面的數字代表反覆按鍵的次數，間隔隨機 |
| `shutdown` | 關機標誌，鍵值無意義，控制開關在配置檔案中 |
| `mouse_move` | 視角轉動，因數值計算複雜（不同裝置數值不同），已被棄用 |
| `scroll` | 滑鼠滾輪滾動數值，同樣較複雜，未被啟用 |
| `e` | 鍵值為 1 時，使用秘技並追加普通攻擊 |
| `e` | 鍵值為 2 時，僅使用秘技；適用於強化型秘技角色 |
| `esc` | 只有鍵值為 1 時有意義，等同於按一次 Esc 鍵 |
| `v` | 等待 N 秒，map 對映為 `await=N` 秒 |

---

## 開發

### 目錄結構

| 目錄 / 檔案 | 說明 |
| --- | --- |
| `fhoe.py` | 主入口（命令列解析 + 各模式排程） |
| `get_width.py` | 螢幕寬度檢測工具 |
| `map/` | 地圖路線 JSON（按版本分子目錄，共 875 張） |
| `picture/` | 模板匹配截圖 |
| `utils/` | 核心邏輯分層（core / drivers / vision / flows / ui） |
| `tests/` | pytest 測試（全替身，無需遊戲視窗） |
| `tools/` | 開發輔助：地圖/圖片校驗與格式化指令碼 |
| `webui/` | 內建 WebUI 伺服器與前端 |
| `新圖注意事項/` | 新圖注意事項說明圖片 |
| `CLAUDE.md` | 工程規則與 AI 協作指引（開發順序/分層/硬規則/測試） |
| `requirements.txt` | Python 依賴 |
| `LICENSE` | GPL-3.0 |

### 架構與分層

專案按 **core → drivers → vision → flows → ui** 分層，依賴方向單向（`tests/test_architecture.py` 強制校驗）。

關鍵約束（詳見 `CLAUDE.md` §3）：

- 時間、輸入、畫面、狀態、結構、資源更新均有硬規則
- 預置與死程式碼有專門清理約定
- 地圖執行契約、ESC 前的介面修復有明確約定

### 測試與 CI

**測試**：`pytest`（全替身，無遊戲視窗；`xfail` 標記的是已記錄的真實缺陷），配合三個靜態校驗工具：

| 工具 | 作用 |
| --- | --- |
| `tools/validate_maps.py` | 地圖 JSON 結構校驗，出錯退出碼 1 |
| `tools/validate_pictures.py` | 圖片檔名全域性唯一 + `picture` 引用可解析 |
| `tools/format_maps.py --base <ref>` | R22 寫盤格式校驗，只攔截本次改動的地圖 |

**CI**（`.github/workflows/run.yml`，`windows-latest` + Python 3.11.5）：

- **test** 作業：pytest + 地圖校驗 + 圖片校驗 + 格式校驗
- **build** 作業：PyInstaller 打包 `Fhoe-Rail.exe` 與 `Start-WebUI.exe`，生成各 `.bat`，複製資源進 `dist`，打 tag 時經 `softprops/action-gh-release` 釋出 `Fhoe-Rail.zip` 並寫 `version.txt`

觸發：push 到任意分支/標籤（`paths` 限 `**.py` + `map/**.json`；標籤 push 不受 `paths` 過濾）。`fetch-depth: 0`（淺克隆拿不到基線）。

### 貢獻指南

歡迎提交最佳化/新版本的路線地圖，以及程式碼改進：

- 新地圖：錄製後按[錄製新地圖](#錄製新地圖)規範產出 JSON + 截圖，提交到 `map` 分支或交由管理員
- 程式碼：遵循 `CLAUDE.md` 的開發順序（可行性探針 → 契約與資源 → 純邏輯嚴格 TDD → 檢測器黃金圖 → 編排替身假時鐘 → 回放端到端），並確保本地 `pytest` + 三個校驗工具通過
- 提交前請跑一遍完整 CI（本地可用 `tools/` 下指令碼復現）

---

## 全自動鋤地（進階）

僅提供思路參考：

1. 進入電腦 BIOS 開啟**來電自啟**
2. 準備**智慧插座**×1（如米家智慧插座 3），定時開啟電源（推薦峰谷電的谷電時間）
3. 將星鐵的遊戲快捷方式（不是啟動器）放到 map 資料夾與開機自啟動資料夾
4. 開啟「跑完關機」

**缺點**：遇到更新或網路卡頓會卡死（指令碼未設計點選方案），建議再設定一個定時關閉電源（時間可參考之前跑完全圖後的日誌計時）。

---

## 相關專案

| 專案 | 說明 | 狀態 |
| --- | --- | --- |
| [StarRailAssistant](https://github.com/Starry-Wind/StarRailAssistant) | 原專案 | 停更 |
| [March7thAssistant](https://github.com/moesnow/March7thAssistant) | 聚合使用 · 三月七小助手 | 活躍 |
| [StarRailAutoProxy](https://github.com/DoctorReid/StarRailAutoProxy) | 鋤大地專案 · 一條龍 | 活躍 |
| [StarRail-FastRun](https://github.com/Souloco/StarRail-FastRun) | 鋤大地專案 · FastRun | 停更 |
| [StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot) | 模擬器專案 · 星鐵速溶茶 | 活躍 |
| [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) | 模擬宇宙專案 | 活躍 |

---

## 貢獻者

感謝以下貢獻者對本專案做出的貢獻

<a href="https://github.com/linruowuyin/Fhoe-Rail/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=linruowuyin/Fhoe-Rail" />

</a>

---

## 許可與免責宣告

**許可**：本專案以 [GPL-3.0](LICENSE) 開源，免費，僅供學習交流使用。開發者團隊擁有本專案最終解釋權。使用本軟體產生的所有問題與本專案及開發者團隊無關。禁止使用本軟體進行大規模商業化行為；若您遇到商家使用本軟體代練並收費，可能是裝置與時間等費用，產生的問題及後果與本軟體無關。本軟體為非商業化專案，故與其他軟體/遊戲/程式並不構成也不可能會構成不正當競爭以及著作權侵權，特此宣告。

**免責宣告（原文）**：

> 本軟體是一個外部工具，旨在自動化崩壞：星穹鐵道的遊戲玩法。它被設計成僅通過現有使用者介面與遊戲互動，並遵守相關法律法規。該軟體包旨在為使用者提供簡化、便捷的功能互動，並且不打算以任何方式破壞遊戲平衡或提供任何不公平的優勢。該軟體包不會以任何方式修改任何遊戲檔案或遊戲程式碼。

請注意，根據 miHoYo 的 [崩壞：星穹鐵道的公平遊戲宣言](https://sr.mihoyo.com/news/111246?nav=news&type=notice)：

> 「嚴禁使用外掛、加速器、指令碼或其他破壞遊戲公平性的第三方工具。」
>
> 「一經發現，米哈遊（下亦稱"我們"）將視違規嚴重程度及違規次數，採取扣除違規收益、凍結遊戲賬號、永久封禁遊戲賬號等措施。」

---

<div align="center">

**Fhoe-Rail** · 免費開源 · 僅供學習交流 · 請勿用於商業用途

</div>
