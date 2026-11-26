"""战斗结算（L1 战斗线负责，见 CONTRACT §2 / D6 / D7）。

三件必须遵守的事：
1. 距离用格、时间用秒，射程判定 dist <= range。
2. 击杀与漏怪只 append 事件到 world.events，金币/血量入账由 L2 完成（D7）。
3. 只返回本次 tick 产生的事件，不直接输出 JSON。
"""

from __future__ import annotations


def resolve(world, dt: float) -> list:
    raise NotImplementedError("L1 待实现：core/combat.py resolve（索敌→开火→命中→击杀）")


def place_tower(world, tower_type: str, cell) -> tuple[bool, str]:
    """合法性判定（界内/可建/未占用），返回 (ok, 原因)。金币由 L2 扣。"""
    raise NotImplementedError("L1 待实现：combat.place_tower")


def upgrade_tower(world, tower_id: int) -> tuple[bool, str, int]:
    """返回 (ok, 原因, 消耗金币)。"""
    raise NotImplementedError("L1 待实现：combat.upgrade_tower")


def sell_tower(world, tower_id: int) -> tuple[bool, str, int]:
    """返回 (ok, 原因, 返还金币)。"""
    raise NotImplementedError("L1 待实现：combat.sell_tower")
