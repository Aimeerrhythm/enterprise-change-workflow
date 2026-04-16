# ECW 提示词能力验证

ECW 插件的"逻辑"全部在 11 个 SKILL.md 提示词文件中（~34K tokens），不是传统可执行代码。本测试套件是一套三层递进验证体系，让每次提示词修改后能快速、可靠地发现破坏性变更。

---

# 第一部分：设计思路

## 核心挑战：提示词不是代码

传统代码测试的前提是**确定性**：同样的输入，函数永远返回同样的输出。提示词打破了这个前提：

| 维度 | 代码 | 提示词 |
|------|------|--------|
| 输出确定性 | 100%——同输入同输出 | 0%——同输入不同输出 |
| 可断言粒度 | 任意字段、任意精度 | 只能断言"决策维度"（等级、路由、分类） |
| 回归检测 | 单元测试可精确定位 | 语义偏移可能无明显症状 |
| 故障模式 | 编译/运行时报错 | 静默降级——路由错了但不报错 |

这意味着我们不能用传统方法（unit test、integration test、e2e test）照搬。需要一套专为提示词设计的验证体系。

## 架构决策：三层递进验证

经过 4 维度独立评审（可行性/成本、覆盖完整性、业界最佳实践、ECW 领域专项），最终方案分三层，**每层解决不同类型的故障**：

| 层级 | 内容 | 耗时 | 成本 | 可靠性 | 捕获的故障类型 |
|------|------|------|------|--------|---------------|
| **Layer 1** | Python 扫描 SKILL.md 结构完整性 | <3s | $0 | 100% | 结构破坏、引用断裂、路由缺失 |
| **Layer 1b** | pytest 测试 verify-completion.py | <10s | $0 | 100% | Hook 行为回归 |
| **Layer 2** | promptfoo + Claude API 验证路由决策 | 2-5min | ~$1-2 | 80-90% | 语义偏移、分类错误 |

**为什么三层都不可替代：**

- **Layer 1 不能替代 Layer 2**：静态检查只能验证"路由表里写了 spec-challenge"，不能验证"给定 PCI 合规需求，LLM 真的会分类为 P0 并路由到 spec-challenge"。
- **Layer 2 不能替代 Layer 1**：LLM 测试有 10-20% flake rate，且只覆盖 risk-classifier 一个 skill 的路由决策。Layer 1 覆盖全部 11 个 skill 的结构完整性，100% 确定性。
- **Layer 1b 独立存在**：verify-completion.py 是 ECW 唯一的可执行代码（448 行 Python），控制"能否标记任务完成"的 gate，需要自己的测试保护网。

**层间分工边界：**

```
Layer 1 回答：SKILL.md 的结构是否完整？（引用、路径、关键词、路由表）
Layer 1b 回答：Hook 代码的行为是否正确？（编译检查、引用检查、覆盖率检查）
Layer 2 回答：LLM 在该提示词下的路由决策是否正确？（给定输入 → 期望的分类和路由链）
```

## 关键设计决策

### 1. 为什么选 promptfoo 而不是自建 Python eval

| 对比项 | promptfoo | 自建 Python eval |
|--------|-----------|-----------------|
| assertion 引擎 | 内置 contains/regex/javascript/llm-rubric | 需自己实现 |
| 结果聚合 + 报告 | 内置 HTML report + JSON output | 需自己实现 |
| 多次运行 + 通过率 | 内置 `repeat` 字段 | 需自己实现 |
| CI 集成 | 内置 `--ci` flag | 需自己写 |
| 差分对比 | 内置 baseline comparison | 需自己实现 |
| 开发投入 | 写 YAML 配置 | 写 500+ 行 Python |

结论：promptfoo 以 YAML 配置覆盖了自建方案需要 500+ 行代码的功能，且持续由社区维护。

### 2. 为什么用 API 直调而不是 claude CLI

评审一致结论：`claude -p` 用于测试有根本性问题：

- AskUserQuestion 在非交互模式下行为未定义
- 插件加载需要额外配置 fixture 项目的 settings.json
- 输出格式不稳定，regex 断言 flake rate 30-50%

API 直调方式：将 SKILL.md 作为 system prompt 注入，用户输入作为 user message，直接验证 LLM 在该 prompt 下的路由决策。Flake rate 降至 10-20%。

