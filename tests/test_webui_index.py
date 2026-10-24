"""webui/index.html —— 日志框「选择 / 复制」的静态契约。

前端没有 JS 测试运行器（服务端测试只起 HTTP），所以这里钉住两条结构性约束，
防止以后又改回「每次刷新直接 innerHTML=」：

1. 两个日志框都可聚焦 —— 点击后焦点在框里，Ctrl+A 才有明确的作用域；
2. 周期刷新必须经过 `updateLogBox()`：框内存在选区时会冻结 DOM，
   否则用户往上拖选时节点被整体替换，选区会跳回第一行。
"""

from pathlib import Path

HTML = (
    Path(__file__).resolve().parent.parent / "webui" / "index.html"
).read_text(encoding="utf-8")


def test_log_boxes_are_focusable():
    assert 'id="log-box" tabindex="0"' in HTML
    assert 'id="run-output" tabindex="0"' in HTML


def test_ctrl_a_is_scoped_to_log_boxes():
    assert 'String(e.key).toLowerCase() !== "a"' in HTML
    assert "selectBoxContents(box)" in HTML


def test_periodic_refresh_goes_through_the_selection_guard():
    assert "function selectionInBox(" in HTML
    assert "function updateLogBox(" in HTML
    assert "updateLogBox(outEl, html, autoScroll);" in HTML
    assert "outEl.innerHTML =" not in HTML, "实时输出又绕过了 updateLogBox，会破坏正在进行的选区"
