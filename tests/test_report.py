"""utils/flows/report.py —— 阶段结束报告的字段输出。"""

from types import SimpleNamespace

from utils.core.map_statu import MapStatu
from utils.flows.report import Report
from utils.core.time_utils import TimeUtils


def build_report(map_version="default", **statu_overrides):
    statu = MapStatu()
    for name, value in statu_overrides.items():
        setattr(statu, name, value)
    combat = SimpleNamespace(
        total_fight_cnt=5,
        total_no_fight_cnt=7,
        snack_used=2,
        error_fight_threshold=3,
        error_fight_cnt=1,
    )
    movement = SimpleNamespace(tatol_save_time=12.5, time_error_cnt=4)
    handle = SimpleNamespace(movement=movement, combat=combat)
    mouse_event = SimpleNamespace(img_search_val_dict={"./picture/a.png": 0.42})
    map_info = SimpleNamespace(map_version=map_version)
    time_mgr = SimpleNamespace(format_time=TimeUtils.format_time)
    return Report(statu, map_info, handle, mouse_event, time_mgr)


def messages(log_records):
    return "\n".join(r["message"] for r in log_records)


class TestOutputReport:
    def test_reports_totals(self, log_records):
        report = build_report(
            total_time=125.0, total_fight_time=30.0
        )

        report.output_report()

        text = messages(log_records)
        assert "2分5.0秒" in text
        assert "30.0秒" in text

    def test_reports_saved_time(self, log_records):
        build_report().output_report()
        assert "12.5秒" in messages(log_records)

    def test_reports_fight_counts(self, log_records):
        build_report().output_report()
        text = messages(log_records)
        assert "战斗次数：5" in text
        assert "未战斗次数：7" in text
        assert "奇巧零食使用次数：2" in text
        assert "系统卡顿次数：4" in text

    def test_reports_map_names(self, log_records):
        report = build_report(
            start_map_name="1-1_0", end_map_name="2-3_1"
        )
        report.output_report()
        text = messages(log_records)
        assert "开始地图：1-1_0" in text
        assert "结束地图：2-3_1" in text

    def test_error_threshold_is_included(self, log_records):
        build_report().output_report()
        assert "战斗时间 < 3 秒" in messages(log_records)

    def test_dream_machine_failure_is_reported(self, log_records):
        report = build_report(error_check_point=True)
        report.output_report()
        assert "筑梦机关检查不通过" in messages(log_records)

    def test_dream_machine_ok_is_not_reported(self, log_records):
        build_report(error_check_point=False).output_report()
        assert "筑梦机关检查不通过" not in messages(log_records)

    def test_f_key_errors_are_listed(self, log_records):
        report = build_report(map_f_key_error=["1-1_0", "2-1_3"])
        report.output_report()
        assert "1-1_0" in messages(log_records)

    def test_huangquan_section_only_for_that_version(self, log_records):
        build_report(
            map_version="HuangQuan",
            fight_in_map_list=["1-1_0(3/40)"],
        ).output_report()
        assert "黄泉模式，异常进入战斗" in messages(log_records)

    def test_other_versions_skip_huangquan_section(self, log_records):
        build_report(map_version="default").output_report()
        assert "黄泉模式" not in messages(log_records)

    def test_low_match_images_are_logged_at_debug(self, log_records):
        build_report().output_report()
        assert any(
            "匹配值小于0.99的图片" in r["message"] and r["level"].name == "DEBUG"
            for r in log_records
        )


class TestMapStatuDefaults:
    def test_fresh_state_is_empty(self):
        statu = MapStatu()
        assert statu.map_f_key_error == []
        assert statu.fight_in_map_list == []
        assert statu.skip_this_map is False
        assert statu.total_fight_time == 0

    def test_instance_lists_are_not_shared(self):
        first = MapStatu()
        first.map_f_key_error.append("x")
        assert MapStatu().map_f_key_error == []
