"""utils/flows/map_operations.py —— 地图流程主逻辑中被测得到的部分。"""

import ast
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import utils.flows.map_operations as operations_module
from utils.config.config import ConfigurationManager
from utils.vision.img import Img
from utils.flows.map_operations import MapOperations
from utils.core.map_statu import MapStatu
from utils.core.time_utils import TimeUtils

# 分发表会调用的 Handle 方法白名单。故意写成白名单而不是"任何未知属性都返回可调用对象"，
# 这样 map_operations 里出现拼写错误时会直接 AttributeError，而不是被静默吞掉。
HANDLE_METHODS = {
    "handle_space",
    "handle_caps",
    "handle_r",
    "handle_f",
    "handle_allow_skip_f",
    "handle_check",
    "mouse_move",
    "handle_fighting",
    "scroll",
    "handle_shutdown",
    "handle_e",
    "handle_esc",
    "handle_num",
    "handle_main",
    "handle_view_set",
    "handle_view_reset",
    "handle_view_rotate",
    "handle_await",
    "auto_use_technique_consumable",
    "handle_move",
    "handle_b",
    "handle_click_floor",
    "back_to_main",
}


class RecordingHandle:
    """只记录被调用的方法名与参数。"""

    def __init__(self):
        self.calls = []
        self.f_key_error = False
        self.fight_in_map = False
        self.last_step_run = False
        # 战斗计数归 handle.combat 持有（见 flows/combat.py）
        self.combat = SimpleNamespace(
            fighting_count=0, current_fighting_index=0, fight_in_map=False
        )
        self.movement = SimpleNamespace(last_step_run=False)

    def __getattr__(self, name):
        if name not in HANDLE_METHODS:
            raise AttributeError(
                f"map_operations 调用了未在白名单里的 Handle.{name}，请先确认是不是拼写错误"
            )

        def record(*args, **kwargs):
            self.calls.append((name, args))

        return record

    def called(self, name):
        return [call for call in self.calls if call[0] == name]


class MapStub:
    """Map 的替身，记录地图侧动作。"""

    def __init__(self, planet_png_lst=()):
        self.calls = []
        self.planet_png_lst = list(planet_png_lst)
        self.allow_drap_map_switch = False
        self.allow_scene_drag_switch = False
        self.allow_retry_in_map_switch = True
        self.multi_click = 1
        self.drag_exact = None
        self.drag_offset = None

    def _record(self, name):
        def capture(*args, **kwargs):
            self.calls.append((name, args))

        return capture

    def __getattr__(self, name):
        # check_* 返回布尔，其余都是记录型动作
        if name in {"check_allowlist_maps", "check_forbidden_maps"}:
            return lambda *args, **kwargs: False
        return self._record(name)

    def called(self, name):
        return [call for call in self.calls if call[0] == name]



def write_map(root, version, filename, payload):
    folder = root / "map" / version
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def set_config_on_disk(root, **values):
    """map_operations 的部分分支直接 read_json_file，绕过了内存缓存。"""
    path = root / "config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(values)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class PauseStub:
    """Pause 的替身。

    真实 Pause 会注册全局热键、还可能在暂停时抓屏弹窗，所以测试一律用它替掉。
    `answers` 是 check_pause 依次返回的值（用完就返回 False）；`waits` 记录闸门被调用次数。
    """

    def __init__(self, *answers):
        self.answers = list(answers)
        self.waits = 0
        self.checks = 0
        self.pending_key = None

    def check_pause(self, dev, last_point=""):
        self.checks += 1
        return self.answers.pop(0) if self.answers else False

    def wait_if_paused(self):
        self.waits += 1
        return 0.0


