"""utils/flows/roles/first_role.py —— 1 号位角色识别与版本强制校验。

钉住：识别框 20×30 @ (1790,310) 外扩 2px、两张模板共用一帧、阈值严格大于、
黄泉 / 银狼 LV.999 版本角色不符时抛 CustomException、其它版本不校验。
"""

import numpy as np
import pytest

from utils.core.exceptions import CustomException
from utils.core.thresholds import FIRST_ROLE_ICON
from utils.flows.roles import first_role as module
from utils.vision import images as image_library
from utils.vision.matcher import Matcher


class RealImg:
    """把一帧合成图喂给真实 `Matcher` 的 Img 替身（模板走真实加载）。"""

    def __init__(self, frame, left=1788, top=308):
        self.frame = frame
        self.left = left
        self.top = top

    def get_img(self, path):
        return image_library.get_img(path)

    def take_screenshot(self, offset=(0, 0, 0, 0)):
        height, width = self.frame.shape[:2]
        return (self.frame, self.left, self.top, self.left + width, self.top + height)

    def match_screenshot(self, screenshot, prepared, left, top):
        return Matcher.match_screenshot(screenshot, prepared, left, top)


class FakeImg:
    """Img 门面的替身：按路径给模板，按模板对象给匹配度。"""

    def __init__(self, acheron=1.0, lv999=0.0, missing=()):
        self.templates = {}
        self.score_by_id = {}
        for index, (role, icon) in enumerate(module.ROLE_ICONS.items()):
            if role in missing:
                self.templates[icon.path] = None
                continue
            template = np.full((30, 20, 3), index + 1, dtype=np.uint8)
            self.templates[icon.path] = template
            self.score_by_id[id(template)] = (
                acheron if role == module.ROLE_ACHERON else lv999
            )
        self.screenshot_count = 0
        self.offsets = []

    def get_img(self, path):
        return self.templates.get(path)

    def take_screenshot(self, offset=(0, 0, 0, 0)):
        self.screenshot_count += 1
        self.offsets.append(offset)
        return (np.zeros((34, 24, 3), dtype=np.uint8), 1788, 308, 1812, 342)

    def match_screenshot(self, screenshot, prepared, left, top):
        return {"max_val": self.score_by_id[id(prepared)]}


class TestRoleIconOffset:
    def test_20x30_at_1790_310_with_2px_padding(self):
        # 框 (1790,310,1810,340) → 外扩 (1788,308,1812,342) → 四边增量
        assert module.role_icon_offset() == (1788, 308, -108, -738)

    def test_padding_is_configurable(self):
        assert module.role_icon_offset(pad=0) == (1790, 310, -110, -740)

    def test_template_overflowing_the_screen_raises(self):
        with pytest.raises(CustomException):
            module.role_icon_offset((20, 30), position=(1910, 1070))


class TestRecognizeFirstRole:
    def test_picks_the_higher_score(self):
        detection = module.recognize_first_role(FakeImg(acheron=0.99, lv999=0.42))

        assert detection["role"] == module.ROLE_ACHERON
        assert detection["max_val"] == pytest.approx(0.99)
        assert detection["scores"] == {
            module.ROLE_ACHERON: pytest.approx(0.99),
            module.ROLE_SILVER_WOLF_LV999: pytest.approx(0.42),
        }

    def test_both_templates_share_one_screenshot(self):
        img = FakeImg(acheron=0.99, lv999=0.42)

        module.recognize_first_role(img)

        assert img.screenshot_count == 1, "同一识别框不能每张模板各抓一次屏（R10）"
        assert img.offsets == [module.role_icon_offset()]

    def test_threshold_is_strictly_greater(self):
        # 正好等于阈值不算匹配 —— 与全项目判定方向一致
        assert (
            module.recognize_first_role(
                FakeImg(acheron=FIRST_ROLE_ICON, lv999=0.5)
            )["role"]
            is None
        )

    def test_below_threshold_returns_no_role(self):
        assert (
            module.recognize_first_role(FakeImg(acheron=0.6, lv999=0.5))["role"]
            is None
        )

    def test_missing_template_raises_before_capture(self):
        img = FakeImg(missing=(module.ROLE_SILVER_WOLF_LV999,))

        with pytest.raises(CustomException):
            module.recognize_first_role(img)

        assert img.screenshot_count == 0

    def test_template_of_the_wrong_size_is_a_config_error(self):
        img = FakeImg()
        img.templates[module.ROLE_ICONS[module.ROLE_ACHERON].path] = np.zeros(
            (31, 20, 3), dtype=np.uint8
        )

        with pytest.raises(CustomException):
            module.recognize_first_role(img)

        assert img.screenshot_count == 0


