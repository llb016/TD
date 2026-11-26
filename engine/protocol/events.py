"""事件构造与序列化（CONTRACT §3.2 / D10）。

事件是普通 dict：L1 往 ``world.events`` 里 append，L2 在 tick 末尾统一发出。
"""

from __future__ import annotations


def _r(value: float) -> float:
    return round(float(value), 2)


def info(code: str, tick: int = 0, cell=None, msg: str = "") -> dict:
    event = {"type": "info", "code": code, "tick": int(tick)}
    if cell is not None:
        event["cell"] = [int(cell[0]), int(cell[1])]
    if msg:
        event["msg"] = msg
    return event


def engine_error(msg: str, code: str = "internal") -> dict:
    return {"type": "engine_error", "code": code, "msg": msg}


def kill(tick: int, enemy_id: int, enemy_type: str, gold: int, x: float, y: float) -> dict:
    return {
        "type": "kill",
        "tick": int(tick),
        "enemy_id": int(enemy_id),
        "enemy_type": enemy_type,
        "gold": int(gold),
        "x": _r(x),
        "y": _r(y),
    }


def leak(tick: int, enemy_id: int, enemy_type: str, hp_damage: int, hp_left: int) -> dict:
    return {
        "type": "leak",
        "tick": int(tick),
        "enemy_id": int(enemy_id),
        "enemy_type": enemy_type,
        "hp_damage": int(hp_damage),
        "hp_left": int(hp_left),
    }


def wave(tick: int, index: int, total: int) -> dict:
    return {"type": "wave", "tick": int(tick), "wave": int(index), "total": int(total)}


def gold(tick: int, delta: int, total: int) -> dict:
    return {"type": "gold", "tick": int(tick), "delta": int(delta), "total": int(total)}


def result(
    tick: int,
    win: bool,
    kills: int,
    leaks: int,
    gold_left: int,
    hp_left: int,
    duration_ticks: int,
) -> dict:
    return {
        "type": "result",
        "tick": int(tick),
        "win": bool(win),
        "kills": int(kills),
        "leaks": int(leaks),
        "gold_left": int(gold_left),
        "hp_left": int(hp_left),
        "duration_ticks": int(duration_ticks),
    }


def event_to_msg(event: dict) -> dict:
    """事件 → 协议消息。目前是恒等映射，保留这层以便将来裁剪字段。"""
    return dict(event)