@pytest.fixture
def operations(make_instance, isolated_cwd, monkeypatch):
    monkeypatch.setattr(operations_module.time, "sleep", lambda seconds: None)
    instance = make_instance(
        MapOperations,
        cfg=ConfigurationManager(),
        map_info=SimpleNamespace(
            map_version="default", map_list=["map_1-1_0.json"]
        ),
        time_mgr=TimeUtils(),
        map_statu=MapStatu(),
        map=SimpleNamespace(
            check_allowlist_maps=lambda name: False,
            check_forbidden_maps=lambda name: False,
            planet_png_lst=[],
            open_map=lambda: None,
            align_angle=lambda: None,
            reset_round_count=lambda: None,
            get_map_list=lambda start, start_in_mid: [],
            allow_map_drag=lambda start: None,
            allow_scene_drag=lambda start: None,
            allow_multi_click=lambda start: None,
            allow_retry_in_map=lambda start: None,
            allow_click_offset=lambda start: None,
            allow_drap_map_switch=False,
            allow_scene_drag_switch=False,
            allow_retry_in_map_switch=True,
            multi_click=1,
        ),
        handle=SimpleNamespace(f_key_error=False),
        pause=PauseStub(),
        img=SimpleNamespace(),
        mouse_event=SimpleNamespace(last_search_allow_retry=False),
        calculated=SimpleNamespace(),
        monthly_pass=SimpleNamespace(monthly_pass_check=lambda: None),
        retry_cnt_max=2,
        now=datetime.now(),
    )
    instance.root = isolated_cwd
    return instance


def basic_map_payload(start, name="1-1 空间站「黑塔」"):
    return {"name": name, "author": "tester", "start": start, "map": []}


class TestDispatchContract:
    """分发表调用的 Handle 方法必须真的存在。

    这里踩过一次：`HANDLE_METHODS` 白名单是从分发表反向推导出来的，
    于是它**记录**了 `mouse_move` / `handle_shutdown` 两个名字，却没有检查
    `Handle` 是否提供它们 —— 名字是照着调用点抄的，调用点什么它就抄什么。
    白名单只能保证「替身愿意响应」，不能保证「真身确实有」。

    这条测试补上真身那一半。用 AST 而不是正则提取，避免把注释掉的调用算进来。
    """

    @staticmethod
    def _self_attr_chain(func):
        """把 `a.b.c(...)` 拆成 ("a", "b", "c")，不是这种形状就返回 None。"""
        parts = []
        node = func
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name) and node.id == "self":
            return tuple(reversed(parts))
        return None

    @classmethod
    def dispatched_names(cls, prefix=("handle",)):
        """map_operations 里真正会执行的 `self.<prefix>.X(...)` 调用名。"""
        source = Path(operations_module.__file__).read_text(encoding="utf-8")
        names = set()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            chain = cls._self_attr_chain(node.func)
            if chain and chain[:-1] == prefix:
                names.add(chain[-1])
        return names

    def test_whitelist_matches_what_dispatch_actually_calls(self):
        """白名单与分发表不能各说各话。"""
        called = self.dispatched_names()
        assert called <= HANDLE_METHODS, (
            f"分发表调用了白名单外的 Handle 方法：{sorted(called - HANDLE_METHODS)}"
        )
        assert HANDLE_METHODS <= called | {"handle_shutdown", "mouse_move"}, (
            f"白名单里有分发表从不调用的名字：{sorted(HANDLE_METHODS - called)}"
        )

    def test_dispatched_combat_methods_exist(self):
        """`self.handle.combat.X(...)` 也要真实存在。"""
        from utils.flows.combat import Combat

        missing = sorted(
            n for n in self.dispatched_names(("handle", "combat")) if not hasattr(Combat, n)
        )
        assert missing == [], f"分发表调用了不存在的 Combat 方法：{missing}"

    @pytest.mark.xfail(
        strict=True,
        reason="分发表调用了 Handle 上不存在的方法：mouse_move / handle_shutdown。"
        "mouse_move 是 record.py 录制视角移动时会写出的步骤（见其 save_json），"
        "handle_shutdown 则在 README 里被列为合法步骤 —— 两者都会 AttributeError",
    )
    def test_every_dispatched_handle_method_exists(self):
        from utils.flows.handle import Handle

        missing = sorted(n for n in self.dispatched_names() if not hasattr(Handle, n))
        assert missing == [], f"分发表调用了不存在的 Handle 方法：{missing}"


