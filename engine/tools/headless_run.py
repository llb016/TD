"""命令行跑分工具（CONTRACT §6 / 阶段验收）。

    python -m engine.tools.headless_run --level 1 --seed 0
"""

from __future__ import annotations

import sys

from ..main import main


def run(argv=None) -> int:
    """参数原样转发给 --headless 模式，避免两处解析规则不一致。"""
    args = list(sys.argv[1:] if argv is None else argv)
    return main(["--headless", *args])


if __name__ == "__main__":
    sys.exit(run())
