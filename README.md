# Qt 塔防大作业

桌面塔防游戏：Qt 做界面，Python 做游戏逻辑，中间由桥接层按行传 JSON 把两边连起来。

目标是先跑通最小闭环：**1 张地图、2 种塔、2 种敌人、3 波**，跑通之后靠改配置加内容，不改代码。
完整分工、时间线与协作规则见课程下发的团队分工大纲（**不在本仓库内**，向组长索取）。

---

## 目录结构

```
engine/                  游戏引擎（Python，只用标准库）
  main.py                入口：stdio 模式与 headless 模式
  CONTRACT.md            引擎内部契约（接口签名、配置字段、健壮性、玩法细则）
  config/                四份配置：map / tower / enemy / wave
  core/                  世界状态、主循环、波次、地图几何、实体、战斗、配置校验
  protocol/              指令解析、事件、每帧快照
  tools/                 命令行工具
docs/
  TEAM_INTERFACE.md      三组之间的接口约定（坐标语义、进程生命周期、退出语义）
tests/
  test_contract.py       契约测试：把 CONTRACT.md 的约定变成可执行断言
```

---

## 环境

| 项 | 版本 | 说明 |
|---|---|---|
| Python | **3.10 及以上**（实测 3.12） | 引擎不使用任何第三方库，无需 `pip install` |
| 操作系统 | Windows / Linux / macOS | 仓库统一 LF 换行（见 `.gitattributes`） |
| Qt | 待界面组填写 | 三组保持一致 |

## 快速开始

在**项目根目录**执行（不要在 `engine/` 里执行）：

```bash
# 1. 跑契约测试，全绿才算环境通了
python -B -m unittest discover -s tests

# 2. 以 stdio 模式启动引擎（界面/桥接层用的就是这个）
python -m engine.main --stdio

# 3. 命令行跑分：不开界面跑完 3 波，打印 WIN / LOSE
python -m engine.main --headless --level 1 --seed 0

# 4. 不知道协议怎么发？用回放工具把一串指令喂给引擎并打印响应
python -m engine.tools.stdio_replay
```

## 引擎用法

### stdio 模式（与界面通信）

每行一条 JSON，从 stdin 读指令、往 stdout 写消息。**stdout 只放协议行**，日志一律走 stderr。

```bash
echo '{"type":"HELLO"}' | python -m engine.main --stdio
# {"type":"HELLO_ACK","protocol_version":1,"engine_version":"0.1.0"}
```

指令与消息的字段见 [docs/TEAM_INTERFACE.md](./docs/TEAM_INTERFACE.md) 与 [engine/CONTRACT.md](./engine/CONTRACT.md) §3。

### headless 模式（不开界面跑分）

```bash
python -m engine.main --headless --level 1 --seed 0 --max-ticks 20000
```

固定 `--seed` 可复现同一局结果；`--log FILE` 把日志写到文件，便于三方按 tick 对账。

### 常用参数

| 参数 | 说明 |
|---|---|
| `--level N` | 关卡编号，对应 `engine/config/map.json` 的 `id` |
| `--seed N` | 随机种子，默认 0（可复现） |
| `--config-dir DIR` | 配置目录，默认 `engine/config` |
| `--log FILE` | 日志写文件（默认 stderr） |
| `-v` | 打开 debug 日志 |

退出码：`0` 正常 / `1` 未捕获异常 / `2` 配置错误（详见 CONTRACT §8 的 I4）。

---

## 当前进度

| 模块 | 状态 |
|---|---|
| 协议层（指令解析、事件、快照）、配置加载与校验、入口与状态机、无界面工具 | 可用 |
| 契约测试 | 39 项全绿 |
| 地图几何、实体、战斗结算 | 待实现（`raise NotImplementedError`，消息里标注归属） |
| 波次刷怪、金币落账、30 帧输出节拍 | 待实现 |

桩函数全部带 `L1 待实现：…` / `L2 待实现：…` 前缀，用一条命令就能列出剩余工作量：

```bash
# Linux / macOS / Git Bash
grep -rn "待实现" engine/
```

```powershell
# PowerShell
Get-ChildItem -Recurse engine -Filter *.py | Select-String "待实现"
```

---

## 协作规则

1. **先定协议再写码**：接口没冻结前不写依赖对方的代码。
2. **每天合并一次**：在各自分支开发，当天合并到 `main`，冲突当天解决。
3. **合并前必须跑测试**：`python -B -m unittest discover -s tests` 全绿；CI 也会再跑一遍。
4. **数值进配置**：塔、敌人、波次的数值只放 `engine/config/*.json`，加内容不改代码。
5. **契约变更走流程**：改 `engine/CONTRACT.md` 必须同时改 `tests/test_contract.py`，并经另一人 review。
6. **图片先不用管**：第一版用色块和简单图形，跑通了再考虑美术。