class TestShowDevInfo:
    def test_noop_outside_dev_mode(self, make_instance, monkeypatch):
        shown = []
        monkeypatch.setattr(
            operations_module, "show_text", lambda *args: shown.append(args)
        )
        instance = make_instance(MapOperations, window=SimpleNamespace())

        instance.show_dev_info(False, "text", 180, 1045, "map_name")

        assert shown == []

    def test_offsets_text_by_window_origin(
        self, make_instance, fake_window_factory, monkeypatch
    ):
        shown = []
        monkeypatch.setattr(
            operations_module, "show_text", lambda *args: shown.append(args)
        )
        instance = make_instance(
            MapOperations, window=fake_window_factory(rect=(100, 200, 2020, 1280))
        )

        instance.show_dev_info(True, "hello", 180, 1045, "map_name")

        assert shown == [("hello", 280, 1245, "nouid", "map_name")]


class TestProcessSingleMapStart:
    def test_forbidden_map_sets_skip_flag(self, operations):
        write_map(operations.root, "default", "map_1-1_0.json", basic_map_payload([]))
        operations.map = SimpleNamespace(
            check_allowlist_maps=lambda name: False,
            check_forbidden_maps=lambda name: True,
            planet_png_lst=[],
        )

        operations.process_single_map_start(0, "map_1-1_0.json")

        assert operations.map_statu.skip_this_map is True

    def test_allowlist_exclusion_sets_skip_flag(self, operations):
        write_map(operations.root, "default", "map_1-1_0.json", basic_map_payload([]))
        operations.map = SimpleNamespace(
            check_allowlist_maps=lambda name: True,
            check_forbidden_maps=lambda name: False,
            planet_png_lst=[],
        )

        operations.process_single_map_start(0, "map_1-1_0.json")

        assert operations.map_statu.skip_this_map is True

    def test_check_key_skips_map_on_the_wrong_weekday(self, operations):
        """start 里的 {"check": []} 表示今天不在购买日，应跳过整张图。"""
        write_map(
            operations.root,
            "default",
            "map_1-1_0.json",
            basic_map_payload([{"check": []}]),
        )

        operations.process_single_map_start(0, "map_1-1_0.json")

        assert operations.map_statu.skip_this_map is True

    def test_check_key_continues_on_matching_weekday(self, operations):
        today = datetime.now().weekday()
        write_map(
            operations.root,
            "default",
            "map_1-1_0.json",
            basic_map_payload([{"check": [today]}, {"await": 0.1}]),
        )
        awaited = []
        operations.handle = SimpleNamespace(
            f_key_error=False, handle_await=lambda value: awaited.append(value)
        )
        operations.map = SimpleNamespace(
            check_allowlist_maps=lambda name: False,
            check_forbidden_maps=lambda name: False,
            planet_png_lst=[],
            allow_map_drag=lambda start: None,
            allow_scene_drag=lambda start: None,
            allow_multi_click=lambda start: None,
            allow_retry_in_map=lambda start: None,
            allow_click_offset=lambda start: None,
        )

        operations.process_single_map_start(0, "map_1-1_0.json")

        assert operations.map_statu.skip_this_map is False
        assert awaited == [0.1]

    def test_need_allow_map_buy_skips_when_disabled(self, operations):
        write_map(
            operations.root,
            "default",
            "map_1-1_0.json",
            basic_map_payload([{"need_allow_map_buy": 1}]),
        )
        operations.map = SimpleNamespace(
            check_allowlist_maps=lambda name: False,
            check_forbidden_maps=lambda name: False,
            planet_png_lst=[],
            allow_map_drag=lambda start: None,
            allow_scene_drag=lambda start: None,
            allow_multi_click=lambda start: None,
            allow_retry_in_map=lambda start: None,
            allow_click_offset=lambda start: None,
        )

        operations.process_single_map_start(0, "map_1-1_0.json")

        assert operations.map_statu.skip_this_map is True

    def test_f_key_error_is_reset_at_map_start(self, operations):
        write_map(operations.root, "default", "map_1-1_0.json", basic_map_payload([]))
        operations.handle = SimpleNamespace(f_key_error=True)

        operations.process_single_map_start(0, "map_1-1_0.json")

        assert operations.handle.f_key_error is False


