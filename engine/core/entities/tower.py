"""塔（L1 负责）。索敌规则见 CONTRACT D6：射程内、路径最靠前的敌人。"""

from __future__ import annotations


class Tower:
    id: int
    type: str
    cell: tuple[int, int]
    level: int
    cooldown: float

    def __init__(self, entity_id: int, cfg: dict, cell) -> None:
        raise NotImplementedError("L1 待实现：Tower.__init__")

    def target(self, enemies):
        raise NotImplementedError("L1 待实现：Tower.target")

    def upgrade(self) -> bool:
        """升一级；已满级返回 False。"""
        raise NotImplementedError("L1 待实现：Tower.upgrade")
