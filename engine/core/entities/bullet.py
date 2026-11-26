"""子弹（L1 负责）。CONTRACT D6 规定默认追踪必中，不做弹道碰撞。"""

from __future__ import annotations


class Bullet:
    id: int
    x: float
    y: float
    target_id: int
    speed: float
    damage: float
    alive: bool

    def __init__(self, entity_id: int, x: float, y: float, target_id: int, speed: float, damage: float) -> None:
        raise NotImplementedError("L1 待实现：Bullet.__init__")

    def move(self, dt: float, target) -> bool:
        """朝目标推进；返回 True 表示已命中。"""
        raise NotImplementedError("L1 待实现：Bullet.move")