class TestRetryFlagPlumbing:
    """重试标志的跨模块传递。

    历史：这个标志曾经是 `Img` 的实例属性，而 `Img` 不是单例 ——
    `mouse_event` 写在自己的实例上，`map_operations` 读另一个实例，永远读到 False，
    于是 `retry_in_map` 的重试分支从不触发，**而且不报任何错**。
    现在标志归 `MouseEvent`（单例）所有，读取方本来就持有它的引用。
    """

    def test_img_is_a_singleton(self, monkeypatch, fake_window_factory):
        monkeypatch.setattr(
            "utils.drivers.screen.Window", lambda *args, **kwargs: fake_window_factory()
        )
        assert Img() is Img(), "7 处 Img() 应共用同一实例"

    def test_flag_no_longer_lives_on_img(self, monkeypatch, fake_window_factory):
        """钉住这次的教训：不要把跨模块状态放到 Img 上。"""
        monkeypatch.setattr(
            "utils.drivers.screen.Window", lambda *args, **kwargs: fake_window_factory()
        )
        assert not hasattr(Img(), "search_img_allow_retry")

    @pytest.fixture
    def retry_run(self, operations, monkeypatch):
        """驱动一次会走到重试判定的 start 步骤。"""
        monkeypatch.setattr(operations_module.time, "sleep", lambda seconds: None)

        def _run(click_times_out: bool, retry_in_map: bool = True):
            write_map(
                operations.root,
                "default",
                "map_1-1_0.json",
                {
                    "name": "1-1 空间站「黑塔」",
                    "author": "tester",
                    "start": [{"picture\\some_point.png": 1}],
                    "map": [],
                },
            )
            # 地图数据里的 forbid_retry 决定要不要重试；map_operations 会把它
            # 作为 retry_in_map 传给 click_target。
            game_map = MapStub()
            game_map.allow_retry_in_map_switch = retry_in_map

            mouse = MouseRecorder(result=not click_times_out)
            img = ImgRecorder(result=not click_times_out)

            def click_target(*args, **kwargs):
                img.calls.append(("click_target", args, kwargs))
                if click_times_out:
                    # 复刻 matcher.click_target 超时分支的写标志行为
                    mouse.last_search_allow_retry = kwargs.get("retry_in_map", True)
                return not click_times_out

            img.click_target = click_target
            operations.handle = RecordingHandle()
            operations.map = game_map
            operations.calculated = CalculatedRecorder()
            operations.mouse_event = mouse
            operations.img = img
            operations.process_single_map_start(0, "map_1-1_0.json")
            return operations.map_statu

        return _run

    def test_click_timeout_skips_map_after_max_retries(self, retry_run):
        """点击一直超时且允许重试时，重试到上限后应跳过本图并标记下一图拖动。"""
        statu = retry_run(click_times_out=True, retry_in_map=True)

        assert statu.skip_this_map is True
        assert statu.next_map_drag is True, "重试耗尽后应改为拖动地图再试"

    def test_successful_click_does_not_skip(self, retry_run):
        statu = retry_run(click_times_out=False)

        assert statu.skip_this_map is False
        assert statu.next_map_drag is False

    def test_forbidden_retry_does_not_skip_the_map(self, retry_run):
        """地图数据声明 forbid_retry 时，超时不触发重试，也不跳过本图。"""
        statu = retry_run(click_times_out=True, retry_in_map=False)

        assert statu.skip_this_map is False

    def test_flag_is_reset_before_each_start_step(self, operations, monkeypatch):
        """上一张图遗留的标志不能影响下一个 start 步骤。"""
        monkeypatch.setattr(operations_module.time, "sleep", lambda seconds: None)
        write_map(
            operations.root,
            "default",
            "map_1-1_0.json",
            {
                "name": "1-1 空间站「黑塔」",
                "author": "tester",
                "start": [{"await": 0.1}],
                "map": [],
            },
        )
        mouse = MouseRecorder()
        mouse.last_search_allow_retry = True  # 模拟上一轮遗留
        operations.handle = RecordingHandle()
        operations.map = MapStub()
        operations.calculated = CalculatedRecorder()
        operations.mouse_event = mouse
        operations.img = ImgRecorder()
        operations.process_single_map_start(0, "map_1-1_0.json")

        assert mouse.last_search_allow_retry is False



