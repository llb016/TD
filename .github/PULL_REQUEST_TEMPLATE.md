## 这个 PR 做了什么

<!-- 一段话说明，关联 issue 用 #编号 -->

## 自检（必须全勾，CI 会再验一遍测试）

- [ ] 在项目根跑过 `python -B -m unittest discover -s tests`，全绿
- [ ] stdout 只放协议 JSON 行，没有留下裸 `print()` 或调试输出
- [ ] 改了 `engine/config/*.json` → 附一次 `python -m engine.main --headless --level 1` 的结果
- [ ] 改了 `engine/CONTRACT.md` → 同步改了 `tests/test_contract.py`
- [ ] 改动涉及别人的文件 → 已在群里说明并得到同意

## 影响范围

<!-- 勾选受影响的部分 -->

- [ ] 引擎逻辑
- [ ] 协议字段（会影响界面组 / 搭桥组，需三组确认）
- [ ] 配置文件字段或数值
- [ ] 文档
