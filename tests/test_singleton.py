"""utils/core/singleton.py —— SingletonMeta 的行为契约。"""

import threading
import time

import pytest

from utils.core.singleton import SingletonMeta


class Sample(metaclass=SingletonMeta):
    def __init__(self, value=None):
        self.value = value


class Sub(Sample):
    pass


class NotASingleton:
    pass


def test_same_class_returns_same_instance():
    assert Sample() is Sample()


def test_subclass_has_its_own_instance():
    assert Sample() is not Sub()
    assert Sub() is Sub()


def test_arguments_are_ignored_after_first_construction():
    """后续调用不会重新 __init__，这是单例的既定语义（也是容易踩的坑）。"""
    first = Sample(value="a")
    second = Sample(value="b")
    assert first is second
    assert second.value == "a"


def test_plain_class_is_unaffected():
    assert NotASingleton() is not NotASingleton()


@pytest.mark.xfail(
    strict=True,
    reason="SingletonMeta.__call__ 的 check-then-set 没有加锁，并发构造会创建多个实例",
)
def test_concurrent_construction_yields_single_instance():
    created = []

    class Slow(metaclass=SingletonMeta):
        def __init__(self):
            created.append(object())
            time.sleep(0.05)

    threads = [threading.Thread(target=Slow) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(created) == 1
