"""波次刷怪（L2 驱动线负责，见 CONTRACT §4.4 / D8）。

实现要点：
- 每个 group 有自己的 delay 与 interval，本波所有 group 并行计时。
- 刷完一组再刷下一组不等前一组，按 wave.json 的 delay 相对本波开始计时。
- 最后一波刷完且场上无敌人后由 loop.is_over 判 WIN，不在这里判。
"""

from __future__ import annotations


def advance(world, dt: float) -> None:
    raise NotImplementedError("L2 待实现：core/waves.py advance（按 delay/interval 刷怪、推进波次）")


def start_wave(world, index: int | None = None) -> None:
    raise NotImplementedError("L2 待实现：core/waves.py start_wave（立即开下一波）")
