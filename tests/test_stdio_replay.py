"""回放工具自身可用性测试：避免工具随引擎演进悄悄失效。"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestStdioReplay(unittest.TestCase):
    def test_builtin_scenario_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", "-m", "engine.tools.stdio_replay", "--quiet"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HELLO_ACK", result.stdout + result.stderr)

    def test_script_file_is_read(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "engine.tools.stdio_replay",
                "--quiet",
                "--script",
                "tests/data/hello_only.jsonl",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BYE", result.stdout)


if __name__ == "__main__":
    unittest.main()
