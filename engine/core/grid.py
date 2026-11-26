"""格子坐标与占格（L1 战斗线负责，见 CONTRACT D7 / §2）。

语义（实现时必须满足）：
- in_bounds(cell): 0 <= x < width 且 0 <= y < height
- is_buildable(cell): 在界内、不在路径格、不在 blocked、未被占用
- occupy/release/occupant: 维护 cell -> entity_id 的唯一占用关系
"""

from __future__ import annotations


class Grid:
    width: int
    height: int
    path_cells: set
    blocked: set
    occupied: dict

    def __init__(self, width: int, height: int, path_cells=(), blocked=()) -> None:
        raise NotImplementedError("L1 待实现：core/grid.py Grid.__init__（格子地图与占格表）")

    def in_bounds(self, cell) -> bool:
        raise NotImplementedError("L1 待实现：Grid.in_bounds")

    def is_buildable(self, cell) -> bool:
        raise NotImplementedError("L1 待实现：Grid.is_buildable")

    def occupy(self, cell, entity_id: int) -> None:
        raise NotImplementedError("L1 待实现：Grid.occupy")

    def release(self, cell) -> None:
        raise NotImplementedError("L1 待实现：Grid.release")

    def occupant(self, cell):
        raise NotImplementedError("L1 待实现：Grid.occupant")
