"""契约测试：把 engine/CONTRACT.md 的约定变成可执行断言。

- 现在必须绿：签名、配置校验、指令解析、状态机、协议行格式、stdin 生命周期。
- TODO 项：L1/L2 实现后应改为真实行为测试（文件里已用 xfail_todo 标记）。
"""

from __future__ import annotations

import inspect
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.core import combat, loop, waves  # noqa: E402
from engine.core.config import ConfigError, load  # noqa: E402
from engine.core.world import Phase  # noqa: E402
from engine.protocol import PROTOCOL_VERSION, commands, events  # noqa: E402
from engine.protocol.snapshot import snapshot  # noqa: E402

CONFIG_DIR = ROOT / "engine" / "config"


class ConfigFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.dir = Path(self._tmp)
        for path in CONFIG_DIR.glob("*.json"):
            shutil.copy(path, self.dir / path.name)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def patch(self, name: str, mutate) -> None:
        path = self.dir / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestSignatures(unittest.TestCase):
    """CONTRACT §2：签名冻结，只能加可选参数（D13）。"""

    def test_l1_signatures(self) -> None:
        self.assertEqual(list(inspect.signature(combat.resolve).parameters), ["world", "dt"])
        self.assertEqual(
            list(inspect.signature(combat.place_tower).parameters),
            ["world", "tower_type", "cell"],
        )
        self.assertEqual(
            list(inspect.signature(combat.upgrade_tower).parameters), ["world", "tower_id"]
        )
        self.assertEqual(
            list(inspect.signature(combat.sell_tower).parameters), ["world", "tower_id"]
        )

    def test_l2_signatures(self) -> None:
        self.assertEqual(list(inspect.signature(loop.tick).parameters), ["world"])
        self.assertEqual(list(inspect.signature(loop.is_over).parameters), ["world"])
        self.assertEqual(list(inspect.signature(snapshot).parameters), ["world"])
        self.assertEqual(list(inspect.signature(events.event_to_msg).parameters), ["event"])
        self.assertEqual(list(inspect.signature(waves.advance).parameters), ["world", "dt"])

    def test_l1_stubs_declare_their_owner(self) -> None:
        with self.assertRaises(NotImplementedError) as ctx:
            combat.resolve(object(), 1 / 30)
        self.assertIn("L1", str(ctx.exception))


class TestConfigValidation(ConfigFixture):
    """CONTRACT §9.1：配置写错必须启动即失败，并指出文件与字段。"""

    def test_default_config_loads(self) -> None:
        cfg = load(CONFIG_DIR, 1)
        self.assertEqual(cfg["map"]["id"], 1)
        self.assertEqual(len(cfg["towers"]), 2)
        self.assertEqual(len(cfg["enemies"]), 2)
        self.assertEqual(len(cfg["waves"]["waves"]), 3)
        self.assertEqual(cfg["waves"]["start_gold"], 150)

    def test_zero_interval_rejected(self) -> None:
        self.patch("tower", lambda d: d[0]["levels"][0].update(interval=0))
        with self.assertRaises(ConfigError) as ctx:
            load(self.dir, 1)
        self.assertIn("interval", str(ctx.exception))
        self.assertIn("tower.json", str(ctx.exception))

    def test_single_point_path_rejected(self) -> None:
        self.patch("map", lambda d: d.update(path=[[0, 4]]))
        with self.assertRaises(ConfigError) as ctx:
            load(self.dir, 1)
        self.assertIn("path", str(ctx.exception))

    def test_diagonal_path_rejected(self) -> None:
        self.patch("map", lambda d: d.update(path=[[0, 4], [3, 7]]))
        with self.assertRaises(ConfigError) as ctx:
            load(self.dir, 1)
        self.assertIn("同行或同列", str(ctx.exception))

    def test_out_of_bounds_path_rejected(self) -> None:
        self.patch("map", lambda d: d.update(path=[[0, 4], [99, 4]]))
        with self.assertRaises(ConfigError) as ctx:
            load(self.dir, 1)
        self.assertIn("越界", str(ctx.exception))

    def test_unknown_enemy_type_rejected(self) -> None:
        self.patch("wave", lambda d: d["waves"][0]["groups"][0].update(enemy_type="ghost"))
        with self.assertRaises(ConfigError) as ctx:
            load(self.dir, 1)
        self.assertIn("ghost", str(ctx.exception))

    def test_int_field_rejects_float(self) -> None:
        self.patch("tower", lambda d: d[0].update(cost=60.0))
        with self.assertRaises(ConfigError) as ctx:
            load(self.dir, 1)
        self.assertIn("cost", str(ctx.exception))

    def test_int_field_rejects_bool(self) -> None:
        self.patch("wave", lambda d: d.update(start_hp=True))
        with self.assertRaises(ConfigError):
            load(self.dir, 1)

    def test_upgrade_cost_must_end_with_zero(self) -> None:
        self.patch("tower", lambda d: d[0]["levels"][-1].update(upgrade_cost=10))
        with self.assertRaises(ConfigError) as ctx:
            load(self.dir, 1)
        self.assertIn("最后一级", str(ctx.exception))

    def test_missing_level_config(self) -> None:
        with self.assertRaises(ConfigError):
            load(self.dir, 9)

    def test_utf8_bom_tolerated(self) -> None:
        path = self.dir / "tower.json"
        path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8-sig")
        self.assertEqual(len(load(self.dir, 1)["towers"]), 2)


