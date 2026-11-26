"""固定步长主循环（L2 驱动线负责，见 CONTRACT D3 / D4 / D8 / I5）。

D4 的顺序是契约的一部分，实现时不要调换：
① 指令入队（由 main 在 tick 之前处理）
② 敌人移动
③ 塔索敌开火
④ 子弹推进与命中
⑤ 死亡/漏怪清理
⑥ 波次推进
⑦ 发事件（调用方负责）
⑧ 输出快照（调用方负责）
"""

from __future__ import annotations

from . import waves
from .combat import resolve
from .world import Phase

DT = 1.0 / 30.0


def tick(world) -> None:
    if world.paused:
        return

    world.tick += 1
    world.events.clear()

    _move_enemies(world)                          # ②
    world.events.extend(resolve(world, DT))       # ③④
    _cleanup(world)                               # ⑤
    waves.advance(world, DT)                      # ⑥


def _move_enemies(world) -> None:
    from ..protocol import events as event_mod

    for enemy in list(world.enemies):
        if enemy.step(DT, world.path):
            continue
        world.leaks += 1
        world.hp -= enemy.leak_damage
        world.emit(
            event_mod.leak(world.tick, enemy.id, enemy.type, enemy.leak_damage, world.hp)
        )


def _cleanup(world) -> None:
    from ..protocol import events as event_mod

    survivors = []
    for enemy in world.enemies:
        if enemy.alive:
            survivors.append(enemy)
            continue
        world.kills += 1
        world.gold += enemy.gold_reward
        x, y = world.path.pos_at(enemy.s)
        world.emit(event_mod.kill(world.tick, enemy.id, enemy.type, enemy.gold_reward, x, y))
    world.enemies = survivors

    world.bullets = [bullet for bullet in world.bullets if bullet.alive]


def is_over(world) -> tuple[bool, str]:
    """(结束?, "WIN" | "LOSE" | "")。D8：血量为 0 立即判负；全部波次清空判胜。"""
    if world.phase is Phase.OVER:
        return True, getattr(world, "result", "") or ""
    if world.hp <= 0:
        return True, "LOSE"
    total_waves = len(world.cfg["waves"]["waves"])
    if world.wave_index >= total_waves and not world.enemies and not world.bullets:
        return True, "WIN"
    return False, ""
