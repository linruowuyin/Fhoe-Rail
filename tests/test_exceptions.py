"""utils/core/exceptions.py —— CustomException 的日志行为与调用栈信息。"""

import pytest

from utils.core.exceptions import CustomException


def test_is_an_exception_with_message():
    error = CustomException("地图数据错误")
    assert isinstance(error, Exception)
    assert str(error) == "地图数据错误"


def test_can_be_raised_and_caught():
    with pytest.raises(CustomException, match="boom"):
        raise CustomException("boom")


def test_logs_error_at_construction(log_records):
    CustomException("出问题了")
    errors = [r for r in log_records if r["level"].name == "ERROR"]
    assert len(errors) == 1
    assert errors[0]["message"] == "出问题了"


def test_construction_always_logs_even_if_caller_swallows(log_records):
    """构造即记录：调用方即使捕获处理，日志里也会留下一条 ERROR。"""
    try:
        raise CustomException("会被捕获")
    except CustomException:
        pass
    assert any(r["level"].name == "ERROR" for r in log_records)


def test_logs_something_at_debug_level(log_records):
    CustomException("boom")
    assert any(r["level"].name == "DEBUG" for r in log_records)


@pytest.mark.xfail(
    strict=True,
    reason="异常是先构造再抛出，构造时没有活跃异常，traceback.format_exc() 只会得到 "
    "'NoneType: None'，这条 debug 日志对定位问题毫无价值",
)
def test_debug_log_carries_a_real_traceback(log_records):
    CustomException("boom")
    debug_messages = [r["message"] for r in log_records if r["level"].name == "DEBUG"]
    assert debug_messages
    assert not any("NoneType: None" in message for message in debug_messages)