### 3. 为什么用 tool_use 结构化输出而不是文本断言

这是**整个方案最关键的设计决策**。

问题：LLM 的文本回复格式不可控。同样是 P0 分类，模型可能输出"风险等级：P0"、"I classify this as P0"、"## Phase 1 Result\n- Risk: P0"等无数变体。文本匹配的 flake rate 极高。

解法：在 eval 的 system prompt 中注入一条额外指令，让 LLM **必须通过 tool_use 调用 `classify_result` 工具**返回结构化结果：

```json
{
  "risk_level": "P0",          // enum: P0|P1|P2|P3
  "mode": "single-domain",     // enum: single-domain|cross-domain
  "change_type": "requirement", // enum: requirement|bug|fast-track
  "routing": ["requirements-elicitation", "writing-plans", "spec-challenge", ...]
}
```

这样断言变成 JSON 字段比对（`result.risk_level === 'P0'`），确定性接近 100%。

**关键原则：这个 tool schema 仅用于测试，不改变 SKILL.md 的实际行为。** SKILL.md 不知道 classify_result 工具的存在，它只是按正常流程做分析。eval wrapper 是一个"观测探针"，不是行为修改。

### 4. 为什么用 Golden Fixture 而不是自动解析路由表

SKILL.md 中的路由表是 markdown 散文格式，不是结构化数据。自动解析需要维护一个 markdown parser，解析器本身也需要测试，维护成本 > 手写 golden fixture。

所以选择手工维护 `routing_matrix.yaml`（13 条路由规则）和 `anchor_keywords.yaml`（11 个 skill 的锚点），作为"这些 SKILL.md 应该包含什么"的参考真值。

代价是修改路由表后需要手动同步 fixture。收益是 fixture 本身就是对路由规则的二次确认——写 fixture 的过程就是 review 路由变更的过程。

### 5. 为什么明确放弃 E2E 全链路测试

| 维度 | E2E 测试 | 实际情况 |
|------|---------|---------|
| 单次成本 | $10+ | 一轮完整工作流需要多次 LLM 调用 |
| 执行时间 | 30-60 分钟 | 多轮交互（Phase 1→2→3 + 子 skill） |
| 可复现性 | <50% | LLM 输出路径不确定，中间步骤不可控 |
| 调试能力 | 极差 | 失败时无法定位是哪个 skill 的问题 |

ROI 为负。Layer 1 + Layer 2 已覆盖 95% 的回归风险：
- Layer 1 验证结构完整性（文件存在、引用正确、路由表完整）
- Layer 2 验证入口 skill（risk-classifier）的路由决策正确
- 如果入口路由正确 + 下游 skill 结构完整，整体工作流大概率正确

---

# 第二部分：维护手册

## 快速开始

```bash
# 前置依赖
pip install pytest pyyaml
npm install -g promptfoo  # 或使用 npx（无需全局安装）

# Layer 2 需要 API Key
export ANTHROPIC_API_KEY=your-key
```

```bash
# 从项目根目录运行
make -C tests lint        # 静态检查（<3s, $0）
make -C tests test-hook   # Hook 单元测试（<10s, $0）
make -C tests eval-quick  # P0 场景 eval（~2min, ~$0.50）
make -C tests eval-full   # 全部 15 场景（~5min, ~$1.50）
make -C tests all         # lint + test-hook + eval-quick
make -C tests clean       # 清理缓存
```

## 验证层级详解

### Layer 1: 静态结构验证

**文件**: `static/lint_skills.py` | **耗时**: <3s | **成本**: $0 | **可靠性**: 100%

14 项检查：

