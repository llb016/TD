"""stdin 指令解析与校验（CONTRACT §3 / D12 / R1）。

本层只负责"形状正确"，是否可以建塔、金币够不够由引擎判断（U3）。
"""

from __future__ import annotations

import json

KNOWN_TYPES = (
    "HELLO",
    "start",
    "place_tower",
    "upgrade_tower",
    "sell_tower",
    "next_wave",
    "set_speed",
    "pause",
    "resume",
    "exit",
)


class CommandError(Exception):
    """指令不合法。code 为 bad_json（语法错）或 bad_command（语义错）。"""

    def __init__(self, code: str, reason: str) -> None:
        self.code = code
        self.reason = reason
        super().__init__(f"{code}: {reason}")


def _int(msg: dict, key: str, minimum: int | None = None) -> int:
    if key not in msg:
        raise CommandError("bad_command", f"缺少字段 {key}")
    value = msg[key]
    if type(value) is not int:
        raise CommandError("bad_command", f"{key} 必须是整数")
    if minimum is not None and value < minimum:
        raise CommandError("bad_command", f"{key} 必须 >= {minimum}")
    return value


def _str(msg: dict, key: str) -> str:
    value = msg.get(key)
    if not isinstance(value, str) or not value:
        raise CommandError("bad_command", f"{key} 必须是非空字符串")
    return value


def _cell(msg: dict, key: str = "cell") -> tuple[int, int]:
    value = msg.get(key)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise CommandError("bad_command", f"{key} 必须是 [x, y]")
    if any(type(item) is not int for item in value):
        raise CommandError("bad_command", f"{key} 的两个分量必须是整数")
    return int(value[0]), int(value[1])


def parse(line: str) -> dict:
    """把一行文本解析为指令字典；不合法时抛 CommandError。"""
    try:
        msg = json.loads(line)
    except json.JSONDecodeError as exc:
        raise CommandError("bad_json", f"JSON 语法错误：{exc.msg}（第 {exc.lineno} 行）") from exc

    if not isinstance(msg, dict):
        raise CommandError("bad_json", "一行必须是一个 JSON 对象")

    ctype = msg.get("type")
    if not isinstance(ctype, str):
        raise CommandError("bad_command", "缺少字符串字段 type")
    if ctype not in KNOWN_TYPES:
        raise CommandError("bad_command", f"未知指令 {ctype!r}")

    cmd: dict = {"type": ctype}
    if ctype == "start":
        cmd["level_id"] = _int(msg, "level_id", 1)
    elif ctype == "place_tower":
        cmd["tower_type"] = _str(msg, "tower_type")
        cmd["cell"] = _cell(msg)
    elif ctype in ("upgrade_tower", "sell_tower"):
        cmd["tower_id"] = _int(msg, "tower_id", 1)
    elif ctype == "next_wave":
        cmd["wave_index"] = _int(msg, "wave_index", 1)
    elif ctype == "set_speed":
        value = _int(msg, "value", 1)
        if value not in (1, 2, 3):
            raise CommandError("bad_command", "value 只能是 1 / 2 / 3")
        cmd["value"] = value
    return cmd
