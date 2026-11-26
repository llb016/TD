# 引擎层内部契约（逻辑组）

> 适用范围：**仅逻辑组两人（L1 战斗线 / L2 驱动线）之间的接口与数据约定。**
> 状态：草案 v0.1 —— 第 1 天两人逐条勾选确认后冻结为 v1.0，之后**只加不改**。
> 修改方式：改本文件 + 改 `tests/test_contract.py`，两人 review 后当次合并。

---

## 0. 角色与边界

| 角色 | 负责 | 只读/不碰 |
|---|---|---|
| **L1 战斗线** | `core/grid.py`、`core/path.py`、`core/entities/*`、`core/combat.py` | 主循环、波次、金币生命胜负、配置加载、JSON 组织 |
| **L2 驱动线** | `main.py`、`core/loop.py`、`core/world.py`、`core/waves.py`、`core/config.py`、`protocol/*`、`tools/*` | 索敌算法、伤害公式、路径推进数学 |

阶段验收：`python -m engine.main --headless --level 1` 跑完 3 波，打印 `WIN` / `LOSE` 与金币、剩余生命。

---

## 1. 必须第 1 天定完的决策

每条的「确认」列由两人签字（`√`），全部确认即冻结。

| # | 决策项 | 约定值 | 确认 |
|---|---|---|---|
| D1 | **单位制** | 距离=格子，时间=秒；射程/速度/伤害/血量全部用格与秒，配置里不出现像素与毫秒 | ☐ |
| D2 | **敌人位置表示** | 敌人只存 **已行驶距离 `s`（float，单位：格）** + 路径引用；屏幕坐标只能由 `path.pos_at(s)` 得到，不缓存 x/y 作为事实来源 | ☐ |
| D3 | **时间步长与倍速** | 固定 `DT = 1.0 / 30`；倍速 N = 每帧对 world 调用 N 次 `tick`，**禁止**放大 dt | ☐ |
| D4 | **tick 内部顺序** | ①指令入队 ②敌人移动 ③塔索敌开火 ④子弹推进与命中 ⑤死亡/漏怪清理 ⑥波次推进 ⑦发出事件 ⑧输出快照 | ☐ |
| D5 | **实体 ID** | `World` 统一发号，单调递增 int，全局唯一，永不复用；塔/敌人/子弹共用一个计数器 | ☐ |
| D6 | **索敌与命中** | 射程判定 `dist <= range`（取开方后的真实距离，含边界）；默认目标 = **路径最靠前**的敌人（`s` 最大）；子弹**追踪必中**，不做弹道碰撞与闪避 | ☐ |
| D7 | **建塔/升级/出售归属** | 合法性判定（在可建格、未被占用、塔存在、金币足够）**在 L1**；**金币扣减与返还入账在 L2**；L1 返回 `ok / 拒绝原因`，L2 落账 | ☐ |
| D8 | **胜负定义** | 漏怪扣血，`hp <= 0` 立即 `LOSE` 并终止后续 tick；所有波次刷完且场上敌人为 0 且未被提前判负 → `WIN` | ☐ |
| D9 | **配置 schema** | 四份 JSON：`map / tower / enemy / wave`，字段名与单位见第 4 节；缺必填字段 → 抛 `ConfigError(file, path, reason)`，**必须指出文件名与字段路径** | ☐ |
| D10 | **事件与快照顺序** | 同一 tick 内**先发事件、后发快照**；事件不可丢，快照可丢（界面只取最新一帧） | ☐ |
| D11 | **随机性** | 全程只有一个 `random.Random(seed)`，由 `World` 持有；seed 来自 `--seed`，默认 `0`；禁止模块级 `random` 直接调用 | ☐ |
| D12 | **非法指令处理** | L2 在 `commands.py` 校验：缺字段 / 越界 / 类型错 / 未知类型 → 记 warning 日志并**丢弃该条，不崩** | ☐ |
| D13 | **接口签名** | 第 2 节的签名冻结；新增只能用可选参数或新增函数，**不改名、不改参数顺序** | ☐ |

---

## 2. 内部接口签名（冻结项）