| # | 检查 | 捕获的问题 |
|---|------|-----------|
| 1 | Frontmatter 校验 | SKILL.md 损坏、新 skill 漏填 name/description |
| 2 | Skill 互引完整性 | 重命名后 `ecw:xxx` 引用指向不存在的目录 |
| 3 | 产出物路径一致性 | SKILL.md 写入路径与 CLAUDE.md artifact table 不匹配 |
| 4 | 路由 DAG 验证 | 孤立 skill（无人引用也不引用别人） |
| 5 | 关键指令锚点 | 重构时意外删除核心段落（如 tdd 的 "RED-GREEN-Refactor"） |
| 6 | session-state 合约 | risk-classifier 写入的字段 ⊇ 下游 skill 引用的字段 |
| 7 | AskUserQuestion 存在性 | 误删用户确认点（Phase 1 确认、TDD 跳过确认） |
| 8 | 跨 skill 一致性 | 多处定义同一规则（TDD 等级、阈值）但改漏 |
| 9 | ecw.yml 配置键引用 | SKILL.md 引用的 key 在 templates/ecw.yml 中不存在 |
| 10 | Markdown 表格结构 | 表格列数不一致导致 AI 误读 |
| 11 | Agent/Prompt 模板引用 | 引用的 .md 模板文件不存在 |
| 12 | CLAUDE.md 一致性 | Skill Trigger 表与 skills/ 目录不匹配 |
| 13 | Token 统计 | Prompt 过长（>20K tokens）导致遵循度下降 |
| 14 | 路由矩阵验证 | SKILL.md 路由表 vs routing_matrix.yaml golden fixture |

支持单项运行：

```bash
python tests/static/lint_skills.py --check frontmatter
python tests/static/lint_skills.py --check routing-matrix
python tests/static/lint_skills.py --quiet  # 仅输出错误
```

### Layer 1b: Hook 单元测试

**文件**: `static/test_verify_completion.py` | **耗时**: <10s | **成本**: $0 | **可靠性**: 100%

56 个测试用例，覆盖 `hooks/verify-completion.py` 全部函数：

| 测试类 | 用例数 | 覆盖 |
|--------|--------|------|
| TestEntryLogic | 4 | 非 TaskUpdate/非 completed/空 cwd → pass |
| TestGetChangedFiles | 4 | 正常输出、空输出、git 错误/超时 |
| TestCheckBrokenReferences | 6 | 引用存在/不存在、非 text 文件跳过 |
| TestCheckStaleReferences | 5 | 删除文件有引用/无引用、skip_dirs |
| TestCheckJavaCompilation | 6 | 无 java/无 pom/成功/失败/超时/mvn 不存在 |
| TestCheckJavaTests | 4 | run_tests=false/失败/成功 |
| TestReadEcwConfig | 4 | 正常/不存在/yaml=None/parse error |
| TestLoadPathMappings | 5 | 正常表格/表头跳过/strip/不存在 |
| TestCheckKnowledgeDocFreshness | 6 | 代码变更+知识未变/已变/启发式匹配 |
| TestCheckTestCoverage | 6 | enabled/disabled/存在/缺失 |
| TestOutputFormat | 4 | fail 格式/截断/pass 格式/reminders |
| TestExceptionSafety | 2 | 异常不阻塞工作流 |

### Layer 2: 场景化行为 Eval

**文件**: `eval/promptfooconfig.yaml` + `eval/scenarios/*.yaml` | **耗时**: 2-5min | **成本**: $0.50-1.50 | **可靠性**: 80-90%

15 个场景，验证 risk-classifier 的路由决策：

**P0 场景（阻塞发布）— 8 个：**

| # | 场景 | 输入（中文） | 关键断言 |
|---|------|-------------|---------|
| S1 | P0 单域需求 | 新增支付网关，PCI 合规 | risk_level=P0, routing 含 spec-challenge + requirements-elicitation + writing-plans + biz-impact-analysis |
| S2 | P1 跨域需求 | 订单退款联动 payment | mode=cross-domain, routing 含 domain-collab + spec-challenge + writing-plans + impl-verify + biz-impact-analysis |
| S3 | P2 单域需求 | 查询性能优化 | routing 不含 requirements-elicitation/spec-challenge |
| S4 | P3 微改动 | 日志级别调整 | routing 不含 writing-plans |
| S5 | Bug 报告 | 下单后库存未扣减 | risk_level≥P1, change_type=bug, routing 含 systematic-debugging + impl-verify + biz-impact-analysis |
| S6 | P1 单域需求 | 手机号绑定 | routing 含 req-elicitation + writing-plans + impl-verify + biz-impact-analysis，不含 spec-challenge |
| S7 | P0 跨域需求 | 跨境支付涉及三域 | routing 含 domain-collab + spec-challenge + writing-plans + impl-verify + biz-impact-analysis |
| S8 | Fast Track | 支付回调超时故障 | routing 含 impl-verify + biz-impact-analysis，不含 spec-challenge/domain-collab |