class TestCommandParsing(unittest.TestCase):
    """CONTRACT §3 / D12 / R1。"""

    def test_place_tower_ok(self) -> None:
        cmd = commands.parse('{"type":"place_tower","tower_type":"arrow","cell":[3,4]}')
        self.assertEqual(cmd["cell"], (3, 4))
        self.assertEqual(cmd["tower_type"], "arrow")

    def test_truncated_json_is_bad_json(self) -> None:
        with self.assertRaises(commands.CommandError) as ctx:
            commands.parse('{"type":"start"')
        self.assertEqual(ctx.exception.code, "bad_json")

    def test_non_object_line_is_bad_json(self) -> None:
        with self.assertRaises(commands.CommandError) as ctx:
            commands.parse("[1,2,3]")
        self.assertEqual(ctx.exception.code, "bad_json")

    def test_unknown_type(self) -> None:
        with self.assertRaises(commands.CommandError) as ctx:
            commands.parse('{"type":"nuke"}')
        self.assertEqual(ctx.exception.code, "bad_command")

    def test_missing_cell(self) -> None:
        with self.assertRaises(commands.CommandError):
            commands.parse('{"type":"place_tower","tower_type":"arrow"}')

    def test_cell_must_be_ints(self) -> None:
        with self.assertRaises(commands.CommandError):
            commands.parse('{"type":"place_tower","tower_type":"arrow","cell":["3",4]}')

    def test_bool_is_not_int(self) -> None:
        with self.assertRaises(commands.CommandError):
            commands.parse('{"type":"start","level_id":true}')

    def test_speed_range(self) -> None:
        self.assertEqual(commands.parse('{"type":"set_speed","value":3}')["value"], 3)
        with self.assertRaises(commands.CommandError):
            commands.parse('{"type":"set_speed","value":4}')


class TestEventsAndSnapshot(unittest.TestCase):
    """CONTRACT §3.1 / §3.2 的字段名。"""

    def test_event_fields(self) -> None:
        self.assertEqual(events.info("too_poor", 3, cell=(1, 2))["cell"], [1, 2])
        payload = events.result(9, True, 5, 1, 30, 18, 9)
        for key in ("win", "kills", "leaks", "gold_left", "hp_left", "duration_ticks"):
            self.assertIn(key, payload)
        self.assertEqual(events.engine_error("boom")["type"], "engine_error")

    def test_snapshot_is_compact_and_rounded(self) -> None:
        tower = SimpleNamespace(id=3, type="arrow", cell=(2, 4), level=1)
        enemy = SimpleNamespace(id=7, type="grunt", s=1.23456, hp=9.876, max_hp=10.0)
        bullet = SimpleNamespace(id=11, x=1.239, y=2.0, target_id=7)
        world = SimpleNamespace(
            tick=5,
            gold=10,
            hp=20,
            wave_index=1,
            paused=False,
            speed=1,
            towers={3: tower},
            enemies=[enemy],
            bullets=[bullet],
            path=SimpleNamespace(pos_at=lambda s: (s, s * 2)),
        )

        state = snapshot(world)

        self.assertEqual(state["type"], "state")
        self.assertEqual(state["towers"], [[3, "arrow", 2, 4, 1]])
        self.assertEqual(state["enemies"], [[7, "grunt", 1.23, 2.47, 9.88, 10.0]])
        self.assertEqual(state["bullets"], [[11, 1.24, 2.0, 7]])


