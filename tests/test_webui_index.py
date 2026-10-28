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


def test_run_page_has_single_and_range_modes():
    assert '<option value="map">单图运行' in HTML
    assert '<option value="range">区间运行' in HTML
    assert "body.map_end = pickMapEnd.value" in HTML


def test_range_option_shows_the_cli_flag():
    """括号里写的是命令行参数，跟其它模式（--map / --dev / --record）一致。"""
    assert '<option value="range">区间运行（--range' in HTML


def test_range_end_defaults_to_the_last_map():
    """区间运行的终点默认是最后一张图：最后一个星球的最后一张。"""
    start = HTML.index("function fillMapListEnd")
    end = HTML.index("function ", start + 1)
    body = HTML[start:end]
    assert "maps[maps.length - 1].id" in body
    assert 'pickPlanetEnd.value = lastPlanet' in HTML


def test_probe_list_loads_more_on_scroll():
    """前 200 张之后滚到底要能接着加载 —— 后端按 offset 翻页。"""
    assert 'id="probe-more"' in HTML
    assert "function maybeLoadMoreProbe(" in HTML
    assert "IntersectionObserver" in HTML
    assert "offset: probeList.offset" in HTML


def test_probe_page_is_tree_plus_grid():
    """探针新布局：左侧 picture 目录树，右侧操作条 + 缩略图铺开（不是三步竖排）。"""
    assert 'id="probe-tree"' in HTML
    assert 'class="probe-layout"' in HTML
    assert "function renderProbeTree(" in HTML
    # 按目录取图：前端把选中的目录传给后端
    assert 'params.set("dir", probeState.dir)' in HTML
    # 旧的「② 跑探针」独立卡片与点击才显示的逻辑已经没了
    assert 'id="probe-run-box"' not in HTML
    assert "① 选一张模板" not in HTML


def test_config_actions_are_frozen_at_the_top():
    """保存/重新读取/查看JSON/下载 四个按钮在最上面并冻结，不随长表单滚走。"""
    toolbar = HTML.split('id="config-toolbar"', 1)[1].split("</div>", 1)[0]
    order = [
        toolbar.index('id="save-config"'),
        toolbar.index('id="reload-config"'),
        toolbar.index('id="open-json"'),
        toolbar.index('id="download-config"'),
    ]
    assert order == sorted(order), "按钮顺序：保存 → 重新读取 → 查看原始JSON → 下载"
    assert "position: sticky" in HTML.split(".config-toolbar", 1)[1].split("}", 1)[0]


def test_raw_json_lives_in_a_dialog():
    """原始 JSON 文本框移进对话框：对话框里复制 + 下载，页面上只剩四个按钮。"""
    assert 'id="json-modal-mask"' in HTML
    assert 'id="raw-json"' in HTML
    assert 'id="copy-config"' in HTML
    assert 'id="download-config-modal"' in HTML
    assert "🧾 原始 JSON" not in HTML, "页面里不该再有「原始 JSON」卡片"
    # 文本框必须落在对话框内部（在 openJsonModal 之前）
    assert HTML.index('id="json-modal-mask"') < HTML.index('id="raw-json"')
