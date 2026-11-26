"""路径折线与行驶距离（L1 战斗线负责，见 CONTRACT D2 / §2）。

唯一坐标出口：屏幕/世界坐标只能由 ``pos_at(s)`` 得到，别处不得自行插值。
"""

from __future__ import annotations


class Path:
    length: float

    def __init__(self, points) -> None:
        raise NotImplementedError("L1 待实现：core/path.py Path.__init__（折线长度表）")

    def pos_at(self, s: float) -> tuple[float, float]:
        """返回已行驶距离 s 处的**格子中心坐标**（浮点），s 先按 [0, length] 夹取。

        K1：格子中心 = 格索引 + 0.5，所以首点 (0, 4) 处 pos_at(0) == (0.5, 4.5)。
        引擎不做像素换算，界面侧统一 pixel = origin + coord * cell_size。
        """
        raise NotImplementedError("L1 待实现：Path.pos_at")

    def clamp(self, s: float) -> float:
        raise NotImplementedError("L1 待实现：Path.clamp")
