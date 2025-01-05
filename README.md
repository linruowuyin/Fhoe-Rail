## 注意事项

- 锄大地可免配置启动
- [附加功能](https://github.com/linruowuyin/Fhoe-Rail/tree/master?tab=readme-ov-file#%E5%85%B3%E4%BA%8E%E9%85%8D%E7%BD%AE)需要自行在配置中打开，黄泉锄大地需要在设置里开启对应地图
- 运行前请阅读[运行须知](https://github.com/linruowuyin/Fhoe-Rail/tree/master?tab=readme-ov-file#%E8%BF%90%E8%A1%8C%E9%A1%BB%E7%9F%A5)，[免责声明](https://github.com/linruowuyin/Fhoe-Rail/tree/master?tab=readme-ov-file#%E5%85%8D%E8%B4%A3%E5%A3%B0%E6%98%8E)


## 功能简介

- **锄地**： 每日锄地，基于图片识别传送点 + 预录线路
- **疾跑**： 锄地过程为疾跑状态，减少运行时间提升效率
- **购买代币**： 过期邮包/艾迪恩代币
- **黄泉专用地图**：加速锄地，需要消耗奇巧零食，可自动合成零食
- **4点续锄(跨日)**：可配置运行一次后等待至凌晨4点继续运行
- 可配置使用秘技
- 可配置锄地结束后自动关机/注销
- 可配置定时后自动运行

> 未来规划：GUI

## 快速上手运行

### 运行须知


- **1号位**为跑图角色，需要是**远程角色**，使用**黄泉专用地图**时必须是**黄泉**
- 远程角色跑图时选择成年模型且攻击无位移最佳，少女模型可能会卡图，查看[跑图模型分类](https://github.com/linruowuyin/Fhoe-Rail/tree/master?tab=readme-ov-file#%E8%B7%91%E5%9B%BE%E6%A8%A1%E5%9E%8B%E5%88%86%E7%B1%BB)
- **帧数：60帧**
- 游戏分辨率：**1920*1080**，部分屏幕无法识别全屏幕，请切换非全屏幕重试
- **集成版本选图**请在命令行输入：Fhoe-Rail.exe --debug
- 请事先开启全部传送锚点，完成地图上可以干扰图片识别传送锚点的一切任务，因此造成的卡图现象本项目不予处理
- 【仅适用于最新版本】禁闭舱段未开启的，请删除1-4-X；绥园未开启的，请删除3-5-X；匹诺康尼未开启的，请删除4-X
- 其他地方卡住的，请留意是否有未开启的机关或者地图上有任务标识等影响识别
- **请不要修改默认键位，由此造成的卡图请自行解决**

### 快速开始

- 运行`Fhoe-Rail.exe`直接免配置开启
- 或运行`自选地图.bat`进行一些相关地图等配置后运行

### 已知缺陷

- 程序闪退可能造成`ALT键`或`SHIFT键`持续处于按下状态，需要手动按下解除
- 识图为截取游戏画面，所以不能有任何覆盖（小心各类弹窗）
- 请勿在非自动战斗状态时移动鼠标或操作键盘

## 进阶内容与配置
<details>
<summary>查看进阶内容</summary>


### 跑图模型分类

现有模型分类（可能有误，待修正）：

| 模型 | 角色                                           |
| ---- | --------------------------------------------- |
| 少女 | 青雀、佩拉、符玄、三月七、艾丝妲              |
| 成女 | 阮•梅、托帕、黑天鹅、布洛妮娅、驭空、娜塔莎、 |
| 少年 | 无                                            |
| 成男 | 丹恒•饮月、瓦尔特                             |


### 地图选择

地图选择方式：以【debug模式运行】或直接运行【自选地图.bat】，选择【设置】，即可选择对应的地图

| 地图名称 | 地图说明 |
| ---------- | -------------------------------------------------------- |
| default       | 默认地图，适配大部分远程角色 |
| technique     | 已无人维护，<del>加入了较多的击打紫色秘技，且在战斗中使用较多秘技</del> |
| HuangQuan     | 黄泉专用地图，自行备足秘技零食 |


### 配置说明

配置文件为 config.json

配置对应项目时，是均为true，否均为false

| 配置项目 | 配置说明 |
| ----------------------- | ----------------------------------- |
| auto_final_fight_e | 是否允许每个地图最后一击改为秘技攻击 |
| auto_final_fight_e_cnt | 每个地图最后一击为秘技攻击上限次数 |
| allow_fight_e_buy_prop | 是否允许自动吃秘技零食，使用黄泉地图时会自动设置为允许 |
| auto_run_in_map | 是否允许在地图中疾跑 |
| detect_fight_status_time | 识别是否进入战斗的时间（秒），默认5 |
| map_version | 使用的地图文件夹 |
| main_map | 优先星球，1-空间站，2-雅利洛VI，3-仙舟，4-匹诺康尼 |
| allow_run_again | 是否允许每次运行连续锄地2次避免漏怪 |
| allow_run_next_day | 是否允许等待至下一个凌晨4点继续从头锄地 |
| allow_map_buy | 是否允许购买 代币 与 过期邮包 |
| allow_snack_buy | 是否允许购买并合成秘技零食的制作材料 |


### 地图录制方式

感谢 [@AlisaCat](https://github.com/AlisaCat-S) 的贡献。


1. **操作限制**：
   - 禁止使用鼠标移动视角。
   - <del>只能使用方向键左右键来调整视角（脚本运行后方向键会映射为鼠标移动）。</del>
   - 录制过程中，每次只能按下一个有效按键，不能同时按下多个按键。

2. **录制规则**：
   - 脚本仅记录按键按下的时间和视角移动，不会记录停顿时间。
   - 推荐逐个按键慢速录制，以确保准确性。

3. **录制完成**：
   - 按下 `F9` 停止录制并保存。
   - 录制支持的按键包括 `W`、`S`、`A`、`D`、`F`、`R`、`X`、鼠标右键。
   - 其他键值需手动修改配置文件。

4. **输出与配置**：
   - 录制完成后会生成一个 `output(时间).json` 文件。
   - 将其重命名为目标地图的 JSON 文件名。
   - 同时将传送点截图重命名后保存到 `picture` 文件夹，即可使用。
   - 如果有新地图录制需求，可以提交到 `map` 分支，或者交由管理员提交。
4. **截图图片要求**
   - 截图文字识别，尽量避免有重复字样，如：支援舱段、禁闭舱段...此时应只截图支援和禁闭，否则一定识别不到就会乱点
   - 尽量不截图文字：便于以后适配多种语言版本
   - 截图图片尽量小：图片会越加越多，适当缩小截图范围

#### 地图 JSON 填写示例

```json
{
    "name": "乌拉乌拉-1",                     // 地图 JSON 文件名为 1-1_1.json
    "author": "Starry-Wind",                 // 作者名称（第二作者不得覆盖第一作者）
    "start": [                                 // 开局传送地图操作步骤
        {"map": 1},                            // 按下 m 键打开地图
        {"picture\\orientation_1.jpg": 1.5}, // 识别 orientation_1.jpg 图片后，移动鼠标到图片中间并按键
        {"picture\\map_1.jpg": 2},           // 识别区域名对应的图片，例如 "乌拉乌拉"
        {"picture\\map_1_point_1.jpg": 1.5}, // 第一个传送点的图片
        {"picture\\transfer.jpg": 1.5},      // "传送"文字的图片
        {"space": 1},                          // 按下 space 键
        {"b": 1},                              // 按下 b 键
        {"await": 5}                           // 等待 5 秒
    ]
}
```


### 键位映射

| 键位       | 映射                                                     |
| ---------- | -------------------------------------------------------- |
| other      | 未列出的任意键都视为移动键，后面的数字代表按下的时间长短 |
| X          | 进入战斗，map映射为fighting=1                            |
| 鼠标左键   | 打障碍物，map映射为fighting=2                            |
| f/r/space  | 交互键，后面的数字代表反复按键的时间次数，间隔随机       |
| shutdown   | 关机标志，键值无意义，控制开关在配置文件中               |
| mouse_move | 视角转动，因数值计算复杂（不同设备数值不同），已被弃用   |
| scroll     | 鼠标滚轮滚动的数值，同样较为复杂，未被启用               |
| e          | 键值为1时，使用秘技并追加普通攻击              |
| e          | 键值为2时，仅使用秘技；适用于强化型秘技角色              |
| esc        | 只有键值为1时有意义，等同于按下了一次Esc键               |

---

### 全自动锄地流程

仅提供思路作为参考：
进入电脑bios开启来电自启功能，需智能插座*1（如米家智能插座3），定时开启电源（推荐峰谷电的谷电时间），将星铁的游戏快捷方式（不是启动器）放到map文件夹和开启自启动文件夹，开启跑完关机

缺点：遇到更新或者网络卡顿会卡死住（脚本未设计点击方案），所以建议再设定一个定时关闭电源（时间可参考之前跑完全图后的日志计时）

</details>

## 相关项目

- 原项目 StarRailAssistant [https://github.com/Starry-Wind/StarRailAssistant](https://github.com/Starry-Wind/StarRailAssistant)

- 聚合使用 March7thAssistant [https://github.com/moesnow/March7thAssistant](https://github.com/moesnow/March7thAssistant)

- 锄大地同类程序 StarRailAutoProxy [https://github.com/DoctorReid/StarRailAutoProxy](https://github.com/DoctorReid/StarRailAutoProxy)

- 锄大地同类程序 StarRail-FastRun [https://github.com/Souloco/StarRail-FastRun](https://github.com/Souloco/StarRail-FastRun)

- 模拟器运行 StarRailCopilot [https://github.com/LmeSzinc/StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot)

## 免责声明

本软件是一个外部工具旨在自动化崩坏星轨的游戏玩法。它被设计成仅通过现有用户界面与游戏交互,并遵守相关法律法规。该软件包旨在提供简化和用户通过功能与游戏交互,并且它不打算以任何方式破坏游戏平衡或提供任何不公平的优势。该软件包不会以任何方式修改任何游戏文件或游戏代码。

This software is open source, free of charge and for learning and exchange purposes only. The developer team has the final right to interpret this project. All problems arising from the use of this software are not related to this project and the developer team. If you encounter a merchant using this software to practice on your behalf and charging for it, it may be the cost of equipment and time, etc. The problems and consequences arising from this software have nothing to do with it.

本ソフトウェアは、崩壊：スターレイルのゲームプレイを自動化するために設計された外部ツールです。 既存のユーザーインターフェイスを通じてのみゲームと連動し、関連法規を遵守するように設計されています。 本パッケージは、その機能性により、シンプルさとゲームとのユーザーインタラクションを提供することを目的としており、ゲームバランスを崩したり、不当な利益を提供することは一切意図していません。 本パッケージはゲームファイルやゲームコードを一切変更しません。

本软件开源、免费，仅供学习交流使用。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目与开发者团队无关。禁止使用本软件进行大规模商业化行为；若您遇到商家使用本软件进行代练并收费，可能是设备与时间等费用，产生的问题及后果与本软件无关。软件非商业化项目，故与其他软件/游戏/程序并没有也不可能会构成不正当竞争、以及著作权侵权的行为，特此声明。

请注意，根据MiHoYo的 [崩坏:星穹铁道的公平游戏宣言](https://sr.mihoyo.com/news/111246?nav=news&type=notice):

```
"严禁使用外挂、加速器、脚本或其他破坏游戏公平性的第三方工具。"
"一经发现，米哈游（下亦称“我们”）将视违规严重程度及违规次数，采取扣除违规收益、冻结游戏账号、永久封禁游戏账号等措施。"
```