class TestProcessMap:
    """process_map 自己构造 Pause —— 真实那只会注册全局热键，所以这里一律替掉。"""

    @pytest.fixture(autouse=True)
    def stub_pause(self, monkeypatch):
        monkeypatch.setattr(operations_module, "Pause", lambda dev=False: PauseStub())

    def test_unknown_start_map_is_reported(self, operations, log_records):
        operations.map_info = SimpleNamespace(map_version="default", map_list=[])

        operations.process_map("9-9_9")

        assert any("不存在" in r["message"] for r in log_records)

    def test_single_map_runs_only_the_requested_file(self, operations, log_records):
        processed = []
        operations.map_info = SimpleNamespace(
            map_version="default", map_list=["map_1-1_0.json", "map_2-1_0.json"]
        )
        operations.map = SimpleNamespace(
            align_angle=lambda: None,
            reset_round_count=lambda: None,
            get_map_list=lambda start, start_in_mid: ["map_1-1_0.json", "map_2-1_0.json"],
        )
        operations.handle = SimpleNamespace(
            combat=SimpleNamespace(total_fight_time=0)
        )
        operations.process_single_map = lambda index, name, dev: processed.append(name)
        operations.report = SimpleNamespace(output_report=lambda: None)

        operations.process_map("1-1_0", single_map=True)

        assert processed == ["map_1-1_0.json"]

    def test_map_gets_the_pause_gate(self, operations):
        """跑图前把闸门接到 Map 上 —— flows/map.py 的循环才能停（那里不 import ui/）。"""
        operations.map_info = SimpleNamespace(map_version="default", map_list=[])

        operations.process_map("9-9_9")

        assert callable(operations.map.pause_gate)
        assert operations.map.pause_gate() == 0.0


class CalculatedRecorder:
    """Calculated 的替身，记录加载检测与购买检测的调用。"""

    def __init__(self, allow_buy=True):
        self.calls = []
        self.allow_buy = allow_buy

    def run_mapload_check(self, *args, **kwargs):
        self.calls.append("run_mapload_check")

    def allow_buy_item(self):
        self.calls.append("allow_buy_item")
        return self.allow_buy

    def first_role_check(self, *args, **kwargs):
        self.calls.append("first_role_check")


class MouseRecorder:
    """MouseEvent 的替身：只记录输入侧动作。

    「找到图就点它」一族（click_target / click_target_above_threshold）
    2026-09 搬到了 vision 层，替身在 ImgRecorder 那边。
    """

    def __init__(self, result=True):
        self.calls = []
        self.result = result
        # click_target 超时时由 vision/matcher 写入，由 map_operations 读取
        self.last_search_allow_retry = False

    def click_target_with_alt(self, matcher, *args, **kwargs):
        self.calls.append(("click_target_with_alt", args, kwargs))
        return self.result


class ImgRecorder:
    """Img 门面的替身：识图与点击都在这一侧。"""

    def __init__(self, result=True):
        self.calls = []
        self.result = result

    def click_target(self, *args, **kwargs):
        self.calls.append(("click_target", args, kwargs))
        return self.result

    def on_main_interface(self, **kwargs):
        return False


