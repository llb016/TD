"""世界状态容器（L2 驱动线负责，见 CONTRACT §2 / D5）。

World 是唯一持有状态的地方：L1 只读它的 grid/path/rng 并往 events 里 append。
"""

from __future__ import annotations

import random
from enum import Enum

from .grid import Grid
from .path import Path


class Phase(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    OVER = "over"


class World:
    def __init__(self, level_id: int, cfg: dict, seed: int = 0) -> None:
        self.level_id = int(level_id)
        self.cfg = cfg
        self.rng = random.Random(seed)

        map_cfg = cfg["map"]
        self.grid = Grid(
            map_cfg["grid"]["width"],
            map_cfg["grid"]["height"],
            path_cells=map_cfg["path"],
            blocked=map_cfg.get("blocked", ()),
        )
        self.path = Path(map_cfg["path"])

        self.tick = 0
        self.gold = int(cfg["waves"]["start_gold"])
        self.hp = int(cfg["waves"]["start_hp"])
        self.wave_index = 0
        self.speed = 1
        self.paused = False
        self.phase = Phase.RUNNING

        self.towers: dict[int, object] = {}
        self.enemies: list = []
        self.bullets: list = []
        self.events: list[dict] = []

        self.kills = 0
        self.leaks = 0
        self._next_id_value = 1

    @classmethod
    def create(cls, level_id: int, cfg: dict, seed: int = 0) -> "World":
        return cls(level_id, cfg, seed)

    def next_id(self) -> int:
        """全局唯一、单调递增、永不复用（D5）。"""
        value = self._next_id_value
        self._next_id_value += 1
        return value

    def emit(self, event: dict) -> None:
        self.events.append(event)