```python
# ============ L1 对外提供（L2 调用） ============
class Grid:
    width: int
    height: int
    def in_bounds(self, cell) -> bool
    def is_buildable(self, cell) -> bool          # 在界内、非路面、未被占用
    def occupy(self, cell, entity_id) -> None
    def release(self, cell) -> None
    def occupant(self, cell) -> int | None

class Path:
    def __init__(self, points: list[tuple[int, int]])
    length: float                                  # 总长度，单位：格
    def pos_at(self, s: float) -> tuple[float, float]   # 已夹取到 [0, length]；返回**格子中心坐标**（格索引 + 0.5）
    def clamp(self, s: float) -> float

class Enemy:
    id: int; type: str; hp: float; max_hp: float
    speed: float; s: float; alive: bool
    def step(self, dt: float, path: Path) -> bool  # True=仍在路上, False=抵达终点(漏怪)

class Tower:
    id: int; type: str; cell: tuple[int, int]; level: int
    def target(self, enemies) -> Enemy | None      # D6 规则
    def upgrade(self) -> bool                      # 已满级返回 False

def resolve(world, dt: float) -> list[Event]       # 索敌→开火→子弹推进→命中扣血→击杀
def place_tower(world, tower_type: str, cell) -> tuple[bool, str]   # (ok, 原因)
def upgrade_tower(world, tower_id: int) -> tuple[bool, str, int]    # 第三项=消耗金币
def sell_tower(world, tower_id: int) -> tuple[bool, str, int]       # 第三项=返还金币

# ============ L2 对外提供（L1 依赖） ============
class Config:
    @staticmethod
    def load(dir_path) -> dict                     # 四份配置合并为 dict，失败抛 ConfigError
class World:
    @staticmethod
    def create(level_id: int, cfg: dict, seed: int) -> World
    grid: Grid; path: Path; rng: random.Random
    gold: int; hp: int; wave_index: int
    towers: dict[int, Tower]; enemies: list[Enemy]; bullets: list[Bullet]
    events: list[Event]                            # 本 tick 产生，末尾清空
    def next_id(self) -> int

def tick(world) -> None                            # 完整一步，顺序按 D4
def is_over(world) -> tuple[bool, str]             # (结束?, "WIN" | "LOSE" | "")
def snapshot(world) -> dict                        # 每帧状态
def event_to_msg(e) -> dict                        # 单个事件 → 消息
```

`Event` 形状（两线共用，L1 只 `append`，L2 只序列化）：

```python
Event = {"type": str, "tick": int, ...}   # type ∈ kill | leak | wave | result | gold | info
```

---

## 3. 消息与指令名（与桥接组对齐后即冻结）

指令（界面 → 引擎）：

| type | 参数 | 说明 |
|---|---|---|
| `start` | `level_id: int` | 开局 |
| `place_tower` | `tower_type: str`, `cell: [x, y]` | 建塔 |
| `upgrade_tower` | `tower_id: int` | 升级 |
| `sell_tower` | `tower_id: int` | 出售 |
| `next_wave` | `wave_index: int` | 立即开下一波 |
| `set_speed` | `value: int` | 1 / 2 / 3 |
| `pause` / `resume` | — | 暂停 / 继续 |
| `exit` | — | 退出 |

引擎 → 界面：`map`（开局一次）、`config`（开局一次）、`state`（每帧快照）、`event`（`kill/leak/wave/result/gold/info`）。

### 3.1 每帧快照 `state`（字段名冻结，只增不改）

坐标一律为**格子中心**浮点，保留 2 位小数（减少体量）；`type` 是配置里的逻辑键，界面自行映射图标与名称。

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | str | 固定 `"state"` |
| `tick` | int | 单调递增，暂停时不增长 |
| `gold` / `hp` | int | 当前金币 / 剩余生命 |
| `wave` | int | 当前波次，`0` = 尚未开始 |
| `paused` | bool | 是否暂停 |
| `speed` | int | 1 / 2 / 3 |
| `towers` | 紧凑数组 | `[id, type, x, y, level]` |
| `enemies` | 紧凑数组 | `[id, type, x, y, hp, max_hp]` |
| `bullets` | 紧凑数组 | `[id, x, y, target_id]` |

### 3.2 事件负载 `event`

| type | 附加字段 | 触发时机 |
|---|---|---|
| `kill` | `enemy_id`, `enemy_type`, `gold`, `x`, `y` | 敌人被击杀 |
| `leak` | `enemy_id`, `enemy_type`, `hp_damage`, `hp_left` | 敌人抵达终点 |
| `wave` | `wave`, `total` | 新一波开始 |
| `result` | `win`(bool), `kills`, `leaks`, `gold_left`, `hp_left`, `duration_ticks` | 一局结束 |
| `gold` | `delta`, `total` | 金币变化（建塔/升级/出售/击杀） |
| `info` | `code`, `cell`(可选) | 非法或失败的指令，`code ∈ too_poor / occupied / blocked / no_tower / max_level / bad_command` |
| `engine_error` | `msg` | 顶层异常，发出后以退出码 1 结束进程 |