**P1 场景（尽快补充）— 5 个：** S9 (P2 跨域含 writing-plans + impl-verify)、S10 (P3 跨域)、S11 (非变更请求)、S12 (信息不足→P2/P3)、S13 (敏感词触发)

**P2 场景（后续完善）— 2 个：** S14 Bug 风险差异、S15 手动覆盖

查看 eval 结果报告：

```bash
cd tests/eval && npx promptfoo eval && npx promptfoo view
```

## 文件依赖地图

当你修改某个源文件时，需要同步更新的测试文件：

```
SKILL.md 变更
│
├─ 路由表变更 ──────────────────→ static/routing_matrix.yaml
│                                  eval/scenarios/*.yaml（相关场景的断言）
│
├─ 新增/删除 Skill ────────────→ static/anchor_keywords.yaml
│                                  static/routing_matrix.yaml
│                                  eval/scenarios/（可能需要新增场景）
│
├─ 核心关键词/段落标题变更 ───→ static/anchor_keywords.yaml
│
├─ session-state 字段变更 ────→ lint_skills.py 中 check_session_state_contract
│                                 （硬编码的 bold_field_pattern 正则）
│
├─ 产出物路径变更 ────────────→ CLAUDE.md artifact table（lint 自动交叉验证）
│
└─ ecw.yml 配置键变更 ────────→ templates/ecw.yml（lint 自动交叉验证）

hooks/verify-completion.py 变更
└─────────────────────────────→ static/test_verify_completion.py

promptfoo 配置变更
├─ 新增 tool schema 字段 ─────→ eval/tools/classify_result.json
└─ 调整 provider/model ───────→ eval/promptfooconfig.yaml
```

## 操作手册：常见维护场景

### 场景 1：新增一个 Skill

假设新增 `skills/rollback-plans/SKILL.md`。

**Step 1 — 确保 lint 能发现它：**

编辑 `static/anchor_keywords.yaml`，新增条目：

```yaml
rollback-plans:
  - "rollback strategy"
  - "rollback trigger"
```

> 选择 2-5 个该 skill 特有的关键短语。要求：在 SKILL.md 中搜索这些词一定能命中，但在其他 skill 中不会命中。

**Step 2 — 更新路由矩阵（如果新 skill 出现在路由链中）：**

编辑 `static/routing_matrix.yaml`，在相关路由规则的 `must_include` 中加入新 skill：

```yaml
- level: P0
  mode: single-domain
  type: requirement
  must_include:
    - ...existing...
    - rollback-plans   # ← 新增
```

**Step 3 — 更新 eval 场景断言（如果需要）：**

在相关的 `eval/scenarios/s*.yaml` 中增加路由包含断言：

```yaml
- type: javascript
  value: |
    const parsed = JSON.parse(output);
    const result = parsed.input || parsed;
    const routing = result.routing || [];
    return routing.includes('rollback-plans');
  metric: routing_includes_rollback_plans
```

**Step 4 — 验证：**

```bash
make -C tests lint       # 应该通过，新 skill 的锚点被检查
make -C tests eval-quick # 如果改了 P0 场景断言，验证通过
```

**Checklist：**
- [ ] `anchor_keywords.yaml` 新增条目
- [ ] `routing_matrix.yaml` 更新相关路由规则（如适用）
- [ ] `eval/scenarios/` 更新相关场景断言（如适用）
- [ ] CLAUDE.md Skill Trigger Conditions 表同步（lint 会自动检查）

---

### 场景 2：修改路由表

假设把 P1 单域需求从"不走 spec-challenge"改为"走 spec-challenge"。

**Step 1 — 修改 SKILL.md**（你的实际变更）

**Step 2 — 同步 routing_matrix.yaml：**

```yaml
# 修改前
- level: P1
  mode: single-domain
  type: requirement
  must_exclude:
    - spec-challenge   # ← 删除这行

# 修改后
- level: P1
  mode: single-domain
  type: requirement
  must_include:
    - ...existing...
    - spec-challenge   # ← 新增到 must_include
```

