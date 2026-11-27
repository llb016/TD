"""按脚本回放：把一串指令喂给引擎，逐条打印响应。

用途：不写 Qt 也能自测协议；联调出分歧时，三方跑同一条脚本对账。

    python -m engine.tools.stdio_replay                    # 内置场景
    python -m engine.tools.stdio_replay --script s.jsonl   # 自定义脚本
    python -m engine.tools.stdio_replay --quiet            # 只输出摘要，适合 CI

脚本格式：每行一条 JSON 指令；空行与 `#` 开头的行会被忽略。

退出码：0 = 全部正常；1 = 有非 JSON 输出、引擎异常退出或超时。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_LINES = 2000

DEFAULT_SCRIPT = """\
# 握手 → 开局 → 未开局/非法指令 → 退出
{"type":"HELLO"}
{"type":"start","level_id":1}
{"type":"place_tower","tower_type":"arrow","cell":[3,4]}
{"type":"pause"}
{"type":"exit"}
"""


def read_script(path) -> list[str]:
    text = DEFAULT_SCRIPT if path is None else Path(path).read_text(encoding="utf-8-sig")
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


class Replay:
    def __init__(self, commands: list[str], extra_args: list[str], quiet: bool, delay: float) -> None:
        self.commands = commands
        self.extra_args = extra_args
        self.quiet = quiet
        self.delay = delay
        self.responses: list[dict] = []
        self.bad_lines: list[str] = []
        self._lock = threading.Lock()

    def say(self, text: str) -> None:
        if not self.quiet:
            print(text, flush=True)

    def _pump(self, stream) -> None:
        """后台读取引擎 stdout，避免管道写满造成死锁。"""
        for raw in stream:
            line = raw.rstrip("\n")
            if not line:
                continue
            with self._lock:
                if len(self.responses) + len(self.bad_lines) < MAX_LINES:
                    try:
                        self.responses.append(json.loads(line))
                    except json.JSONDecodeError:
                        self.bad_lines.append(line)
            self.say(f"  <- {line}")

    def run(self) -> int:
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        cmd = [sys.executable, "-B", "-m", "engine.main", "--stdio", *self.extra_args]
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        reader = threading.Thread(target=self._pump, args=(proc.stdout,), daemon=True)
        reader.start()

        for command in self.commands:
            self.say(f"  -> {command}")
            try:
                proc.stdin.write(command + "\n")
                proc.stdin.flush()
            except (BrokenPipeError, ValueError):
                self.say("  !! 引擎已关闭 stdin，停止发送")
                break
            time.sleep(self.delay)

        try:
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            rc = -1

        reader.join(timeout=2)
        stderr = proc.stderr.read() if proc.stderr else ""

        # 摘要无论是否 --quiet 都要输出，CI 与 tests 都依赖它
        types = [msg.get("type", "?") for msg in self.responses]
        print("")
        print(f"发送 {len(self.commands)} 条，收到 {len(self.responses)} 条消息，"
              f"非法行 {len(self.bad_lines)} 条，退出码 {rc}")
        if types:
            print("消息类型：" + ", ".join(types))
        if stderr.strip():
            self.say("--- stderr ---")
            self.say(stderr.rstrip())

        failed = False
        if self.bad_lines:
            print("stdout 出现非 JSON 行（违反 CONTRACT I1）：", file=sys.stderr)
            for line in self.bad_lines:
                print(f"  {line}", file=sys.stderr)
            failed = True
        if rc != 0:
            print(f"引擎退出码为 {rc}，期望 0（CONTRACT I4）", file=sys.stderr)
            failed = True
        if not any(msg.get("type") == "HELLO_ACK" for msg in self.responses):
            print("没有收到 HELLO_ACK（CONTRACT B2）", file=sys.stderr)
            failed = True
        return 1 if failed else 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(prog="engine.tools.stdio_replay", description=__doc__.splitlines()[0])
    parser.add_argument("--script", help="指令脚本文件（每行一条 JSON）")
    parser.add_argument("--delay", type=float, default=0.05, help="每条指令间隔秒数，默认 0.05")
    parser.add_argument("--quiet", action="store_true", help="只输出摘要")
    parser.add_argument("--level", type=int, default=1, help="传给引擎的关卡编号")
    args = parser.parse_args(argv)

    commands = read_script(args.script)
    if not commands:
        print("脚本里没有指令", file=sys.stderr)
        return 1

    return Replay(commands, ["--level", str(args.level)], args.quiet, args.delay).run()


if __name__ == "__main__":
    sys.exit(main())