---

## 4. 四份配置的字段表

统一约定：键名 `snake_case`；数值单位见 D1；未标注的字段为必填。

### 4.1 `config/map.json`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int | 关卡编号，`--level` 对应此值 |
| `name` | str | 显示名 |
| `grid.width` / `grid.height` | int | **格子从 0 开始计数**，宽高为格数 |
| `path` | `[[x, y], ...]` | 折线顶点，含起点与终点，可含直角折点；相邻点须同行或同列 |
| `blocked` | `[[x, y], ...]` | 可选，额外不可建格（装饰/障碍） |

> 派生出：`Path.length`、`start_cell = path[0]`、`end_cell = path[-1]`。

### 4.2 `config/tower.json`

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | str | 唯一键，如 `arrow` / `slow` |
| `name` | str | 显示名 |
| `icon` | str | 图标逻辑键，如 `tower_arrow`；**引擎不使用**，仅原样下发给界面由其映射资源 |
| `cost` | int | 建造价 |
| `projectile_speed` | float | 格/秒；`0` 表示瞬中（无子弹飞行） |
| `levels` | list | 每级一项，索引 0 = 1 级 |
| `levels[].damage` | float | 单发伤害 |
| `levels[].range` | float | 射程（格） |
| `levels[].interval` | float | 攻击间隔（秒） |
| `levels[].upgrade_cost` | int | 升到 **下一级** 的价格；最后一级填 `0` |
| `effect` | dict | `{"kind": "single"}` 或 `{"kind": "slow", "factor": 0.5, "duration": 1.5}` |

### 4.3 `config/enemy.json`

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | str | 唯一键，如 `grunt` / `runner` |
| `name` | str | 显示名 |
| `icon` | str | 图标逻辑键，如 `enemy_grunt`；同 `tower.json`，引擎不使用 |
| `hp` | float | 最大生命 |
| `speed` | float | 格/秒 |
| `leak_damage` | int | 抵达终点扣的生命 |
| `gold_reward` | int | 击杀奖励金币 |
| `armor` | float | 可选，默认 `0`；实际伤害 = `max(damage - armor, 0)` |

### 4.4 `config/wave.json`

| 字段 | 类型 | 说明 |
|---|---|---|
| `level_id` | int | 所属关卡 |
| `start_gold` | int | 开局金币 |
| `start_hp` | int | 开局生命 |
| `waves` | list | 按顺序，长度 = 波数（首版 3） |
| `waves[].groups` | list | 本波出怪组，组间可并行 |
| `waves[].groups[].enemy_type` | str | 对应 `enemy.json` 的 `type` |
| `waves[].groups[].count` | int | 数量 |
| `waves[].groups[].interval` | float | 同组相邻两只的间隔（秒） |
| `waves[].groups[].delay` | float | 本组相对本波开始的延迟（秒） |

---

## 5. 需与其它组确认（逻辑组只确认，不决策）

完整清单见 [docs/TEAM_INTERFACE.md](../docs/TEAM_INTERFACE.md)。本节只列与本契约字段直接相关的三条：

1. 消息类型、字段命名与第 3.1/3.2 节的结构 —— 三组确认后冻结。
2. 引擎只输出**格子坐标**（原点左上，格子从 0 开始，取格子中心），像素换算只在界面侧单一函数内完成。
3. 每行一条 JSON，Python 侧必须 `print(..., flush=True)`；stdout 只放协议行，日志走 stderr。

---

## 6. 待定项（第 2 周结束前必须冻结）

- [ ] 全部数值表（塔/敌/波的平衡值）
- [ ] 地图路径点最终坐标
- [x] 快照字段名与布局 —— 已定，见 §3.1（紧凑数组）
- [x] 日志行格式 —— 已定，见 §8 的 I11
- [ ] 快照裁剪阈值：**先全量发送**，单帧 >16KB 或单 tick >5ms 时再改动（改动须走 §7）
- [ ] 无界面跑分参数：`--headless --level N --seed N --script FILE`

---

## 7. 变更流程

1. 提改动的人改本文件，并把 `tests/test_contract.py` 同步改成**先红**。
2. 另一人 review，通过后合并，契约版本号 +0.1。
3. 合并当天更新受影响的调用方，不允许「先合并、明天再改对面」。