**Step 3 — 同步 eval 场景断言：**

编辑 `eval/scenarios/s06-p1-single-domain.yaml`：

```yaml
# 修改前：断言排除 spec-challenge
- type: javascript
  value: |
    const parsed = JSON.parse(output);
    const result = parsed.input || parsed;
    const routing = result.routing || [];
    return !routing.includes('spec-challenge');

# 修改后：断言包含 spec-challenge
- type: javascript
  value: |
    const parsed = JSON.parse(output);
    const result = parsed.input || parsed;
    const routing = result.routing || [];
    return routing.includes('spec-challenge');
  metric: routing_includes_spec_challenge
```

**Step 4 — 验证：**

```bash
make -C tests lint       # routing-matrix 检查应通过
make -C tests eval-quick # S6 场景应通过
```

**Checklist：**
- [ ] `routing_matrix.yaml` 同步 must_include/must_exclude
- [ ] `eval/scenarios/` 中受影响的场景断言更新
- [ ] `make lint` + `make eval-quick` 通过

---

### 场景 3：修改 Skill 核心行为（重构段落、改关键词）

假设把 tdd 的 "Iron Law" 段落重命名为 "Core Principle"。

**Step 1 — 更新 anchor_keywords.yaml：**

```yaml
# 修改前
tdd:
  - "Iron Law"

# 修改后
tdd:
  - "Core Principle"
```

**Step 2 — 验证：**

```bash
make -C tests lint  # 锚点检查应通过
```

如果只是措辞变更（不影响路由逻辑），不需要改 eval 场景。

**判断原则：** 如果变更影响的是"LLM 如何做决策"（路由规则、分类逻辑），需要改 eval。如果只影响"执行步骤的描述"（段落标题、措辞），只需改锚点。

---

### 场景 4：修改 verify-completion.py

假设新增一个检查函数 `check_api_contracts()`。

**Step 1 — 在 test_verify_completion.py 中新增测试类：**

```python
class TestCheckApiContracts:
    def test_no_api_files_skipped(self, hook_module):
        # ...

    def test_contract_violation_produces_issue(self, hook_module):
        # ...
```

**Step 2 — 验证：**

```bash
make -C tests test-hook  # 所有测试应通过
```

**原则：** 每个公开函数至少有 3 个测试：正常路径、跳过路径、错误路径。参考现有的 `TestCheckJavaCompilation`（6 个用例）作为模板。

---

### 场景 5：新增一个 eval 场景

假设需要测试"共享资源变更自动升级到 P1"的行为。

**Step 1 — 创建场景文件 `eval/scenarios/s16-shared-resource-upgrade.yaml`：**

```yaml
# S16: Shared Resource Upgrade
# Changes to shared resources should upgrade risk to at least P1
- vars:
    input: "修改 Redis 缓存的 key 命名规则，影响订单和支付两个域的共享缓存"
  assert:
    - type: is-json
      value: "{{output}}"
    - type: javascript
      value: |
        const parsed = JSON.parse(output);
        const result = parsed.input || parsed;
        return result.risk_level === 'P0' || result.risk_level === 'P1';
      metric: upgraded_to_p1_or_higher
    - type: javascript
      value: |
        const parsed = JSON.parse(output);
        const result = parsed.input || parsed;
        return result.mode === 'cross-domain';
      metric: mode_cross_domain
    - type: javascript
      value: |
        const parsed = JSON.parse(output);
        const result = parsed.input || parsed;
        const routing = result.routing || [];
        return routing.includes('domain-collab');
      metric: routing_includes_domain_collab
```

**Step 2 — 文件命名规则：** `s{编号}-{简短描述}.yaml`，编号递增。

**Step 3 — 断言编写原则：**

1. **必须有 `is-json`** 断言——验证 tool call 输出可解析
2. **每个断言一个 `metric` 名**——在报告中可独立追踪
3. **风险等级允许相邻 1 级浮动**——LLM 固有不确定性（`P0 || P1`）
4. **路由断言覆盖 must_include 和 must_exclude**——不要只测排除
5. **JSON 路径兼容**——使用 `const parsed = JSON.parse(output); const result = parsed.input || parsed;` 兼容 tool_use 嵌套格式

**Step 4 — 验证：**

