[原项目:StarRailAssistant](https://github.com/Starry-Wind/StarRailAssistant)         [聚合使用March7thAssistant](https://github.com/moesnow/March7thAssistant)      [同类程序StarRailAutoProxy](https://github.com/DoctorReid/StarRailAutoProxy) 

[同类程序StarRail-FastRun](https://github.com/Souloco/StarRail-FastRun)       [模拟器运行StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot)             

------

### 免责声明

本软件是一个外部工具旨在自动化崩坏星轨的游戏玩法。它被设计成仅通过现有用户界面与游戏交互,并遵守相关法律法规。该软件包旨在提供简化和用户通过功能与游戏交互,并且它不打算以任何方式破坏游戏平衡或提供任何不公平的优势。该软件包不会以任何方式修改任何游戏文件或游戏代码。

This software is open source, free of charge and for learning and exchange purposes only. The developer team has the final right to interpret this project. All problems arising from the use of this software are not related to this project and the developer team. If you encounter a merchant using this software to practice on your behalf and charging for it, it may be the cost of equipment and time, etc. The problems and consequences arising from this software have nothing to do with it.

本ソフトウェアは、崩壊：スターレイルのゲームプレイを自動化するために設計された外部ツールです。 既存のユーザーインターフェイスを通じてのみゲームと連動し、関連法規を遵守するように設計されています。 本パッケージは、その機能性により、シンプルさとゲームとのユーザーインタラクションを提供することを目的としており、ゲームバランスを崩したり、不当な利益を提供することは一切意図していません。 本パッケージはゲームファイルやゲームコードを一切変更しません。

本软件开源、免费，仅供学习交流使用。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目与开发者团队无关。若您遇到商家使用本软件进行代练并收费，可能是设备与时间等费用，产生的问题及后果与本软件无关。

请注意，根据MiHoYo的 [崩坏:星穹铁道的公平游戏宣言](https://sr.mihoyo.com/news/111246?nav=news&type=notice):

```
"严禁使用外挂、加速器、脚本或其他破坏游戏公平性的第三方工具。"
"一经发现，米哈游（下亦称“我们”）将视违规严重程度及违规次数，采取扣除违规收益、冻结游戏账号、永久封禁游戏账号等措施。"
```

------

**集成版本选图**请在命令行输入：Fhoe-Rail.exe --debug

程序只支持**1920*1080游戏分辨率**，部分屏幕无法识别全屏幕，请切换非全屏幕重试

**程序缺陷**：程序闪退可能造成atl键或shift键持续处于按下状态，需要手动按下解除

识图为截取游戏画面，所以不能有任何覆盖（小心各类弹窗）

请勿在非自动战斗状态时移动鼠标或操作键盘

---

### 全自动锄地流程

仅提供思路作为参考：

进入电脑bios开启来电自启功能，需智能插座*1（如米家智能插座3），定时开启电源（推荐峰谷电的谷电时间），将星铁的游戏快捷方式（不是启动器）放到map文件夹和开启自启动文件夹，开启跑完关机

缺点：遇到更新或者网络卡顿会卡死住（脚本未设计点击方案），所以建议再设定一个定时关闭电源（时间可参考之前跑完全图后的日志计时）

---

### 关于地图

【仅适用于最新版本】禁闭舱段未开启的，请删除1-4-X；绥园未开启的，请删除3-5-X

其他地方卡住的，请留意是否有未开启的机关或者地图上有任务标识等影响识别

---

### 功能区分

- [x] 疾跑
- [x] 过期邮包
- [x] 使用秘技
- [x] 自动开/关机
- [x] 地图拖拽
- [ ] GUI

---

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
| e          | 只有键值为1时有意义，使用秘技并追加普通攻击              |
| esc        | 只有键值为1时有意义，等同于按下了一次Esc键               |

---

## 关于跑图

请事先开完全部锚点，完成地图上可以干扰图片识别传送的一切任务，因此造成的卡图现象本项目不予处理

请不要修改默认键位，由此造成的卡图请自行解决

现有模型分类：

成年女性模型（且攻击为远程无位移）跑图最佳，如：娜塔莎、艾丝妲、三月七、布洛妮娅

少女模型可能会卡（概率较小），如：青雀、佩拉、符玄

成女有位移，如：驭空

青年男有位移，如：饮月丹恒

---

### 关于地图录制

感谢[@AlisaCat](https://github.com/AlisaCat-S)

禁止用鼠标移动视角，只能使用方向键左右来移动视角（脚本运行后方向键左右会映射鼠标移动）

录制期间能且只能按动键盘上的一个有效按键（也就是不能同时按下多键）

脚本只会录制按键按下时间和移动的视角，不会录制停顿的时间（可以慢慢一个键一个键录制，保证录制准确性）

录制完成后F9停止录制并保存。

（只有WSADF鼠标右键X参与录制，其他键值只能自己修改）

1. 完成后将会生成output(时间).json文件，请把他重命名替换成你要更改的地图json，并且将传送点截图重命名并保存到picture即可使用 （就可以申请到map分支提交，或者交给管理提交）

2. 地图json中的空白填写示例：

   ~~~
   {
       "name": "乌拉乌拉-1",       （地图json名为1-1_1.json）
       "author": "Starry-Wind",   （作者名，第二作者不能覆盖第一作者名称）
       "start": [           （开局传送地图识别图片，并将鼠标移动至图片中间并按下按键）
           {"map": 1},         （按下m键打开地图）
           {"picture\\orientation_1.jpg": 1.5},     （识别到orientation_1.jpg图片后，将鼠标移动至图片中间并按下按键）
           {"picture\\map_1.jpg": 2},               （具体图片自己看，一般为该区域名"乌拉乌拉"的地图文字）
           {"picture\\map_1_point_1.jpg": 1.5},       （第一个传送点的图片）
           {"picture\\transfer.jpg": 1.5}              （"传送"字的图片）
       ]
   }
   ~~~