---

## 8. 工程与流程约定

### 8.1 P0（不定就必然出事故）

| # | 约定 | 约定值 | 确认 |
|---|---|---|---|
| I1 | **stdout 独占** | 引擎 stdout **只允许协议 JSON 行**；调试与日志走 `stderr`，或 `--log FILE` 写文件。禁止任何裸 `print` 出现在非协议路径 | ☐ |
| I2 | **启动方式** | 统一 `python -m engine.main`，工作目录=项目根；`engine/` 是包（有 `__init__.py`）；禁止 `python engine/main.py` | ☐ |
| I3 | **配置路径解析** | 一律 `Path(__file__).parent / "config"`，不依赖当前工作目录 | ☐ |
| I4 | **退出码与终止** | `0` 正常（`exit` / 判负后 / stdin EOF）；`1` 未捕获异常（traceback→stderr）；`2` 配置错误；**stdin EOF 一律视为退出** | ☐ |
| I5 | **暂停与倍速语义** | 暂停：不推进战斗与波次、`tick` 不增长，但**仍处理指令**；倍速 N：每帧调用 N 次 `tick`，`dt` 恒为 `1/30` | ☐ |
| I6 | **删除时机** | 死亡/移除先收集到 `to_remove`，只在 D4 第⑤步统一清理；禁止遍历中删列表 | ☐ |
| I7 | **测试与合并门槛** | 只用标准库 `unittest`；命令 `python -m unittest discover -s tests`；**全绿才允许合并** | ☐ |
| I8 | **换行与编码** | UTF-8 无 BOM、`\n` 换行；仓库根加 `.gitattributes`（`* text=auto eol=lf`） | ☐ |

### 8.2 P1（第 1 周内说清）

| # | 约定 | 约定值 | 确认 |
|---|---|---|---|
| I9 | 性能预算 | 单 tick < 5ms；首版上限 100 敌人 / 30 塔 / 60 子弹；不做空间分桶、不做对象池 | ☐ |
| I10 | 快照策略 | 先每 tick 全量；超阈值再优化（见 §6），不做提前增量 | ☐ |
| I11 | 日志格式 | `[tick=N] type key=value key=value`，一行一条，默认关闭，`--log FILE` 开启 | ☐ |
| I12 | 命名映射 | 配置键 = Python 属性 = JSON 字段，全 `snake_case`，**不做 camelCase 转换层** | ☐ |
| I13 | 提交规范 | 前缀 `L1:` / `L2:`；分支 `feat/l1-combat`、`feat/l2-loop`；每天合并一次 | ☐ |
| I14 | 目录互不越界 | 只改自己名下的文件（见 §0）；要动对方的走 §7 | ☐ |
| I15 | 每日同步 | 每天 10 分钟：昨天完成 / 今天计划 / 阻塞点；冲突当天解决 | ☐ |

---

## 9. 运行时健壮性（防崩清单）

§1 定的是「语义」，这一节定的是「边界情况下的行为」。每条都要在代码里落实，否则会出现「约定对了但程序还是崩」。

| # | 场景 | 约定值 | 责任方 | 确认 |
|---|---|---|---|---|
| R1 | 界面发来非法行（截断、非 JSON、非对象） | `except json.JSONDecodeError` → 记 warning 并**丢弃该行**（`bad_json` 不回包）；**连续 10 条**异常行则发 `{"type":"engine_error","code":"bad_stream"}` 并以退出码 1 结束 | L2 | ☐ |
| R2 | Windows 下中文输出 | 启动即 `sys.stdin/stdout/stderr.reconfigure(encoding="utf-8", newline="\n")`；`json.dumps(..., ensure_ascii=False)`；日志一律走 stderr | L2 | ☐ |
| R3 | 未开局就收到玩法指令 | `IDLE` 只接受 `HELLO / start / exit`；其余回 `info{code:"bad_command"}`，**不创建 world、不访问它的属性** | L2 | ☐ |
| R4 | 一局结束后继续 tick 或发指令 | `OVER` 禁止 `tick`；只接受 `start / exit`；`result` 事件只发一次 | L2 | ☐ |
| R5 | 配置写错 | 按 §9.1 清单校验；失败抛 `ConfigError(file, path, reason)`，**启动即失败（退出码 2）**，不带病运行 | L2 | ☐ |
| R6 | 数值下限 | `interval / speed / hp / range > 0`；`count ≥ 1`；`cost / damage / leak_damage / gold_reward / armor / delay ≥ 0`；`upgrade_cost` 最后一级必须为 0 | L2 | ☐ |
| R7 | 快照体积 | 坐标与血量固定保留 2 位小数；单帧 >16KB 时**先记录、不改代码**，按 §7 提案后再改 | L2 | ☐ |
| R8 | stderr 混入协议流 | 桥接层必须 `setProcessChannelMode(SeparateChannels)`；引擎侧 stdout 只写协议行（双重保险） | 桥接组 + L2 | ☐ |