class TestCheckFirstRole:
    def test_huangquan_passes_with_acheron(self):
        detection = module.check_first_role("HuangQuan", FakeImg(acheron=0.995))

        assert detection["role"] == module.ROLE_ACHERON

    def test_silver_wolf_passes_with_silver_wolf(self):
        detection = module.check_first_role(
            "SilverWolfLv999", FakeImg(acheron=0.3, lv999=0.995)
        )

        assert detection["role"] == module.ROLE_SILVER_WOLF_LV999

    def test_huangquan_rejects_another_known_role(self):
        with pytest.raises(CustomException) as raised:
            module.check_first_role("HuangQuan", FakeImg(acheron=0.4, lv999=0.99))

        message = str(raised.value)
        assert "黄泉" in message and "银狼 LV.999" in message

    def test_huangquan_rejects_unknown_role(self):
        with pytest.raises(CustomException) as raised:
            module.check_first_role("HuangQuan", FakeImg(acheron=0.5, lv999=0.5))

        assert "未识别出角色" in str(raised.value)

    def test_silver_wolf_rejects_acheron(self):
        with pytest.raises(CustomException):
            module.check_first_role(
                "SilverWolfLv999", FakeImg(acheron=0.99, lv999=0.2)
            )

    @pytest.mark.parametrize("version", ["default", "default_lite", "technique", ""])
    def test_other_versions_skip_the_check(self, version):
        img = FakeImg()

        assert module.check_first_role(version, img) is None
        assert img.screenshot_count == 0


class TestRealTemplates:
    """用仓库里的真实模板 + 真 cv2 匹配跑一遍（CLAUDE.md §1.5 的正/负样本）。

    合成帧只负责把模板摆进 24×34 的搜索区，验证「裁切尺寸 → 外扩 2px →
    通道序 → 阈值」这一整串能接上。实机 2026-10 量得：正样本 1.000（±2px
    抖动仍为 1.000），另一角色的模板同一位置只有约 0.893 —— 阈值 0.98 的
    两侧余量都够。
    """

    @staticmethod
    def frame_with(template, dx=0, dy=0):
        # 搜索区 = 20×30 模板 + 四周 2px，模板正好摆在 (2,2)
        frame = np.zeros((34, 24, 3), dtype=np.uint8)
        frame[2 + dy:2 + dy + 30, 2 + dx:2 + dx + 20] = template
        return frame

    @pytest.mark.parametrize("dx,dy", [(0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)])
    def test_real_templates_are_recognized_under_jitter(self, repo_root, dx, dy):
        for role, icon in module.ROLE_ICONS.items():
            template = image_library.get_img(icon.path)
            assert template is not None

            detection = module.recognize_first_role(
                RealImg(self.frame_with(template, dx, dy))
            )

            assert detection["role"] == role
            assert detection["scores"][role] == pytest.approx(1.0, abs=1e-6)

    def test_the_other_role_stays_below_the_threshold(self, repo_root):
        acheron = image_library.get_img(module.ROLE_ICONS[module.ROLE_ACHERON].path)

        detection = module.recognize_first_role(RealImg(self.frame_with(acheron)))

        assert detection["role"] == module.ROLE_ACHERON
        assert detection["scores"][module.ROLE_SILVER_WOLF_LV999] < FIRST_ROLE_ICON

