原项目地址：https://github.com/Starry-Wind/StarRailAssistant

聚合使用请去：https://github.com/moesnow/March7thAssistant

### 免责声明

本软件是一个外部工具旨在自动化崩坏星轨的游戏玩法。它被设计成仅通过现有用户界面与游戏交互,并遵守相关法律法规。该软件包旨在提供简化和用户通过功能与游戏交互,并且它不打算以任何方式破坏游戏平衡或提供任何不公平的优势。该软件包不会以任何方式修改任何游戏文件或游戏代码。

This software is open source, free of charge and for learning and exchange purposes only. The developer team has the final right to interpret this project. All problems arising from the use of this software are not related to this project and the developer team. If you encounter a merchant using this software to practice on your behalf and charging for it, it may be the cost of equipment and time, etc. The problems and consequences arising from this software have nothing to do with it.

本软件开源、免费，仅供学习交流使用。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目与开发者团队无关。若您遇到商家使用本软件进行代练并收费，可能是设备与时间等费用，产生的问题及后果与本软件无关。

请注意，根据MiHoYo的 [崩坏:星穹铁道的公平游戏宣言](https://sr.mihoyo.com/news/111246?nav=news&type=notice):

```
"严禁使用外挂、加速器、脚本或其他破坏游戏公平性的第三方工具。"
"一经发现，米哈游（下亦称“我们”）将视违规严重程度及违规次数，采取扣除违规收益、冻结游戏账号、永久封禁游戏账号等措施。"
```

### 功能区分

- 相比原版更轻量，启动更快
- 但是相对缺失了一些功能
- 但同时我又增加了原版没有的功能
- 比如：跑完关机、使用秘技、自动启动

自动启动的使用方法：把星铁的快捷方式（不是启动器），放到map文件夹中，运行启动器后就无需操作了，脚本会自动启动游戏（目前无法应对有更新的情况）

### 键位映射

| 键位       | 映射                                                   |
| ---------- | ------------------------------------------------------ |
| WSAD       | 移动键，后面的数字代表按下的时间长短                   |
| X          | 进入战斗，map映射为fighting=1                          |
| 鼠标左键   | 打障碍物，map映射为fighting=2                          |
| F          | 交互键，后面的数字代表反复按F的时间长短，间隔随机      |
| shutdown   | 关机标志，键值无意义，控制开关在配置文件中             |
| mouse_move | 视角转动，因数值计算复杂（不同设备数值不同），已被弃用 |
| scroll     | 鼠标滚轮滚动的数值，同样较为复杂，未被启用             |
| e          | 只有键值为1时有意义，使用秘技并追加普通攻击            |

### 关于地图录制

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

   

### 关于识别问题

识图为截取游戏画面，所以不能有任何覆盖

### 关于秘技

当前版本的秘技功能仅为顺带做日常任务，只在1图实装。尚未制作匹配未实装的托帕，如作者抽到，可能会单独制作一个适用托帕的版本

### 设计缺陷

游戏闪退时程序无法正常识别错误，需要人工解决
请勿在非自动战斗状态时移动鼠标或操作键盘

### 关于跑图

请事先开完全部锚点，完成地图上可以干扰图片识别传送的一切任务，因此造成的卡图现象本项目不予处理

请不要修改默认键位，由此造成的卡图请自行解决

现有模型分类：

成年女性模型（且攻击为远程无位移）跑图最佳，如：娜塔莎、艾丝妲、三月七、布洛妮娅

少女模型可能会卡（概率较小），如：青雀、佩拉、符玄

成女有位移，如：驭空

青年男有位移，如：饮月丹恒