class TestStartStepDispatch:
    """process_single_map_start 里 start 条目的键值分发表。"""

    @pytest.fixture
    def run(self, operations, monkeypatch):
        pressed = []
        monkeypatch.setattr(operations_module, "KeyboardEvent", SimpleNamespace(keyboard_press=lambda key, delay=0: pressed.append(key)))

        def _run(entry, planet_png_lst=(), allow_buy=True, click_ok=True):
            pressed.clear()
            # start 是一个「单键字典」的列表：每个元素只取第一个键，
            # 所以多步场景必须传列表，不能把多个键塞进同一个 dict。
            start = [entry] if isinstance(entry, dict) else list(entry)
            write_map(
                operations.root,
                "default",
                "map_1-1_0.json",
                {
                    "name": "1-1 空间站「黑塔」",
                    "author": "tester",
                    "start": start,
                    "map": [],
                },
            )
            handle = RecordingHandle()
            game_map = MapStub(planet_png_lst=planet_png_lst)
            calculated = CalculatedRecorder(allow_buy=allow_buy)
            mouse = MouseRecorder(result=click_ok)
            img = ImgRecorder(result=click_ok)
            operations.handle = handle
            operations.map = game_map
            operations.calculated = calculated
            operations.mouse_event = mouse
            operations.img = img
            # 检查点返回非 F7 的键时会切窗口（见 _pause_checkpoint）
            operations.window = SimpleNamespace(switch_window=lambda: None)
            operations.process_single_map_start(0, "map_1-1_0.json")
            return SimpleNamespace(
                handle=handle,
                map=game_map,
                calculated=calculated,
                mouse=mouse,
                img=img,
                pressed=list(pressed),
                statu=operations.map_statu,
            )

        return _run

    @pytest.mark.parametrize(
        "entry,method,args",
        [
            ({"space": 0.5}, "handle_space", (0.5, "space")),
            ({"f": 15}, "handle_f", (15,)),
            ({"w": 1.5}, "handle_move", (1.5, "w")),
            ({"a": 2.5}, "handle_move", (2.5, "a")),
            ({"s": 0.4}, "handle_move", (0.4, "s")),
            ({"d": 3.0}, "handle_move", (3.0, "d")),
            ({"await": 2}, "handle_await", (2,)),
            ({"b": 1}, "handle_b", ()),
            ({"main": 1}, "back_to_main", ()),
        ],
    )
    def test_key_routes_to_handle_method(self, run, entry, method, args):
        result = run(entry)
        assert result.handle.called(method)[0][1] == args

    @pytest.mark.parametrize("key", ["esc", "F4"])
    def test_keys_are_pressed_directly(self, run, key):
        assert run({key: 1}).pressed == [key]

    def test_map_key_opens_the_map(self, run):
        assert len(run({"map": 1}).map.called("open_map")) == 1

    def test_blackscreen_key_runs_the_loading_check(self, run):
        assert run({"blackscreen": 1}).calculated.calls == ["run_mapload_check"]

    def test_normal_run_key_switches_off_sprinting(self, run):
        assert run({"normal_run": 1}).statu.normal_run is True

    def test_check_key_matching_today_continues(self, run):
        today = datetime.now().weekday()
        result = run([{"check": [today]}, {"await": 1}])
        assert result.statu.skip_this_map is False
        assert result.handle.called("handle_await")

    def test_check_key_not_matching_today_skips_the_map(self, run):
        tomorrow = (datetime.now().weekday() + 1) % 7
        result = run([{"check": [tomorrow]}, {"await": 1}])
        assert result.statu.skip_this_map is True
        assert result.handle.called("handle_await") == []

    def test_need_allow_map_buy_skips_when_disabled(self, run):
        assert run({"need_allow_map_buy": 1}).statu.skip_this_map is True

    def test_need_allow_map_buy_continues_when_enabled(self, run, operations):
        # 这一支读的是磁盘上的 config.json，不是内存缓存
        set_config_on_disk(operations.root, allow_map_buy=True)
        assert run({"need_allow_map_buy": 1}).statu.skip_this_map is False

    def test_need_allow_snack_buy_skips_when_disabled(self, run):
        assert run({"need_allow_snack_buy": 1}).statu.skip_this_map is True

    def test_need_allow_memory_token_skips_when_disabled(self, run):
        assert run({"need_allow_memory_token": 1}).statu.skip_this_map is True

    def test_max_picture_buys_item_and_continues(self, run):
        result = run({"picture\\max.png": 1})
        assert result.calculated.calls == ["allow_buy_item"]
        assert result.statu.skip_this_map is False
        assert result.img.calls[0][0] == "click_target"

    def test_max_picture_skips_map_when_cannot_buy(self, run):
        result = run({"picture\\max.png": 1}, allow_buy=False)
        assert result.statu.skip_this_map is True
        assert result.img.calls == []

    def test_transfer_picture_runs_loading_check_after_click(self, run):
        result = run({"picture\\transfer.png": 1})
        assert result.img.calls[0][0] == "click_target"
        assert result.calculated.calls == ["run_mapload_check"]

    def test_transfer_picture_skips_map_when_click_fails(self, run):
        result = run({"picture\\transfer.png": 1}, click_ok=False)
        assert result.statu.skip_this_map is True
        assert result.calculated.calls == []

    def test_floor_entry_clicks_the_matching_index(self, run):
        result = run({"floor": [[10, 20, 30], 20]})
        assert result.handle.called("handle_click_floor")[0][1] == (1,)

    def test_floor_entry_with_unknown_target_is_swallowed(self, run, log_records):
        run({"floor": [[10, 20], 999]})
        assert any("floor处理异常" in r["message"] for r in log_records)

    def test_floor_picture_routes_to_map_handler(self, run):
        assert len(run({"picture\\1floor.png": 1}).map.called("handle_floor")) == 1

    def test_back_picture_routes_to_handle_back(self, run):
        assert len(run({"picture\\fanhui_1.png": 1}).map.called("handle_back")) == 1

    def test_orientation_picture_routes_to_orientation_handler(self, run):
        assert len(run({"picture\\orientation_1.png": 1}).map.called("handle_orientation")) == 1

    def test_planet_picture_routes_to_planet_handler(self, run):
        key = "picture\\orientation_2.png"
        result = run({key: 1}, planet_png_lst=[key])
        assert result.map.called("handle_planet")[0][1] == (key,)

    def test_unknown_point_clicks_without_dragging_by_default(self, run):
        result = run({"picture\\unknown_point.png": 1})
        assert result.map.called("find_transfer_point") == []
        assert result.map.called("find_scene") == []
        assert result.img.calls[0][0] == "click_target"
        assert result.statu.temp_point == "picture\\unknown_point.png"

    def test_unknown_point_drags_when_previous_map_requested_it(self, run, operations):
        operations.map_statu.next_map_drag = True
        result = run({"picture\\unknown_point.png": 1})
        assert len(result.map.called("find_transfer_point")) == 1

    def test_dream_machine_check_failure_is_recorded(self, run):
        result = run({"picture\\check_4-1_point.png": 1}, click_ok=False)
        assert result.statu.error_check_point is True

    def test_dream_machine_check_success_is_not_recorded(self, run):
        result = run({"picture\\check_4-1_point.png": 1}, click_ok=True)
        assert result.statu.error_check_point is False

    def test_teleport_click_counter_increments(self, run):
        assert run({"picture\\unknown_point.png": 1}).statu.teleport_click_count == 1

    def test_pause_checkpoints_cover_the_whole_start_phase(self, run, operations):
        """start 阶段以前一次检查都没有，按 F8 会被静默丢弃。

        （那时 Pause 还建在 handle 阶段：第一张图根本没注册热键，之后的图按下的
        F8 又被下一张图新建的 Pause 把事件对象换掉了。）
        """
        run([{"w": 1.0}, {"w": 1.0}])

        # 重试循环 1 次 + start 每一步 1 次
        assert operations.pause.checks == 3

    def test_f9_in_the_start_phase_reruns_the_map(self, run, operations):
        """F9 的重跑意图要在 start 阶段生效，而不是被吞掉。"""
        operations.pause = PauseStub("F9")

        result = run({"w": 1.5})

        assert result.calculated.calls == ["run_mapload_check"], (
            "F9 应触发「重新传送至地图」的加载检查"
        )