### 9.1 配置校验清单（R5）

- **map**：`grid.width/height > 0`；`path` 至少 2 点、全为 `(int, int)`、在界内、**相邻点必须同行或同列**且不重合；`blocked` 在界内。
- **tower**：`type` 唯一；`levels` 非空；每级 `range > 0`、`interval > 0`、`damage ≥ 0`；`upgrade_cost` 为 int 且最后一级为 `0`；`effect.kind ∈ {single, slow}`，slow 需 `0 < factor ≤ 1`、`duration > 0`。
- **enemy**：`type` 唯一；`hp > 0`、`speed > 0`；`armor` 可选且 `≥ 0`。
- **wave**：`start_hp > 0`、`start_gold ≥ 0`；`waves` 非空；每组 `count ≥ 1`、`interval > 0`、`delay ≥ 0`；`enemy_type` **必须存在于 enemy.json**。
- 所有数值字段拒绝 `bool`（`True` 不是整数）；整数字段拒绝 `1.0` 这类浮点写法。

### 9.2 骨架期临时约定

骨架阶段（v0.1）L1/L2 算法未实现时，引擎对相关指令回 `info{code:"not_implemented"}`：**不崩溃、不退出、进程继续服务**。该 code 属于临时项，v1.0 前删除。

---

## 10. 玩法细则（K1–K6，开工前必须确认）

这 6 条与 §1 的"接口语义"不同：它们决定**游戏怎么跑**，而且是两条线都必须知道的规则。不定就各写一套。

| # | 问题 | 约定值 | 归属 | 确认 |
|---|---|---|---|---|
| K1 | `pos_at(s)` 返回哪种坐标 | **返回格子中心坐标 = 格索引 + 0.5**。首点 `(0, 4)` → `pos_at(0) == (0.5, 4.5)`；末端同理。界面侧换算只有 `pixel = origin + coord * cell_size`，**引擎不再做任何 +0.5** | L1 | ☐ |
| K2 | 下一波怎么来 | **自动推进**：本波出怪完毕 **且** 场上敌人为 0（子弹不计）→ 延迟 **3.0 秒**自动开下一波；`next_wave` 是**提前开**（跳过剩余等待，不叠加波次）。计时在 `waves.advance` | L2 | ☐ |
| K3 | 出售返还多少 | `refund = floor((建造价 + 已花升级价) * 0.6)`；出售同时释放占格、移除该塔；L1 计算，L2 入账并加 `gold` 事件 | L1 算 / L2 入账 | ☐ |
| K4 | 减速叠加规则 | **不叠加**：同一敌人只保留一个减速效果，`factor` 取更小者，`duration` 刷新为两者较大值；禁止乘算、禁止多段并存 | L1 | ☐ |
| K5 | 敌人之间是否阻挡 | **不碰撞、可重叠**（与"塔和敌人不互相阻挡"一致）；同一 `s` 允许多只；索敌仍取 `s` 最大者 | L1 | ☐ |
| K6 | 事件里的 `tick` 语义 | `tick` 从 **1** 开始单调递增；事件中的 `tick` = **产生该事件的那一步编号**（`loop` 先 `+1` 再跑）；暂停期间不产生任何事件 | L2 | ☐ |

### 10.1 塔的冷却细则

- **建成即可开火**：新建塔的冷却初值为 0。
- **升级不重置冷却**：升级只换伤害/射程/间隔，不刷新已累积的冷却（防通过反复升级刷伤害）。
- 已满级再执行 `upgrade_tower` → 回 `info{code:"max_level"}`，不改金币。

### 10.2 变更说明

K 系列都是"改数值/改体验"的高频项，但**改动只能走 §7**：先改本节与 `tests/test_contract.py`，再改实现。任何情况下不允许只改代码不改本节——否则下一个人按旧规则写测试，就会出现"两个人都对、合起来是错"的局面。
