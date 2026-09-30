"""core 向外部要东西时的接口（CLAUDE.md R4）。

core 层不允许依赖窗口 / 输入 / 图像库，也不该直接调 `time.time()` / `time.sleep()` ——
那样测试只能去替换整个 `time` 模块。这里定义协议，真实实现由入口装配后经参数传进来，
测试传一个假时钟即可。

只放"需要被替换"的东西。别往这里堆工具函数。
"""

import datetime
import time


class Clock:
    """时间来源。取"现在"和"等待"都走它。"""

    def now(self) -> datetime.datetime:
        return datetime.datetime.now()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


SYSTEM_CLOCK = Clock()