class TestHandleStepDispatch:
    """process_single_map_handle 里 map 条目的键值分发表。"""

    @pytest.fixture
    def run(self, operations):
        def _run(entry):
            write_map(
                operations.root,
                "default",
                "map_1-1_0.json",
                {
                    "name": "1-1 空间站「黑塔」",
                    "author": "tester",
                    "start": [],
                    "map": [entry],
                },
            )
            handle = RecordingHandle()
            operations.handle = handle
            operations.calculated = CalculatedRecorder()
            operations.monthly_pass = SimpleNamespace(
                monthly_pass_check=lambda: None
            )
            operations.window = SimpleNamespace(switch_window=lambda: None)
            operations.process_single_map_handle("map_1-1_0.json", normal_run=False)
            return SimpleNamespace(handle=handle, statu=operations.map_statu)

        return _run

    @pytest.mark.parametrize(
        "entry,method,args",
        [
            ({"space": 0.5}, "handle_space", (0.5, "space")),
            ({"caps": 0.5}, "handle_caps", (0.5,)),
            ({"r": 0.5}, "handle_r", (0.5, "r")),
            ({"f": 15}, "handle_f", (15,)),
            ({"allow_skip_f": 15}, "handle_allow_skip_f", (15,)),
            ({"mouse_move": 30}, "mouse_move", (30,)),
            ({"fighting": 1}, "handle_fighting", (1,)),
            ({"scroll": -3}, "scroll", (-3,)),
            ({"shutdown": 1}, "handle_shutdown", ()),
            ({"e": 1}, "handle_e", (1,)),
            ({"esc": 1}, "handle_esc", (1,)),
            ({"1": 0.5}, "handle_num", (0.5, "1")),
            ({"main": 1}, "handle_main", (1,)),
            ({"view_set": 0.1}, "handle_view_set", (0.1,)),
            ({"view_reset": 0.1}, "handle_view_reset", (0.1,)),
            ({"view_rotate": 90}, "handle_view_rotate", (90,)),
            ({"await": 2}, "handle_await", (2,)),
            ({"w": 1.5}, "handle_move", (1.5, "w", False, "")),
        ],
    )
    def test_key_routes_to_handle_method(self, run, entry, method, args):
        assert run(entry).handle.called(method)[0][1] == args

    def test_unknown_key_falls_through_to_handle_move(self, run):
        result = run({"some_unknown_key": 1.2})
        assert result.handle.called("handle_move")[0][1] == (
            1.2,
            "some_unknown_key",
            False,
            "",
        )

    def test_check_key_uses_the_recording_date(self, run, operations):
        result = run({"check": [0, 1, 2, 3, 4, 5, 6]})
        name, args = result.handle.called("handle_check")[0]
        assert args[0] == [0, 1, 2, 3, 4, 5, 6]
        assert args[1] == operations.now.strftime("%A")

    def test_fighting_count_is_precomputed(self, run):
        result = run({"fighting": 1})
        assert result.handle.combat.fighting_count == 1

    def test_multi_entry_map_runs_every_step(self, operations):
        write_map(
            operations.root,
            "default",
            "map_1-1_0.json",
            {
                "name": "1-1 空间站「黑塔」",
                "author": "tester",
                "start": [],
                "map": [{"w": 1.0}, {"await": 2.0}, {"d": 3.0}],
            },
        )
        handle = RecordingHandle()
        operations.handle = handle
        operations.calculated = CalculatedRecorder()
        operations.monthly_pass = SimpleNamespace(monthly_pass_check=lambda: None)

        operations.process_single_map_handle("map_1-1_0.json", normal_run=False)

        assert [call[0] for call in handle.calls] == [
            "handle_view_set",  # 进图前先校准视角
            "handle_move",
            "handle_await",
            "handle_move",
        ]

    def test_f_key_error_breaks_out_and_is_recorded(self, operations):
        write_map(
            operations.root,
            "default",
            "map_1-1_0.json",
            {
                "name": "1-1 空间站「黑塔」",
                "author": "tester",
                "start": [],
                "map": [{"f": 15}, {"await": 2.0}],
            },
        )
        handle = RecordingHandle()

        def fail_f(value):
            handle.calls.append(("handle_f", (value,)))
            handle.f_key_error = True

        handle.handle_f = fail_f
        operations.handle = handle
        operations.calculated = CalculatedRecorder()
        operations.monthly_pass = SimpleNamespace(monthly_pass_check=lambda: None)

        operations.process_single_map_handle("map_1-1_0.json", normal_run=False)

        assert operations.map_statu.map_f_key_error == ["1-1 空间站「黑塔」"]
        assert not handle.called("handle_await"), "F 键出错后应中断这张地图剩余步骤"

    def test_dev_restart_on_f9_switches_window(self, operations):
        # 只在第一次检查时返回 F9：否则 while dev_restart 会永远转下去
        operations.pause = PauseStub("F9")
        write_map(
            operations.root,
            "default",
            "map_1-1_0.json",
            {
                "name": "1-1 空间站「黑塔」",
                "author": "tester",
                "start": [],
                "map": [{"await": 1.0}],
            },
        )
        switched = []
        img = ImgRecorder()
        operations.handle = RecordingHandle()
        operations.calculated = CalculatedRecorder()
        operations.monthly_pass = SimpleNamespace(monthly_pass_check=lambda: None)
        operations.window = SimpleNamespace(
            switch_window=lambda: switched.append(1), get_rect=lambda: (0, 0, 1920, 1080)
        )
        operations.img = img

        operations.process_single_map_handle("map_1-1_0.json", normal_run=False, dev=True)

        assert switched == [1]
        assert img.calls[0][0] == "click_target"