class TestIsOver(unittest.TestCase):
    """CONTRACT D8。"""

    def _world(self, **kwargs):
        base = dict(
            phase=Phase.RUNNING,
            hp=10,
            wave_index=0,
            cfg={"waves": {"waves": [{}, {}, {}]}},
            enemies=[],
            bullets=[],
        )
        base.update(kwargs)
        return SimpleNamespace(**base)

    def test_running(self) -> None:
        self.assertEqual(loop.is_over(self._world()), (False, ""))

    def test_lose_when_hp_zero(self) -> None:
        self.assertEqual(loop.is_over(self._world(hp=0)), (True, "LOSE"))

    def test_win_after_last_wave_cleared(self) -> None:
        self.assertEqual(loop.is_over(self._world(wave_index=3)), (True, "WIN"))

    def test_not_win_with_enemies_left(self) -> None:
        world = self._world(wave_index=3, enemies=[SimpleNamespace()])
        self.assertEqual(loop.is_over(world), (False, ""))


class TestStdioLifecycle(unittest.TestCase):
    """CONTRACT B2 / B3 / B4 / B6 / I1 / I4 / R1 / R3。"""

    def run_engine(self, payload: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "engine.main", "--stdio", *args],
            cwd=str(ROOT),
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    @staticmethod
    def parse_lines(stdout: str) -> list[dict]:
        lines = [line for line in stdout.splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    def test_handshake_and_exit(self) -> None:
        result = self.run_engine('{"type":"HELLO"}\n{"type":"exit"}\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        messages = self.parse_lines(result.stdout)
        self.assertEqual(messages[0]["type"], "HELLO_ACK")
        self.assertEqual(messages[0]["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(messages[-1]["type"], "BYE")

    def test_stdout_is_pure_json_without_cr(self) -> None:
        result = self.run_engine('{"type":"HELLO"}\n{"type":"exit"}\n', "-v")
        self.assertNotIn("\r", result.stdout)
        for line in result.stdout.splitlines():
            if line.strip():
                json.loads(line)  # 任何非 JSON 行都会让这里抛异常

    def test_garbage_line_does_not_crash(self) -> None:
        result = self.run_engine('{"type":"start"\n{"type":"HELLO"}\n{"type":"exit"}\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        types = [msg["type"] for msg in self.parse_lines(result.stdout)]
        self.assertIn("HELLO_ACK", types)

    def test_too_many_bad_lines_exits_with_engine_error(self) -> None:
        result = self.run_engine("{bad\n" * 10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.parse_lines(result.stdout)[-1]["code"], "bad_stream")

    def test_gameplay_command_before_start_rejected(self) -> None:
        result = self.run_engine(
            '{"type":"place_tower","tower_type":"arrow","cell":[3,4]}\n{"type":"exit"}\n'
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        messages = self.parse_lines(result.stdout)
        self.assertEqual(messages[0]["type"], "info")
        self.assertEqual(messages[0]["code"], "bad_command")

    def test_eof_without_exit_still_quits(self) -> None:
        result = self.run_engine('{"type":"HELLO"}\n')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_start_sends_map_and_config(self) -> None:
        result = self.run_engine('{"type":"start","level_id":1}\n{"type":"exit"}\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        messages = self.parse_lines(result.stdout)
        types = [msg["type"] for msg in messages]
        self.assertIn("map", types)
        self.assertIn("config", types)

        map_msg = messages[types.index("map")]
        self.assertEqual(map_msg["name"], "第一关·林间小道")
        self.assertEqual(map_msg["grid"], {"width": 16, "height": 10})

        config_msg = messages[types.index("config")]
        self.assertEqual({tower["icon"] for tower in config_msg["towers"]}, {"tower_arrow", "tower_slow"})
        self.assertTrue(all("cost" in tower for tower in config_msg["towers"]))

    def test_headless_fails_cleanly_while_unimplemented(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "engine.main", "--headless", "--level", "1"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        self.assertIn(result.returncode, (0, 1))
        self.assertNotIn("Traceback", result.stderr)
        finished = "WIN" in result.stdout or "LOSE" in result.stdout
        self.assertTrue(finished or "未实现" in result.stderr)


class TestHeadlessConfigError(unittest.TestCase):
    def test_bad_config_exits_with_code_2(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        for path in CONFIG_DIR.glob("*.json"):
            shutil.copy(path, Path(tmp) / path.name)
        wave_path = Path(tmp) / "wave.json"
        data = json.loads(wave_path.read_text(encoding="utf-8"))
        data["waves"][0]["groups"][0]["speed"] = 1
        data["waves"][0]["groups"][0].pop("interval")
        wave_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "engine.main", "--headless", "--config-dir", tmp],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("配置错误", result.stderr)


if __name__ == "__main__":
    unittest.main()
