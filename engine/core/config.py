"""配置加载与校验（CONTRACT §4 / D9 / R5 / R6 / §9.1）。

校验在启动时完成：配置写错就让进程以退出码 2 失败，绝不带病运行。
每个错误都带文件名与字段路径，便于定位。
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_FILES = ("map", "tower", "enemy", "wave")


class ConfigError(Exception):
    def __init__(self, file: str, path: str, reason: str) -> None:
        self.file = file
        self.path = path
        self.reason = reason
        super().__init__(f"{file}: {path or '<root>'} {reason}")


# ---------------------------------------------------------------- 基础校验


def _read(path: Path) -> object:
    if not path.is_file():
        raise ConfigError(path.as_posix(), "", "文件不存在")
    try:
        # utf-8-sig：容忍记事本另存为带 BOM 的 UTF-8（Windows 常见）
        with path.open(encoding="utf-8-sig") as fp:
            return json.load(fp)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            path.as_posix(), "", f"JSON 语法错误（第 {exc.lineno} 行第 {exc.colno} 列）"
        ) from exc


def _need(obj, key: str, file: str, path: str):
    if not isinstance(obj, dict):
        raise ConfigError(file, path, f"应为对象，实际是 {type(obj).__name__}")
    if key not in obj:
        raise ConfigError(file, path, f"缺少必填字段 {key}")
    return obj[key]


def _int(value, file: str, path: str, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise ConfigError(file, path, f"必须是整数（当前 {type(value).__name__}: {value!r}）")
    if minimum is not None and value < minimum:
        raise ConfigError(file, path, f"必须 >= {minimum}（当前 {value}）")
    return value


def _num(
    value, file: str, path: str, minimum: float | None = None, exclusive: bool = False
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(file, path, f"必须是数字（当前 {type(value).__name__}: {value!r}）")
    number = float(value)
    if minimum is not None:
        if exclusive and number <= minimum:
            raise ConfigError(file, path, f"必须 > {minimum}（当前 {number}）")
        if not exclusive and number < minimum:
            raise ConfigError(file, path, f"必须 >= {minimum}（当前 {number}）")
    return number


def _str(value, file: str, path: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ConfigError(file, path, f"必须是字符串（当前 {type(value).__name__}）")
    if not allow_empty and not value:
        raise ConfigError(file, path, "不能为空字符串")
    return value


def _list(value, file: str, path: str, min_len: int = 0) -> list:
    if not isinstance(value, list):
        raise ConfigError(file, path, f"必须是数组（当前 {type(value).__name__}）")
    if len(value) < min_len:
        raise ConfigError(file, path, f"至少需要 {min_len} 项（当前 {len(value)}）")
    return value


def _select(data, key: str, value, file: str) -> dict:
    """配置文件可以是「单条记录」或「记录数组」，按 key=value 选出本次要用的那条。"""
    items = data if isinstance(data, list) else [data]
    for item in items:
        if isinstance(item, dict) and item.get(key) == value:
            return item
    raise ConfigError(file, key, f"找不到 {key}={value!r} 的记录")


def _records(data, key: str, file: str) -> list[dict]:
    """tower.json / enemy.json 允许单条、数组或 {键: 记录} 三种写法，统一成列表。"""
    if isinstance(data, dict) and key not in data and all(isinstance(v, dict) for v in data.values()):
        items = list(data.values())
    elif isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        raise ConfigError(file, "<root>", f"应为对象或数组（当前 {type(data).__name__}）")
    for item in items:
        _need(item, key, file, "<record>")
    return items


# ---------------------------------------------------------------- 各文件校验


def _validate_map(cfg: dict, file: str) -> dict:
    level_id = _int(_need(cfg, "id", file, "<root>"), file, "id", 1)
    name = _str(_need(cfg, "name", file, "<root>"), file, "name")
    grid = _need(cfg, "grid", file, "<root>")
    width = _int(_need(grid, "width", file, "grid"), file, "grid.width", 1)
    height = _int(_need(grid, "height", file, "grid"), file, "grid.height", 1)

    points = _list(_need(cfg, "path", file, "<root>"), file, "path", 2)
    path: list[list[int]] = []
    for index, point in enumerate(points):
        where = f"path[{index}]"
        _list(point, file, where, 2)
        if len(point) != 2:
            raise ConfigError(file, where, "必须是 [x, y] 两个整数")
        x = _int(point[0], file, f"{where}[0]")
        y = _int(point[1], file, f"{where}[1]")
        if not (0 <= x < width and 0 <= y < height):
            raise ConfigError(file, where, f"({x}, {y}) 越界，地图为 {width}x{height}")
        if path:
            px, py = path[-1]
            if (px, py) == (x, y):
                raise ConfigError(file, where, f"与上一个点重合 ({x}, {y})")
            if px != x and py != y:
                raise ConfigError(
                    file, where, f"相邻点必须同行或同列：({px}, {py}) → ({x}, {y})"
                )
        path.append([x, y])

    blocked_raw = cfg.get("blocked", [])
    blocked = []
    for index, point in enumerate(_list(blocked_raw, file, "blocked")):
        where = f"blocked[{index}]"
        _list(point, file, where, 2)
        if len(point) != 2:
            raise ConfigError(file, where, "必须是 [x, y] 两个整数")
        x = _int(point[0], file, f"{where}[0]")
        y = _int(point[1], file, f"{where}[1]")
        if not (0 <= x < width and 0 <= y < height):
            raise ConfigError(file, where, f"({x}, {y}) 越界，地图为 {width}x{height}")
        blocked.append([x, y])

    return {
        "id": level_id,
        "name": name,
        "grid": {"width": width, "height": height},
        "path": path,
        "blocked": blocked,
    }


def _validate_effect(cfg: dict, file: str, where: str) -> dict:
    effect = _need(cfg, "effect", file, where)
    kind = _str(_need(effect, "kind", file, where), file, f"{where}.kind")
    if kind == "single":
        return {"kind": "single"}
    if kind == "slow":
        factor = _num(_need(effect, "factor", file, where), file, f"{where}.factor", 0, True)
        if factor > 1:
            raise ConfigError(file, f"{where}.factor", f"必须 <= 1（当前 {factor}）")
        duration = _num(_need(effect, "duration", file, where), file, f"{where}.duration", 0, True)
        return {"kind": "slow", "factor": factor, "duration": duration}
    raise ConfigError(file, f"{where}.kind", f"只允许 single / slow（当前 {kind!r}）")


def _validate_tower(cfg: dict, file: str) -> dict:
    tower_type = _str(_need(cfg, "type", file, "<record>"), file, "type")
    where = f"tower[{tower_type}]"
    name = _str(_need(cfg, "name", file, where), file, f"{where}.name")
    icon = _str(cfg.get("icon", ""), file, f"{where}.icon", allow_empty=True)
    cost = _int(_need(cfg, "cost", file, where), file, f"{where}.cost", 0)
    projectile_speed = _num(
        _need(cfg, "projectile_speed", file, where), file, f"{where}.projectile_speed", 0
    )

    levels_raw = _list(_need(cfg, "levels", file, where), file, f"{where}.levels", 1)
    levels = []
    last = len(levels_raw) - 1
    for index, level in enumerate(levels_raw):
        at = f"{where}.levels[{index}]"
        damage = _num(_need(level, "damage", file, at), file, f"{at}.damage", 0)
        attack_range = _num(_need(level, "range", file, at), file, f"{at}.range", 0, True)
        interval = _num(_need(level, "interval", file, at), file, f"{at}.interval", 0, True)
        upgrade_cost = _int(_need(level, "upgrade_cost", file, at), file, f"{at}.upgrade_cost", 0)
        if index == last and upgrade_cost != 0:
            raise ConfigError(file, f"{at}.upgrade_cost", f"最后一级必须为 0（当前 {upgrade_cost}）")
        if index != last and upgrade_cost == 0:
            raise ConfigError(file, f"{at}.upgrade_cost", "非最后一级不能为 0")
        levels.append(
            {
                "damage": damage,
                "range": attack_range,
                "interval": interval,
                "upgrade_cost": upgrade_cost,
            }
        )

    return {
        "type": tower_type,
        "name": name,
        "icon": icon,
        "cost": cost,
        "projectile_speed": projectile_speed,
        "levels": levels,
        "effect": _validate_effect(cfg, file, where),
    }


def _validate_enemy(cfg: dict, file: str) -> dict:
    enemy_type = _str(_need(cfg, "type", file, "<record>"), file, "type")
    where = f"enemy[{enemy_type}]"
    return {
        "type": enemy_type,
        "name": _str(_need(cfg, "name", file, where), file, f"{where}.name"),
        "icon": _str(cfg.get("icon", ""), file, f"{where}.icon", allow_empty=True),
        "hp": _num(_need(cfg, "hp", file, where), file, f"{where}.hp", 0, True),
        "speed": _num(_need(cfg, "speed", file, where), file, f"{where}.speed", 0, True),
        "leak_damage": _int(
            _need(cfg, "leak_damage", file, where), file, f"{where}.leak_damage", 0
        ),
        "gold_reward": _int(_need(cfg, "gold_reward", file, where), file, f"{where}.gold_reward", 0),
        "armor": _num(cfg.get("armor", 0), file, f"{where}.armor", 0),
    }


def _validate_waves(cfg: dict, file: str, enemy_types: set[str]) -> dict:
    level_id = _int(_need(cfg, "level_id", file, "<root>"), file, "level_id", 1)
    where = f"wave[level_id={level_id}]"
    start_gold = _int(_need(cfg, "start_gold", file, where), file, f"{where}.start_gold", 0)
    start_hp = _int(_need(cfg, "start_hp", file, where), file, f"{where}.start_hp", 1)

    waves_raw = _list(_need(cfg, "waves", file, where), file, f"{where}.waves", 1)
    waves = []
    for w_index, wave_cfg in enumerate(waves_raw):
        at = f"{where}.waves[{w_index}]"
        groups_raw = _list(_need(wave_cfg, "groups", file, at), file, f"{at}.groups", 1)
        groups = []
        for g_index, group in enumerate(groups_raw):
            gat = f"{at}.groups[{g_index}]"
            enemy_type = _str(_need(group, "enemy_type", file, gat), file, f"{gat}.enemy_type")
            if enemy_type not in enemy_types:
                raise ConfigError(
                    file,
                    f"{gat}.enemy_type",
                    f"{enemy_type!r} 在 enemy.json 中不存在（可选：{sorted(enemy_types)}）",
                )
            groups.append(
                {
                    "enemy_type": enemy_type,
                    "count": _int(_need(group, "count", file, gat), file, f"{gat}.count", 1),
                    "interval": _num(
                        _need(group, "interval", file, gat), file, f"{gat}.interval", 0, True
                    ),
                    "delay": _num(_need(group, "delay", file, gat), file, f"{gat}.delay", 0),
                }
            )
        waves.append({"groups": groups})

    return {"level_id": level_id, "start_gold": start_gold, "start_hp": start_hp, "waves": waves}


def _no_duplicates(records: list[dict], file: str) -> None:
    seen: set[str] = set()
    for record in records:
        key = record["type"]
        if key in seen:
            raise ConfigError(file, f"type={key}", "type 重复")
        seen.add(key)


def load(dir_path, level_id: int = 1) -> dict:
    """加载并校验四份配置，返回可在引擎内直接使用的归一化字典。"""
    base = Path(dir_path)
    raw = {name: _read(base / f"{name}.json") for name in CONFIG_FILES}

    map_file = (base / "map.json").as_posix()
    tower_file = (base / "tower.json").as_posix()
    enemy_file = (base / "enemy.json").as_posix()
    wave_file = (base / "wave.json").as_posix()

    map_cfg = _validate_map(_select(raw["map"], "id", level_id, map_file), map_file)

    towers = [
        _validate_tower(item, tower_file)
        for item in _records(raw["tower"], "type", tower_file)
    ]
    _no_duplicates(towers, tower_file)

    enemies = [
        _validate_enemy(item, enemy_file)
        for item in _records(raw["enemy"], "type", enemy_file)
    ]
    _no_duplicates(enemies, enemy_file)

    wave_cfg = _validate_waves(
        _select(raw["wave"], "level_id", level_id, wave_file),
        wave_file,
        {enemy["type"] for enemy in enemies},
    )

    return {"level_id": level_id, "map": map_cfg, "towers": towers, "enemies": enemies, "waves": wave_cfg}
