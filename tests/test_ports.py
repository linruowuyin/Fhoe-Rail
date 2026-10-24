"""utils/core/ports.py —— 需要被替换的外部依赖的接口（CLAUDE.md R4）。"""

import datetime

from utils.core.ports import SYSTEM_CLOCK, Clock


class TestClock:
    def test_now_returns_a_datetime(self):
        assert isinstance(SYSTEM_CLOCK.now(), datetime.datetime)

    def test_sleep_zero_does_not_block(self):
        SYSTEM_CLOCK.sleep(0)

    def test_a_fake_only_needs_now_and_sleep(self):
        """业务代码只依赖这两个方法，替身实现它们就够 —— 不必去替换整个 time 模块。"""

        class Fake(Clock):
            def __init__(self):
                self.slept = []

            def sleep(self, seconds):
                self.slept.append(seconds)

        fake = Fake()
        fake.sleep(3)
        assert fake.slept == [3]
        assert isinstance(fake.now(), datetime.datetime)
