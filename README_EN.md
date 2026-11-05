<div align="center">

# Fhoe-Rail · Honkai: Star Rail Auto-Farming

[![GitHub release](https://img.shields.io/github/v/release/linruowuyin/Fhoe-Rail?label=Release&color=blue)](https://github.com/linruowuyin/Fhoe-Rail/releases)
[![GitHub stars](https://img.shields.io/github/stars/linruowuyin/Fhoe-Rail?label=Stars&color=yellow)](https://github.com/linruowuyin/Fhoe-Rail/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/linruowuyin/Fhoe-Rail?label=Forks&color=green)](https://github.com/linruowuyin/Fhoe-Rail/network)
[![License](https://img.shields.io/github/license/linruowuyin/Fhoe-Rail?label=License&color=orange)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)

**An image-recognition driven daily farming (锄大地) script for Honkai: Star Rail** — A lightweight fork of StarRailAssistant. Free and open source, for learning and exchange only.

**This project is a subset of [March7thAssistant](https://github.com/moesnow/March7thAssistant) (三月七小助手) and can be deployed and run independently (or aggregated within March7th)** — they share the onepush notification solution and the StarRail.exe path configuration convention; the project itself is a lightweight fork of [StarRailAssistant](https://github.com/Starry-Wind/StarRailAssistant).

</div>

---

<div align="center">

[简体中文](./README.md) | [繁體中文](./README_TW.md) | **English** | [日本語](./README_JA.md) | [한국어](./README_KR.md)

</div>

---

## Table of Contents

<table align="center">
<tr>
<td>

- [What is this](#what-is-this)
- [Features](#features)
- [Quick Start](#quick-start)
  - [Environment Requirements](#environment-requirements)
  - [Usage Notes](#usage-notes)
  - [How to Launch](#how-to-launch)
  - [Command-line Arguments](#command-line-arguments)
  - [Known Limitations](#known-limitations)

</td>
<td>

- [WebUI Control Panel](#webui-control-panel)
- [Notifications](#notifications)
- [Configuration](#configuration)
- [Maps](#maps)
  - [Map Versions](#map-versions)
  - [Selecting a Map](#selecting-a-map)
  - [Recording a New Map](#recording-a-new-map)
  - [Map JSON Format](#map-json-format)

</td>
<td>

  - [Main Interface Detection](#main-interface-detection)
- [Key Bindings](#key-bindings)
- [Development](#development)
  - [Directory Structure](#directory-structure)
  - [Architecture and Layering](#architecture-and-layering)
  - [Testing and CI](#testing-and-ci)
  - [Contribution Guide](#contribution-guide)

</td>
<td>

- [Fully Automatic Farming (Advanced)](#fully-automatic-farming-advanced)
- [Related Projects](#related-projects)
- [Contributors](#contributors)
- [License and Disclaimer](#license-and-disclaimer)

</td>
</tr>
</table>

---

## What is this

Fhoe-Rail is a **daily farming (clearing daily commissions / farming materials) automation script for Honkai: Star Rail** that runs on **Windows**.

It does not read or modify any game files or game code. Instead, it operates like a real player: **captures the game screen → template matching (OpenCV) to identify teleport points / interaction points → simulates keyboard and mouse** to execute pre-recorded routes. All farming routes are manually recorded by the community and shared as open source.

**What this is not:**

- ❌ Not a cheat/mod — does not inject processes, modify memory, or alter game files
- ❌ Not cross-platform — Windows only (depends on pywin32 / PyAutoGUI / PyGetWindow)
- ❌ Not a commercial product — free, open source, for learning and exchange only
- ⚠️ Using third-party scripts carries a **ban risk**. Please read the [Disclaimer](#license-and-disclaimer) at the end.

---

## Features

| Feature | Description |
| --- | --- |
| Daily Farming | Image-recognition based teleport point detection + pre-recorded routes. Launch without configuration. |
| Sprint | Sprint throughout the entire route to save time and improve efficiency. |
| Cloud Star Rail | Requires a 1920×1080 fullscreen game window. |
| Whitelist / Blacklist | Run only / forbid specific maps. |
| Token Collection | Automatically buy expired mail packages, Edin tokens, and Amphoreus Memory tokens. |
| HuangQuan-specific Maps | Accelerate farming. Consumes snack items; can auto-synthesize them. |
| Continue at 4 AM | After one run, wait until 4 AM the next day to continue (cross-day continuous farming). |
| Technique | Configurable technique (E skill) usage. |
| End Actions | After finishing, automatically shut down / log off / close a specified process. |
| Scheduled Runs | Schedule runs at a set time. |
| WebUI | Built-in local control panel with zero dependencies. |

---

## Quick Start

### Environment Requirements

| Requirement | Description |
| --- | --- |
| OS | Windows (depends on Win32 API) |
| Game Resolution | 1920×1080 (Cloud Star Rail must be fullscreen) |
| Game Frame Rate | 60 FPS |
| Python | 3.11+ (standalone exe requires no installation) |
| Network | Optional (notifications, update checks) |

### Usage Notes

1. This project records key presses and uses image recognition; routes are manually recorded by the community.
2. The character in slot 1 must be a ranged character. HuangQuan maps require HuangQuan; SilverWolf LV.999 maps require SilverWolf LV.999.
3. For ranged characters, adult models with attacks that have no displacement are recommended; girl (young female) models may get stuck on maps.
4. Unlock all teleport anchors beforehand and complete tasks that may interfere with recognition, otherwise the script may get stuck (this project does not handle that case).
5. Watch out for unopened mechanisms / quest markers.
6. Blacklist setup: launch with `--debug`, then add maps to the "forbidden run" list in settings. If "禁闭舱段" is not unlocked, add "禁闭舱段"; if "绥园" is not unlocked, add "绥园".
7. Do not modify the default key bindings.
8. The screen must not have any overlays (be careful of pop-ups).
9. Do not touch the mouse or keyboard when the game is not in auto-battle.

### How to Launch

| Method | Description |
| --- | --- |
| Menu (Recommended) | Double-click `1点这里.bat` or `Fhoe-Rail.bat` and follow the menu prompts. |
| No-config | Run `Fhoe-Rail.exe` directly. |
| WebUI | Double-click `Start-WebUI.bat`; it opens http://127.0.0.1:8666 automatically. |
| From Source | `pip install -r requirements.txt` then `python fhoe.py`. |

### Command-line Arguments

| Argument | Description |
| --- | --- |
| `--debug` | Three-level map selection menu (includes settings). |
| `--dev` | Same as `--debug`, but auto-reselects each round. |
| `--white` | Whitelist mode. |
| `--record` | Record a new map. |
| `--test` | Test mode. |
| `--config` | Configuration mode. |
| `--map <ID>` | Run a single map only, e.g. `3-5_1`. |
| `--range <start> <end>` | Run from start to end in list order (inclusive), e.g. `3-5_1 3-5_2`. |
| `--map-version <name>` | Temporarily specify a version, e.g. `HuangQuan`. |
| `--webui-server` | Launch the built-in WebUI (port 8666). |

**Constraint:** The start and end of a range must be in the same map version, and the end cannot come before the start in list order.

### Known Limitations

1. Recognition relies on screen capture; any overlay (pop-up, other window, mouse tooltip) may affect recognition.
2. Some screens cannot be recognized in fullscreen; switch to windowed and retry.
3. Using the script carries a ban risk; evaluate it yourself.

---

## WebUI Control Panel

The built-in local WebUI has **zero third-party dependencies** (Python standard library only).

- **Launch:** Double-click `Start-WebUI.bat`; it auto-requests admin privileges and opens http://127.0.0.1:8666.
- **Re-launch:** If the port is occupied by our own WebUI, the new instance lets the old one exit gracefully and takes over. If occupied by another program, it only reports an error and does not kill the process.
- **Command Center:** Run status and statistics (battle count / total time / sprint savings / stutters).
- **Run Control:** Seven modes — default / whitelist / single map / range / developer single map / record / install dependencies — with real-time output.
- **Map Catalog:** Browse all routes by version / planet; search by name, ID, or author.
- **Settings:** Visually edit every config.json setting; supports save / copy / download.
- **Voyage Log:** View real-time logs.
- **New Map Notes:** View images with notes about new maps.

---

## Notifications

**19 channels:**

| Channel | Notes |
| --- | --- |
| Windows Desktop Notification | Zero-configuration default. |
| Server酱 (ServerChan) | — |
| Server酱³ (ServerChan³) | — |
| PushPlus | — |
| Telegram | — |
| Bark | — |
| DingTalk | — |
| WeCom (Enterprise WeChat) Bot / App | — |
| Feishu (Lark) | — |
| Discord | — |
| Gotify | — |
| Ntfy | — |
| PushDeer | — |
| Qmsg | — |
| SMTP Email | — |
| QQ Bot | — |
| Custom Request | — |
| Generic Webhook | — |

**Timing:** Notify on farm start / farm complete (with statistics summary) / on error — each can be toggled independently.
**Test:** The WebUI can send a test notification directly.

---

## Configuration

`config.json` (in the repository or run directory). **24 settings:**

| Setting | Default | Description |
| --- | --- | --- |
| `auto_final_fight_e` | `false` | Whether to change the final strike of each map to a technique attack. |
| `auto_final_fight_e_cnt` | — | Max number of technique attacks for the final strike of each map. |
| `allow_fight_e_buy_prop` | `false` | Whether to auto-consume technique snacks (auto-allowed for HuangQuan maps). |
| `auto_run_in_map` | `false` | Whether to sprint while in the map. |
| `detect_fight_status_time` | `5` | Seconds to recognize whether battle has started. |
| `map_version` | — | Map folder to use. |
| `main_map` | — | Preferred planet: 1=Space Station, 2=Jarilo-VI, 3=Xianzhou, 4=Penacony. |
| `allow_run_again` | `false` | Run each map twice consecutively to avoid missing enemies. |
| `allow_run_next_day` | `false` | Wait until 4 AM and continue from the start. |
| `allow_map_buy` | `false` | Allow buying tokens and expired mail packages. |
| `allow_snack_buy` | `false` | Allow buying materials to synthesize technique snacks. |
| `allow_memory_token` | `false` | Allow obtaining Amphoreus Memory tokens. |
| `allowlist_mode_once` | `false` | Whitelist for this run only. |
| `auto_shutdown` | `0` | System action after farming: 0=none, 1=shut down, 2=log off, 3=close specified process. |
| `taskkill_name` | — | Process name to close when `auto_shutdown=3`. |
| `webhook_url` | — | Generic webhook notification URL. |
| `notify_enabled` | `false` | Enable notifications. |
| `notify_channel` | — | Channel: windows desktop / serverchan / pushplus / telegram / dingtalk, etc. |
| `notify_key` | — | Channel secret key. |
| `notify_chat_id` | — | Target parameter (e.g. Telegram chat_id). |
| `notify_params` | — | Channel advanced parameters (JSON). |
| `notify_on_start` | `false` | Notify on start. |
| `notify_on_end` | `false` | Notify on complete (includes statistics). |
| `notify_on_error` | `false` | Notify on error. |

---

## Maps

Maps are JSON files in `map/<version>/`, organized by version directory.

### Map Versions

| Version | Description |
| --- | --- |
| `default` | Default, adapted to most ranged characters. |
| `default_lite` | Lite version. |
| `technique` | No longer maintained (uses many purple techniques and techniques frequently in battle). |
| `HuangQuan` | HuangQuan-specific; you must have enough technique snacks. |
| `SilverWolfLv999` | SilverWolf LV.999-specific; converted from HuangQuan maps, does not use E technique. |

**Farming model classification:** A small number of characters may get stuck due to body size; ranged adult models with no-displacement attacks are preferred; girl (young female) models may get stuck.

### Selecting a Map

Use `--debug` mode (or run `自选地图.bat`) and choose [Settings].

### Recording a New Map

Thanks to @AlisaCat for the contribution.

**Operation restrictions:** No mouse view rotation; only one valid key at a time (no simultaneous presses). Supported: W/S/A/D move, F interact, R Penacony dream-bubble bridge, E technique (often used for HuangQuan farming), X enter battle, right-click to break obstacles / cancel sprint by running into a wall, `v` wait N seconds. Other keys require manual config changes.

**Recording rules:** Only key-press times and view movement are recorded, not pauses. Recommended to record slowly, one key at a time, for accuracy.

**Finish:** Press F9 to stop and save, generating `output(时间).json`.

**Output & configuration:** ① Rename to the target map JSON filename ② Rename the teleport point screenshot and save it to the `picture` folder ③ New maps can be submitted to the `map` branch or handed to an admin.

**Screenshot requirements:** Avoid repeated text (e.g. for 「支援舱段」「禁闭舱段」, only capture the support and the confinement parts, otherwise recognition may fail and mis-click); try not to capture text (for future multi-language adaptation); keep the capture area as small as possible.

### Map JSON Format

Example:

```json
{
  "name": "乌拉乌拉-1",
  "author": "Starry-Wind",
  "start": [
    {"map": 1},
    {"picture\\orientation_1.jpg": 1.5},
    {"picture\\map_1.jpg": 2},
    {"picture\\map_1_point_1.jpg": 1.5},
    {"picture\\transfer.jpg": 1.5},
    {"space": 1},
    {"b": 1},
    {"await": 5}
  ]
}
```

- `name`: map display name (filename is `1-1_1.json`).
- `author`: original author (a second author must not override the first).
- `start`: steps. `{"map":1}` presses `m` to open the map. `{"picture\\orientation_1.jpg":1.5}` recognizes the image then moves the mouse to its center and presses the key. `{"picture\\map_1.jpg":2}` recognizes the region name (e.g. 乌拉乌拉). `{"picture\\map_1_point_1.jpg":1.5}` is the first teleport point image. `{"picture\\transfer.jpg":1.5}` is the "transfer" text image. `{"space":1}` presses space. `{"b":1}` presses b. `{"await":5}` waits 5 seconds.

### Main Interface Detection

Before executing the `map` steps, the script always performs one `back_to_main` (equivalent to writing `{"main":1}` at the end of `start`, but you don't need to write it yourself):

1. First recognize the light-bulb icon at the top-left of the main interface.
2. If not on the main interface, press ESC to return. If the 「是否放弃游玩？」 (quit?) dialog appears, dismiss it first.
3. Wait at most 120 seconds; on timeout, abort this round and prompt to check the game interface.

**Two preconditions for the first step of `map`:** You must be on the main interface, and this state must be reachable from the main interface by pressing ESC.

**Editing / recording notes:** Do not treat residual dialogs / menus / battles after a teleport as the first-step precondition (if they need handling, put them at the end of `start` before main-interface detection, or confirm that pressing ESC returns to the main interface before writing them into `map`). At the start of `map`, do not repeat `{"main":1}` and do not write `{"esc":1}` (you are already on the main interface; an extra ESC opens the ESC menu).

---

## Key Bindings

| Key | Meaning |
| --- | --- |
| `other` | Any unlisted key is treated as a movement key (number = hold duration). |
| `x` | Enter battle (`map` mapping: `fighting=1`). |
| Left Mouse Button | Break obstacles (`map` mapping: `fighting=2`). |
| `f` | Interact key (number = wait time after pressing F, default 15 seconds). |
| `r` · `space` | Interact key (number = repeat count, random interval). |
| `shutdown` | Shutdown flag (value meaningless; control switch is in config). |
| `mouse_move` | View rotation — deprecated (numerical calculation is complex, values differ by device). |
| `scroll` | Mouse wheel — not enabled (values also complex). |
| `e` | Value 1 = use technique then add a normal attack; value 2 = use technique only (for enhanced-technique characters). |
| `esc` | Only value 1 is meaningful (equivalent to pressing ESC once). |
| `v` | Wait N seconds (`map` mapping: `await=N`). |

---

## Development

### Directory Structure

| Path | Description |
| --- | --- |
| `fhoe.py` | Main entry (command-line parsing + mode dispatch). |
| `get_width.py` | Screen width detection utility. |
| `map/` | Map route JSON files, by version subdirectory, 875 total. |
| `picture/` | Template matching screenshots. |
| `utils/` | Core logic layering (core / drivers / vision / flows / ui). |
| `tests/` | pytest tests, fully mocked, no game window needed. |
| `tools/` | Dev helpers: map image validation and formatting scripts. |
| `webui/` | Built-in WebUI server and frontend. |
| `新图注意事项/` | Images with notes about new maps. |
| `CLAUDE.md` | Engineering rules and AI collaboration guide (dev order / layering / hard rules / testing). |
| `requirements.txt` | Python dependencies. |
| `LICENSE` | GPL-3.0. |

### Architecture and Layering

The dependency direction is **one-way**: `core → drivers → vision → flows → ui` (enforced by `tests/test_architecture.py`).

**Key constraints (CLAUDE.md §3):** Time / input / screen / state / structure / resource updates all have hard rules; there are dedicated cleanup conventions for presets and dead code; map execution contract and pre-ESC interface repair conventions are explicitly defined.

### Testing and CI

**Testing:** pytest (fully mocked, no game window; `xfail` marks known real defects) + three static validations:
- `tools/validate_maps.py` — map JSON structure validation (exit code 1 on error).
- `validate_pictures.py` — picture filenames globally unique + picture references resolvable.
- `format_maps.py --base <ref>` — R22 write format validation, only checks current changes.

**CI (`.github/workflows/run.yml`, windows-latest + Python 3.11.5):**
- `test` job: pytest + map validation + picture validation + format validation.
- `build` job: PyInstaller packages `Fhoe-Rail.exe` and `Start-WebUI.exe`, generates the `.bat` files, copies resources into `dist`, and on tags publishes `Fhoe-Rail.zip` via `softprops/action-gh-release` and writes `version.txt`.

**Trigger:** push to any branch/tag (paths limited to `**.py` + `map/**.json`; tag pushes are not filtered by paths). `fetch-depth: 0` (shallow clones cannot get the baseline).

### Contribution Guide

Contributions of optimized/new routes and code improvements are welcome:
- **New maps:** Record according to the recording rules, produce JSON + screenshots, submit to the `map` branch or hand to an admin.
- **Code:** Follow the CLAUDE.md development order (feasibility probe → contract & resources → pure logic strict TDD → detector golden images → orchestration mock clock → replay end-to-end) and ensure local pytest + the three validation tools pass.
- **Before submitting:** Run the full CI (locally reproducible with the `tools/` scripts).

---

## Fully Automatic Farming (Advanced)

Reference approach:
1. Enable "power on after AC loss" in BIOS.
2. Prepare a smart plug ×1 (e.g. Xiaomi Smart Plug 3) to power on at a scheduled time (peak/off-peak electricity recommended).
3. Put the Honkai: Star Rail game shortcut (not the launcher) in the `map` folder and the startup folder.
4. Enable "shut down after farming".

**Drawback:** If the game updates or the network stutters, the script may get stuck (it is not designed to click through updates). It is recommended to also set a timed power-off (reference the log timing from the previous full run).

---

## Related Projects

| Project | Description | Status |
| --- | --- | --- |
| [StarRailAssistant](https://github.com/Starry-Wind/StarRailAssistant) | Original project | Discontinued |
| [March7thAssistant](https://github.com/moesnow/March7thAssistant) | Aggregation tool · 三月七小助手 | Active |
| [StarRailAutoProxy](https://github.com/DoctorReid/StarRailAutoProxy) | Farming · one-stop | Active |
| [StarRail-FastRun](https://github.com/Souloco/StarRail-FastRun) | Farming · FastRun | Discontinued |
| [StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot) | Emulator · 星铁速溶茶 | Active |
| [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) | Simulated Universe | Active |

---

## Contributors

Thanks to the following contributors for their contributions to this project

<a href="https://github.com/linruowuyin/Fhoe-Rail/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=linruowuyin/Fhoe-Rail" />

</a>

---

## License and Disclaimer

**GPL-3.0** — free, open source, for learning and exchange only. The developer team has final interpretive authority. All problems arising from using this software are unrelated to this project and the developer team. Large-scale commercialization is prohibited (if a merchant charges for leveling services, that may be device/time fees; resulting problems and consequences are unrelated to this software). This non-commercial project does not constitute unfair competition or copyright infringement.

**Disclaimer (original text):**

> This software is open source, free of charge and for learning and exchange purposes only. The developer team has the final right of interpretation. All problems arising from the use of this software are unrelated to this project and the developer team.

**Fair Play Declaration** (from miHoYo, [source](https://sr.mihoyo.com/news/111246?nav=news&type=notice)):

> "The use of cheats, accelerators, scripts, or other third-party tools that harm the fairness of the game is strictly prohibited."
>
> "Once discovered, miHoYo (hereinafter "we") will, depending on the severity and number of violations, take measures such as deducting illegal gains, freezing game accounts, and permanently banning game accounts."

**Fhoe-Rail · Free & Open Source · For Learning & Exchange Only · Not for Commercial Use**
