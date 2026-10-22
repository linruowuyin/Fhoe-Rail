# Puzzle-abandon dialog fixture

`dialog.png` is a 1000x400 crop at (460, 350) of a real Chinese 1920x1080
Star Rail frame captured on 2026-10-02. It contains the “是否放弃游玩？”
confirmation from 雅努斯密径. The crop excludes the UID and desktop overlays.
The runtime templates in `picture/puzzle_exit_*.png` come from this frame.

Probe results using `TM_CCOEFF_NORMED` in the production search regions:

| Sample | Prompt | Confirm button |
| --- | ---: | ---: |
| Captured dialog | 1.000 | 1.000 |
| Same dialog with prompt erased | 0.243 | 1.000 |
| Same dialog with confirm erased | 1.000 | 0.447 |
| Puzzle screen before opening the dialog | 0.147 | 0.265 |

Both thresholds are 0.90. The two erased negatives and the wrong-side button
case are generated from the captured dialog in `tests/test_puzzle_exit.py`.
They are synthetic lookalikes, not additional independent game captures.
Other languages and resolutions are not covered by this fixture.
