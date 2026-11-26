"""敌人（L1 负责）。位置只存已行驶距离 s（CONTRACT D2）。"""

from __future__ import annotations


class Enemy:
    id: int
    type: str
    hp: float
    max_hp: float
    speed: float
    s: float
    alive: bool
    leak_damage: int
    gold_reward: int
    armor: float

    def __init__(self, entity_id: int, cfg: dict) -> None:
        raise NotImplementedError("L1 待实现：Enemy.__init__")

    def step(self, dt: float, path) -> bool:
        """前进 dt 秒；返回 True 表示仍在路上，False 表示已抵达终点（漏怪）。"""
        raise NotImplementedError("L1 待实现：Enemy.step")
