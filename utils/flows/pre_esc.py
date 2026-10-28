"""按 ESC 之前统一处理「ESC 关不掉的界面」。

`Handle.back_to_main` 的主循环只做三件事：判断是否主界面、把**同一帧**交给
这张表修、没修好才按 ESC。所有「ESC 处理不了、必须先点掉」的界面都登记在
这里 —— 新增一种只加一条表项，不再往 `back_to_main` 里塞 `if`。

每个修复分两段：

- `detect(frame)`：纯识别，返回动作参数（点、匹配结果……）或 None；
  不截图、不点击，可以直接用黄金图测。
- `apply(action, left, top)`：真正执行。可能是多步（点击 → 等动画 → 确认）。
  `left/top` 是这一帧对应的窗口原点，动作里的坐标都按**帧内坐标**记。

`once=True` 表示「每次 `back_to_main` 只试一次」——不管命中与否。月卡界面用
这条：识别错时不能每个循环都去点，否则 120 秒里会反复点同一处。
"""

from typing import Any, Callable, NamedTuple

from utils.flows import puzzle_exit


class PreEscFix(NamedTuple):
    """一条「按 ESC 前先修」的界面。"""

    name: str
    detect: Callable[[Any], Any]
    apply: Callable[[Any, int, int], None]
    once: bool = False


class PreEscFixer:
    """一次 `back_to_main` 调用里的修复表；`once` 状态随实例走。"""

    def __init__(self, img, mouse, monthly_pass):
        self.img = img
        self.mouse = mouse
        self.monthly_pass = monthly_pass
        self._tried = set()

        # 顺序就是优先级：越具体、误点代价越大的越靠前。
        self.fixes = (
            PreEscFix(
                "puzzle_exit",
                puzzle_exit.detect,
                lambda point, left, top: puzzle_exit.click(
                    point, self.mouse, left, top
                ),
            ),
            PreEscFix(
                "monthly_pass",
                self.monthly_pass.match_frame,
                self._apply_monthly,
                once=True,
            ),
        )

    def _apply_monthly(self, action, left, top):
        pic_data, result, pic_desc = action
        self.monthly_pass.claim_match(pic_data, result, pic_desc, left, top)

    def try_fix(self, frame, left, top):
        """用这一帧依次尝试修复；处理了返回 True，全都没命中返回 False。"""
        for fix in self.fixes:
            if fix.once:
                if fix.name in self._tried:
                    continue
                # 先记「已尝试」：没命中也不在本次调用里重复试（与旧行为一致）
                self._tried.add(fix.name)
            action = fix.detect(frame)
            if action is None:
                continue
            fix.apply(action, left, top)
            return True
        return False