```bash
cd tests/eval && npx promptfoo eval --filter-pattern "s16-*"
```

---

### 场景 6：调整 session-state 字段

假设在 session-state.md 模板中新增字段 `**Deployment Strategy**`。

**Step 1 — 确认 lint 能发现下游引用：**

`lint_skills.py` 的 `check_session_state_contract` 使用硬编码的字段名列表（`bold_field_pattern` 正则）。如果新字段需要被下游 skill 引用，需更新这个正则。

在 `lint_skills.py` 中找到 `bold_field_pattern`，新增字段名：

```python
re.compile(
    r"\*\*(Risk Level|Domains|Mode|Routing|Current Phase"
    r"|Implementation Strategy|Post-Implementation Tasks"
    r"|Deployment Strategy)\*\*"  # ← 新增
)
```

**Step 2 — 验证：**

```bash
make -C tests lint  # session-state 合约检查应通过
```

## CI 集成

```yaml
# GitHub Actions 示例
name: ECW Verification
on: [push, pull_request]

jobs:
  static:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.9'
      - run: pip install pytest pyyaml
      - run: make -C tests lint
      - run: make -C tests test-hook

  eval:
    runs-on: ubuntu-latest
    needs: static  # lint 失败则不浪费 API 费用
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm install -g promptfoo
      - run: make -C tests eval-quick
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

> Layer 2 eval 不建议作为 PR blocking check（flake rate 10-20%），适合作为 advisory signal。

## 故障排查

**`make lint` 报路由矩阵不匹配**

检查 `skills/risk-classifier/SKILL.md` 的路由表是否与 `static/routing_matrix.yaml` 一致。这是最常见的 lint 失败原因——修改了路由表但忘记同步 golden fixture。

修复：对照 SKILL.md 路由表更新 `routing_matrix.yaml` 的 must_include/must_exclude。

**`make lint` 报锚点关键词缺失**

某个 skill 的 SKILL.md 中不再包含 `anchor_keywords.yaml` 定义的关键词。通常是重构时改了段落标题或关键措辞。

修复：更新 `anchor_keywords.yaml` 中的关键词，确保新措辞在 SKILL.md 中能被找到。

**`make eval-quick` 单次失败**

LLM 输出有固有随机性。单次失败不代表有问题。

排查步骤：
1. 再跑一次：`cd tests/eval && npx promptfoo eval --repeat 3`
2. 如果 3 次中 2 次通过（majority vote），说明是正常波动
3. 如果 3 次全部失败，说明 SKILL.md 的路由规则可能真的有问题

**`make eval-quick` 全部场景失败**

可能的原因：
- `ANTHROPIC_API_KEY` 未设置或过期
- promptfoo 版本不兼容（建议 >= 0.80）
- 网络问题导致 API 调用超时

**`make test-hook` 测试失败**

`hooks/verify-completion.py` 有改动。测试依赖具体实现细节，hook 代码变更后需同步更新 `static/test_verify_completion.py`。

**`make lint` 报 2 个 warning（正常）**

当前有 2 个已知的合理 warning：
1. `[consistency] Implementation Strategy thresholds differ` — 跨 skill 的阈值定义不完全一致，已知但暂未修复
2. `[ecw-yml] tdd.base_test_class not found` — tdd skill 引用了 ecw.yml 中未定义的配置键，用户自定义时补充

## 目录结构

```
tests/
├── Makefile                          # 构建命令（含 API key 检查和 clean）
├── README.md                         # 本文件
├── static/
│   ├── lint_skills.py                # Layer 1: 14 项静态检查（~880 行）
│   ├── routing_matrix.yaml           # 路由 golden fixture（13 条规则）
│   ├── anchor_keywords.yaml          # 锚点关键词（11 个 skill）
│   ├── conftest.py                   # pytest fixtures
│   └── test_verify_completion.py     # Layer 1b: 56 个 hook 单元测试
└── eval/
    ├── promptfooconfig.yaml          # promptfoo 主配置
    ├── tools/
    │   └── classify_result.json      # 结构化输出 tool schema
    └── scenarios/
        ├── s01-p0-single-domain.yaml
        ├── s02-p1-cross-domain.yaml
        ├── ...
        └── s15-manual-override.yaml
```
