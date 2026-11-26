"""每帧状态快照（CONTRACT §3.1 / R7）。

坐标一律取格子中心，并保留 2 位小数以控制单帧体积。
"""

from __future__ import annotations


def _r(value: float) -> float:
    return round(float(value), 2)


def snapshot(world) -> dict:
    towers = [
        [tower.id, tower.type, int(tower.cell[0]), int(tower.cell[1]), int(tower.level)]
        for tower in world.towers.values()
    ]

    enemies = []
    for enemy in world.enemies:
        x, y = world.path.pos_at(enemy.s)
        enemies.append([enemy.id, enemy.type, _r(x), _r(y), _r(enemy.hp), _r(enemy.max_hp)])

    bullets = [
        [bullet.id, _r(bullet.x), _r(bullet.y), bullet.target_id] for bullet in world.bullets
    ]

    return {
        "type": "state",
        "tick": int(world.tick),
        "gold": int(world.gold),
        "hp": int(world.hp),
        "wave": int(world.wave_index),
        "paused": bool(world.paused),
        "speed": int(world.speed),
        "towers": towers,
        "enemies": enemies,
        "bullets": bullets,
    }
