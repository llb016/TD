"""引擎入口（CONTRACT I2 / I4 / R1–R4 / B1 / B6）。

用法：
    python -m engine.main --stdio                      # 与界面通信（默认模式）
    python -m engine.main --headless --level 1 --seed 0 # 命令行跑分
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .core import combat
from .core import waves as waves_mod
from .core.config import ConfigError, load as load_config
from .core.loop import is_over, tick
from .core.world import Phase, World
from .protocol import PROTOCOL_VERSION, commands, events
from .protocol.snapshot import snapshot

CONFIG_DIR = Path(__file__).resolve().parent / "config"
MAX_BAD_LINES = 10

log = logging.getLogger("engine")


# ---------------------------------------------------------------- 输出


def write_line(msg: dict) -> None:
    """写一行协议 JSON：单行、UTF-8、以 \\n 结束（B4）。"""
    text = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
    if "\n" in text or "\r" in text:
        raise ValueError("协议行内不得包含换行")
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------- 引擎


class Engine:
    def __init__(self, config_dir=CONFIG_DIR, level: int = 1, seed: int = 0) -> None:
        self.config_dir = Path(config_dir)
        self.level = int(level)
        self.seed = int(seed)
        self.cfg: dict | None = None
        self.world: World | None = None
        self.phase = Phase.IDLE
        self.bad_lines = 0

    # --- 生命周期 -------------------------------------------------

    def run_stdio(self) -> int:
        log.info("引擎就绪：PROTOCOL v%s，等待指令", PROTOCOL_VERSION)
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue

            try:
                cmd = commands.parse(line)
            except commands.CommandError as exc:
                if self._on_bad_line(exc):
                    return 1
                continue

            self.bad_lines = 0
            try:
                if not self.handle(cmd):
                    return 0
            except NotImplementedError as exc:
                log.warning("功能未实现：%s", exc)
                self.emit(events.info("not_implemented", self._tick(), msg=str(exc)))
            except Exception as exc:  # noqa: BLE001 - 兜底，见 B7
                log.exception("处理指令时发生异常")
                self.emit(events.engine_error(str(exc)))
                return 1

        log.info("stdin EOF，退出（B6 / I4）")
        return 0

    def _on_bad_line(self, exc: commands.CommandError) -> bool:
        """R1 / D12：语法错的整行丢弃；连续过多则报错退出。返回 True 表示要退出。"""
        if exc.code != "bad_json":
            self.emit(events.info("bad_command", self._tick(), msg=exc.reason))
            return False
        self.bad_lines += 1
        log.warning("丢弃非法行（连续 %d/%d）：%s", self.bad_lines, MAX_BAD_LINES, exc.reason)
        if self.bad_lines >= MAX_BAD_LINES:
            self.emit(events.engine_error("连续非法行过多，协议流不可用", "bad_stream"))
            return True
        return False

    def emit(self, msg: dict) -> None:
        write_line(msg)

    def _tick(self) -> int:
        return self.world.tick if self.world is not None else 0

    # --- 指令分发 -------------------------------------------------

    def handle(self, cmd: dict) -> bool:
        """处理一条指令；返回 False 表示退出进程。"""
        ctype = cmd["type"]

        if ctype == "HELLO":
            self.emit(
                {
                    "type": "HELLO_ACK",
                    "protocol_version": PROTOCOL_VERSION,
                    "engine_version": __version__,
                }
            )
            return True

        if ctype == "exit":
            self.emit({"type": "BYE"})
            return False

        if ctype == "start":
            return self._start(cmd["level_id"])

        # R3 / R4：只有 RUNNING 才接受玩法指令
        if self.phase is not Phase.RUNNING or self.world is None:
            self.emit(events.info("bad_command", self._tick(), msg=f"{ctype}：当前未在对局中"))
            return True

        world = self.world
        if ctype == "set_speed":
            world.speed = cmd["value"]
        elif ctype == "pause":
            world.paused = True
        elif ctype == "resume":
            world.paused = False
        elif ctype == "place_tower":
            ok, reason = combat.place_tower(world, cmd["tower_type"], cmd["cell"])
            if not ok:
                self.emit(events.info(reason or "bad_command", world.tick, cell=cmd["cell"]))
                return True
            # TODO(L2): 金币扣减与 gold 事件落账（D7）
        elif ctype == "upgrade_tower":
            ok, reason, _cost = combat.upgrade_tower(world, cmd["tower_id"])
            if not ok:
                self.emit(events.info(reason or "bad_command", world.tick))
                return True
            # TODO(L2): 扣金币 + gold 事件（D7）
        elif ctype == "sell_tower":
            ok, reason, _refund = combat.sell_tower(world, cmd["tower_id"])
            if not ok:
                self.emit(events.info(reason or "bad_command", world.tick))
                return True
            # TODO(L2): 返还金币 + gold 事件（D7）
        elif ctype == "next_wave":
            waves_mod.start_wave(world, cmd["wave_index"])

        self._step_and_emit()
        return True

    def _start(self, level_id: int) -> bool:
        self.world = None
        self.phase = Phase.IDLE

        try:
            self.cfg = load_config(self.config_dir, level_id)
        except ConfigError as exc:
            log.error("配置错误：%s", exc)
            self.emit(events.engine_error(str(exc), "config_error"))
            raise SystemExit(2) from exc

        map_cfg = self.cfg["map"]
        self.emit(
            {
                "type": "map",
                "id": map_cfg["id"],
                "name": map_cfg["name"],
                "grid": map_cfg["grid"],
                "path": map_cfg["path"],
                "start": map_cfg["path"][0],
                "end": map_cfg["path"][-1],
            }
        )
        self.emit(
            {
                "type": "config",
                "towers": [
                    {
                        "type": tower["type"],
                        "name": tower["name"],
                        "icon": tower["icon"],
                        "cost": tower["cost"],
                    }
                    for tower in self.cfg["towers"]
                ],
                "enemies": [
                    {"type": enemy["type"], "name": enemy["name"], "icon": enemy["icon"]}
                    for enemy in self.cfg["enemies"]
                ],
            }
        )

        try:
            self.world = World.create(level_id, self.cfg, self.seed)
        except NotImplementedError as exc:
            log.warning("引擎功能未实现：%s", exc)
            self.emit(events.info("not_implemented", 0, msg=str(exc)))
            return True

        self.phase = Phase.RUNNING
        self.emit(snapshot(self.world))
        return True

    def _step_and_emit(self) -> None:
        world = self.world
        # TODO(L2): 按 30 行/秒独立节拍输出（B5）；骨架期每处理一条指令推进一步
        for _ in range(max(1, world.speed)):
            if not world.paused:
                tick(world)
            if is_over(world)[0]:
                break

        for event in world.events:
            self.emit(events.event_to_msg(event))
        world.events.clear()

        over, why = is_over(world)
        if over:
            self.phase = Phase.OVER
            self.emit(
                events.result(
                    world.tick,
                    why == "WIN",
                    world.kills,
                    world.leaks,
                    world.gold,
                    world.hp,
                    world.tick,
                )
            )
        else:
            self.emit(snapshot(world))


# ---------------------------------------------------------------- 无界面模式


def run_headless(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(Path(args.config_dir), args.level)
    except ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr, flush=True)
        return 2

    world = World.create(args.level, cfg, args.seed)
    for _ in range(args.max_ticks):
        tick(world)
        for event in world.events:
            print(json.dumps(events.event_to_msg(event), ensure_ascii=False), flush=True)
        world.events.clear()

        over, why = is_over(world)
        if over:
            print(why, flush=True)
            return 0

    print("TIMEOUT：超过最大 tick 数仍未结束", file=sys.stderr, flush=True)
    return 1


# ---------------------------------------------------------------- 入口


def _configure_io() -> None:
    """R2：三路标准流统一 UTF-8 + LF，避免 Windows 下中文崩溃与多余 \\r。"""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="engine.main", description="塔防游戏引擎")
    parser.add_argument("--stdio", action="store_true", help="与界面按行 JSON 通信（默认）")
    parser.add_argument("--headless", action="store_true", help="命令行跑分，不读 stdin")
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--config-dir", default=str(CONFIG_DIR))
    parser.add_argument("--max-ticks", type=int, default=20000)
    parser.add_argument("--log", metavar="FILE", help="日志写文件（默认 stderr）")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def _configure_logging(args: argparse.Namespace) -> None:
    level = logging.DEBUG if args.verbose else logging.INFO
    if args.log:
        handler: logging.Handler = logging.FileHandler(args.log, encoding="utf-8")
        fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    else:
        handler = logging.StreamHandler(sys.stderr)
        fmt = "%(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=level, handlers=[handler], format=fmt, force=True)


def main(argv=None) -> int:
    _configure_io()
    args = _parse_args(argv)
    _configure_logging(args)

    try:
        if args.headless:
            return run_headless(args)
        return Engine(args.config_dir, args.level, args.seed).run_stdio()
    except NotImplementedError as exc:
        print(f"引擎功能未实现：{exc}", file=sys.stderr, flush=True)
        return 1
    except Exception as exc:  # noqa: BLE001 - 兜底，见 B7
        log.exception("未捕获异常")
        try:
            write_line(events.engine_error(str(exc)))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
