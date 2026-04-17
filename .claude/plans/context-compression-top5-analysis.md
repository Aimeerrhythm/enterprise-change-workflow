# ECW 上下文压缩问题 Top 5 分析报告

## Context

ECW 在执行复杂的 P0/P1 跨域任务时，单个 session 内会触发多次上下文压缩（实测 6 次），导致关键分析结论丢失、工作流断裂。本报告基于 WMS 项目 2026-04-15 的实际 session 数据（session `5f1c91c6`，6.1MB，1988 行），定位 Top 5 上下文消耗瓶颈，为红蓝对抗开发提供精确的问题定义和验收标准。

### 数据来源

- **Session**: `/Users/urbanic/.claude/projects/-Users-urbanic-Documents-project-java-wms/5f1c91c6-c560-442b-840f-ddc2d85d8f37.jsonl`
- **任务**: "入库签收时，如果实际到货数量与采购单数量不符，需要自动创建到货异常单，冻结该批次对应库位的库存，并取消该批次关联的待执行任务"
- **风险等级**: P0，跨 4 个 domain（入库、异常、库存、任务）
- **完整 Skill 链**: risk-classifier → domain-collab → writing-plans → spec-challenge → TDD → impl-verify(x2) → biz-impact-analysis

### 压缩事件全景

| # | Session 行号 | 工作流阶段 | 压缩摘要大小 | 直接原因 |
|---|-------------|-----------|-------------|---------|
| 1 | 214 | spec-challenge 中间 | 13.8KB | domain-collab 12 agent 结果 + Plan 全文 + spec-challenge 结果 |
| 2 | 436 | TDD 中期 | 14.9KB | 测试编写 + 代码读取循环 |
| 3 | 771 | TDD 后期 | 14.4KB | 继续 RED-GREEN 循环 |
| 4 | 1110 | TDD 末期 | 16.3KB | 实现代码 + 测试修复循环 |
| 5 | 1410 | impl-verify 初始 | 18.9KB | Skill prompt 注入 + 重读实现文件 |
| 6 | 1666 | impl-verify 中期 | 13.7KB | 多轮验证逐轮读文件 |

### 文件读取统计

| 阶段 | 读取次数 | 唯一文件数 | 最高频文件 |
|------|---------|-----------|-----------|
| risk-classifier | 4 | 4 | — |
| domain-collab | 4 | 4 | — |
| spec-challenge | 5 | 1 | Plan 文件 x5 |
| **TDD** | **107** | **36** | SortingBizServiceImpl.java x23 |
| **impl-verify** | **49** | **15** | PutAwayBizServiceImpl.java x12 |
| **合计** | **169** | **49** | — |

---

## Issue #1: TDD+实现在 coordinator 中直接执行

### 严重度: Critical

### 数据证据

- TDD 阶段（line 300 → line 1383）产生 **107 次文件读取**，触发 **3 次上下文压缩**（占总压缩次数 50%）
- `SortingBizServiceImpl.java` 被读取 **23 次**（每次 edit 后重读验证）
- `ExpOperateCoreBizServiceImpl.java` 被读取 **14 次**
- `SortingAutoExpDetectionTest.java` 被读取 **14 次**
- 该 session 没有使用 `impl-orchestration`——所有 TDD + 实现代码直接在 coordinator 上下文中执行

### 根因分析

当前 `risk-classifier` 的 Implementation Strategy Selection（`skills/risk-classifier/SKILL.md:105-127`）规则：

```
Plan Tasks ≤ 3 → 直接实现
Plan Tasks 4-8, P0/P1 → impl-orchestration
```

**问题**：判断维度单一（仅 Task 数量）。该 session 的 Plan 可能只有 3 个 Task，但每个 Task 涉及 10+ 个文件的密集 read/edit。即使 Task 数少，coordinator 内的文件操作量也足以撑爆上下文。

此外，TDD Skill 本身（`skills/tdd/SKILL.md`）**完全没有 subagent 机制**——所有 RED-GREEN-REFACTOR 循环都在 coordinator 中执行，无论复杂度多高。

### 解决方案

**A. 修改 risk-classifier 的 Implementation Strategy Selection 规则（`skills/risk-classifier/SKILL.md:105-127`）**

将单维度 "Task 数量" 改为多维度决策矩阵：

```markdown
| Condition | Strategy | Rationale |
|-----------|----------|-----------|
| Plan Tasks ≤ 3 且 涉及文件 ≤ 5 | **Direct** | 少量任务+少量文件，subagent 开销不值 |
| Plan Tasks ≤ 3 但 涉及文件 ≥ 6 | **`ecw:impl-orchestration`** | 文件操作密集，coordinator 上下文会爆 |
| Plan Tasks ≤ 3 但 涉及 ≥ 2 domains 代码修改 | **`ecw:impl-orchestration`** | 跨域修改文件分散，上下文消耗大 |
| Plan Tasks 4-8, P0/P1 | **`ecw:impl-orchestration`** | 保持不变 |
| Plan Tasks 4-8, P2 | **Direct** | 保持不变 |
| Plan Tasks > 8, P0/P1 | **`ecw:impl-orchestration`**, merge | 保持不变 |
| P3 | **Direct** | 保持不变 |
| Bug fix | **Direct** | 保持不变 |
```

新增判断：在 writing-plans 完成后，扫描 Plan 中所有 Task 涉及的文件列表，统计 unique 文件数和 domain 数。

**B. TDD Skill 增加 subagent delegation 路径（`skills/tdd/SKILL.md`）**

当 Implementation Strategy = `ecw:impl-orchestration` 时，TDD 不在 coordinator 执行——由 impl-orchestration 的 implementer subagent 在自己的上下文中执行 TDD 循环。

当 Implementation Strategy = Direct 但文件数 ≥ 6 时，TDD 每个 RED-GREEN cycle 封装为一个 subagent 调用：
- subagent 接收：当前 cycle 的 test scenario + 相关 Plan Task 内容 + 文件路径
- subagent 执行：写测试 → 编译 → 实现 → 编译 → 验证
- subagent 返回：cycle 结果摘要（pass/fail + 修改的文件列表）
- coordinator 只持有摘要，不持有文件内容

### 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `skills/risk-classifier/SKILL.md` | 修改 lines 105-127，Implementation Strategy Selection 规则 |
| `skills/tdd/SKILL.md` | 新增 subagent delegation 路径，当文件数 ≥ 6 时 cycle 下沉 |
| `skills/impl-orchestration/SKILL.md` | 确认 implementer subagent 已包含 TDD 执行能力（当前已有 TDD requirement 注入） |

### 验收标准（Red Team）

1. **规则验证**：给定一个 Plan 包含 3 个 Task 但涉及 8 个文件（跨 2 个 domain），risk-classifier 应输出 `Implementation Strategy: subagent-driven`
2. **规则验证**：给定一个 Plan 包含 3 个 Task 且仅涉及 3 个文件（单 domain），risk-classifier 应输出 `Implementation Strategy: direct`
3. **TDD 行为验证**：当 Strategy=subagent-driven 时，TDD cycle 必须通过 Agent tool 派发，coordinator 不直接执行 Read/Edit
4. **回归验证**：原有 Tasks ≤ 3 + 文件 ≤ 5 的场景仍走 Direct，不引入不必要的 subagent 开销
5. **上下文验证**：模拟一个涉及 6+ 文件的 TDD 场景，coordinator 上下文中不应出现实现文件的完整内容

---

## Issue #2: impl-verify 全轮次在 coordinator 中执行

### 严重度: High

### 数据证据

- impl-verify 阶段（line 1383 → line 1823）产生 **49 次文件读取**，触发 **2 次上下文压缩**
- `PutAwayBizServiceImpl.java` 被读取 **12 次**
- `ExpOperateCoreBizServiceImpl.java` 被读取 **10 次**
- `SortingBizServiceImpl.java` 被读取 **10 次**
- impl-verify 被调用了 **2 次**（第一次发现 must-fix，修复后第二次重跑）

### 根因分析

`skills/impl-verify/SKILL.md` 的 4 轮验证（Round 1-4）全部在 coordinator 中顺序执行：

- **Round 1**（line 73-97）：执行 `git diff` + 读取需求文档 + 逐文件验证代码逻辑
- **Round 2**（line 99-120）：读取 domain 知识文件（business-rules.md, data-model.md）+ 对比代码
- **Round 3**（line 122-143）：读取 Plan 文件 + 对比代码
- **Round 4**（line 145-167）：读取现有代码模式 + 审查工程标准

虽然 impl-verify 有 "Diff Read Strategy"（lines 64-69）减少重复 `git diff`，但**每轮仍然需要读取实现文件来验证逻辑**，加上各轮各自读取的参考文件（知识文件/Plan/代码模式），累积量很大。

更关键的是：当 Round N 发现 must-fix → 修复 → 重跑受影响轮次，这个收敛循环会导致文件读取量成倍增加。

### 解决方案

**将 impl-verify 的每一轮下沉为独立 subagent。**

修改 `skills/impl-verify/SKILL.md`：

```
当前：
  coordinator: Round 1 读所有文件 + 分析 → Round 2 读知识文件 + 分析 → Round 3 读 Plan + 分析 → Round 4 审查
  （4 轮文件内容全部堆在 coordinator 上下文）

改为：
  coordinator: 执行 git diff --name-only 获取变更文件列表（轻量）
  coordinator: dispatch Round 1 subagent
    inputs: 变更文件列表 + 需求摘要（从 session-data 读 或 session-state）
    agent 内部: 读 git diff + 实现文件 + 需求文档，做双向追踪
    返回: 结构化 findings YAML（每条: file, line, severity, description）
  coordinator: dispatch Round 2 subagent
    inputs: 变更文件列表 + domain 知识文件路径
    agent 内部: 读知识文件 + 实现文件，做规则对齐
    返回: 结构化 findings YAML
  coordinator: dispatch Round 3 subagent（同理）
  coordinator: dispatch Round 4 subagent（同理）
  coordinator: 合并 4 轮 findings → 输出给用户
```

**Round 1-4 可以并行派发**（4 个 subagent 同时执行），因为每轮的验证维度独立，不依赖前一轮的结果。

**收敛循环优化**：
- must-fix 修复后，只对受影响的轮次重新 dispatch subagent（不重跑全部 4 轮）
- 重跑 subagent 只读取修复涉及的文件（增量 diff），不重读全部变更

### 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `skills/impl-verify/SKILL.md` | 重构执行协议：4 轮从顺序 inline 改为 parallel subagent dispatch |
|  | 新增 subagent prompt 模板（每轮一个），定义 inputs/outputs 格式 |
|  | 修改收敛循环逻辑：增量重跑受影响轮次 |

### 验收标准（Red Team）

1. **隔离验证**：impl-verify 执行期间，coordinator 上下文中不应出现实现文件（.java）的完整内容
2. **并行验证**：Round 1-4 的 4 个 subagent 应在同一条 assistant 消息中并行派发（多个 Agent tool call）
3. **findings 格式验证**：每个 subagent 返回的 findings 必须是结构化格式（YAML/表格），而非散文
4. **收敛验证**：当 Round 1 有 must-fix 且已修复后，重跑只 dispatch Round 1 subagent，不重跑 Round 2-4
5. **回归验证**：impl-verify 的 4 轮验证覆盖度不因 subagent 化而降低（每轮的检查项清单与改造前一致）

---

## Issue #3: writing-plans 在 coordinator 中生成完整 Plan

### 严重度: High

### 数据证据

- 第 1 次压缩发生在 line 214（spec-challenge 中间），此时 coordinator 已积累：
  - risk-classifier Phase 1 分析 + 4 次知识文件读取
  - domain-collab 12 个 agent 结果（Round 1: 4 个, Round 2: 4 个, 探索: 3 个, 设计: 1 个）
  - **writing-plans 生成的完整 Plan**（`concurrent-swinging-puddle.md`，被读取 5 次）
  - spec-challenge agent 返回的审查结果
- 从 domain-collab 开始（line 69）到第 1 次压缩（line 214）只用了 **145 行对话**就撑满了上下文

### 根因分析

`skills/writing-plans/SKILL.md:33-41` 定义了 Domain Context Injection：
1. 读 `ecw-path-mappings.md`
2. 读每个 affected domain 的 `business-rules.md`
3. 读 `knowledge-summary.md`（如存在）

这些文件读取 + Plan 生成全部在 coordinator 中执行。生成的 Plan 包含"每个 Task 的完整代码规格"（`skills/writing-plans/SKILL.md:58-65` "每步 2-5 分钟"），一个 P0 Plan 可能有 5-8 个 Task，每个 Task 包含文件路径、方法签名、测试场景、错误码等，**Plan 全文很容易超过 5000 tokens**。

加上 domain-collab 的 12 个 agent 结果虽然是 YAML 格式（≤30 行/个），但 12 个 agent × 30 行 = 360 行 YAML 也不少。

### 解决方案

**将 writing-plans 的重逻辑下沉为 subagent。**

修改 `skills/writing-plans/SKILL.md`：

```
当前：
  coordinator: 读 ecw-path-mappings → 读 business-rules → 读 knowledge-summary → 生成 Plan → Write Plan 文件
  （所有知识文件内容 + Plan 全文都在 coordinator 上下文中）

改为：
  coordinator: 构造 subagent prompt，注入：
    - 需求摘要（从 .claude/ecw/session-data/requirements-summary.md 或 domain-collab-report.md 路径）
    - Phase 2 评估结论（从 .claude/ecw/session-data/phase2-assessment.md 或 session-state.md）
    - 文件路径列表（ecw-path-mappings, business-rules, knowledge-summary 的路径）
    - Plan 输出目标路径（.claude/plans/{feature}.md）
    - Risk level + Plan 详细度要求
  
  subagent 执行：
    - 读知识文件（在自己的上下文中）
    - 生成 Plan
    - Write(.claude/plans/{feature}.md)
    - 返回：Plan 摘要（Task 数量 + 每个 Task 一句话描述 + 涉及文件列表）

  coordinator 收到摘要后：
    - 更新 session-state.md 的 Implementation Strategy
    - 展示摘要给用户确认
    - 用户如需 review 完整 Plan → 读文件（或用户自行查看）
```

**附带优化：domain-collab 后的 context 清理**

在 domain-collab Round 3 输出 30 行摘要后，下游 Skill 应该**从 `domain-collab-report.md` 文件读取**，而不是依赖 coordinator 对话中的 agent 返回结果。当前 SKILL.md 的描述是 "output only summary in conversation"，但实际上 Round 1/2 的 YAML 结果仍留在对话历史中。

### 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `skills/writing-plans/SKILL.md` | 重构为 subagent 模式：coordinator 构造 prompt → dispatch agent → 接收摘要 |
|  | 新增 subagent prompt 模板，定义 inputs（知识文件路径）和 outputs（Plan 摘要格式） |
| `skills/domain-collab/SKILL.md` | 强化 Round 3 的描述：明确指出下游 Skill 应从文件读取，不依赖对话中的 agent 结果 |

### 验收标准（Red Team）

1. **隔离验证**：writing-plans 执行后，coordinator 上下文中不应包含 `business-rules.md` 或 `data-model.md` 的完整内容
2. **Plan 文件验证**：`.claude/plans/{feature}.md` 必须由 subagent 直接 Write，不经过 coordinator 中转
3. **摘要格式验证**：coordinator 收到的摘要 ≤ 500 tokens，包含：Task 数量、每 Task 一句话描述、涉及文件清单
4. **下游可用性验证**：spec-challenge 能从 Plan 文件（而非 coordinator 对话历史）读取完整 Plan 并执行审查
5. **回归验证**：Plan 的完整性和详细度不因 subagent 化而降低（P0 Plan 仍包含完整代码规格）

---

## Issue #4: Phase 2 依赖图查询在 coordinator 中执行

### 严重度: Medium

### 数据证据

- Phase 2（`skills/risk-classifier/SKILL.md:330-426`）需要读取 5 类知识文件：
  - `cross-domain-calls.md`（§1）
  - `mq-topology.md`（§2）
  - `shared-resources.md`（§3）
  - `external-systems.md`（§4）
  - `e2e-paths.md`（§5）
- 在该 session 中，Phase 1 已读取了 `shared-resources.md` 和 `mq-topology.md`，Phase 2 又重复读取这 5 个文件
- Phase 2 的分析结果（变更类型分析、风险等级升降级判断）留在 coordinator 上下文中
- 虽然单独看 Phase 2 不是最大瓶颈，但它累加在 domain-collab 之后、writing-plans 之前，处于 "上下文即将满载" 的临界点

### 根因分析

Phase 2 在 coordinator 中**全量读取 5 类知识文件**做依赖图查询。这些文件在中大型项目中可能各有 50-200 行（WMS 项目的 shared-resources.md 等）。

更重要的是**重复读取**问题：Phase 1 已读过 shared-resources.md 和 mq-topology.md，Phase 2 又读一遍。如果 domain-collab 在 Round 3 也读了部分知识文件，同一个文件在一个 session 中可能被读 3 次。

### 解决方案

**将 Phase 2 依赖图查询下沉为 subagent。**

修改 `skills/risk-classifier/SKILL.md` Phase 2 部分：

```
coordinator 构造 prompt，注入：
  - 需求摘要 + 变更组件列表（从 requirements-elicitation 或 domain-collab 结论）
  - Phase 1 的预判结果（P级 + domains）
  - 5 类知识文件的路径
  - knowledge-summary.md 路径（如存在，优先使用）

subagent 执行：
  - 优先读 knowledge-summary.md（如存在，跳过已覆盖的知识文件）
  - 按需读取未覆盖的知识文件
  - 执行 §1-§5 依赖图查询
  - 输出结构化结论

subagent 返回 YAML：
  risk_level: P1
  change_from: P0  # 如有升降级
  affected_domains: [order, inventory]
  dependency_graph:
    direct_calls: [{from, to, method}]
    mq_impacts: [{topic, publishers, consumers}]
    shared_resources: [{resource, consumers}]
    external_impacts: [{system, direction, interface}]
    e2e_paths: [{path_name, affected_step}]
  upgrade_reason: "xxx"  # 如有升级
```

### 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `skills/risk-classifier/SKILL.md` | 重构 Phase 2（lines 330-426）：从 coordinator inline 改为 subagent dispatch |
|  | 新增 Phase 2 subagent prompt 模板 |
|  | Phase 1 中删除重复读取（如果 Phase 2 subagent 会读，Phase 1 只做轻量级 keyword 匹配） |

### 验收标准（Red Team）

1. **隔离验证**：Phase 2 执行后，coordinator 上下文中不应包含 5 类知识文件的完整内容
2. **knowledge-summary 复用验证**：当 `knowledge-summary.md` 存在时，subagent 应优先使用它，减少原始文件读取
3. **升降级正确性**：Phase 2 subagent 的升降级判断与原 inline 版本一致（给定相同的 knowledge 文件和变更描述，输出相同的 risk_level）
4. **结构化输出验证**：subagent 返回必须是可解析的 YAML，不是散文描述
5. **回归验证**：Phase 2 的 5 类依赖图查询（§1-§5）在 subagent 中全部执行，无遗漏

---

## Issue #5: 无主动压缩策略（PreCompact hook 缺失）

### 严重度: Medium

### 数据证据

- 6 次压缩全部是**系统自动触发**，发生在随机时刻
- 压缩摘要大小 13.7K-18.9K chars 不等，说明摘要质量不受控
- 第 5 次压缩（line 1410，18.9K）发生在 impl-verify Skill prompt 刚注入之后——Skill 的完整协议文本可能在压缩中被部分丢失
- 项目中**没有 PreCompact hook**，也没有任何主动压缩管理机制
- 对比 ECC 项目：有 `pre-compact.js` hook 在压缩前保存状态 + `suggest-compact.js` 在逻辑边界建议手动 compact

### 根因分析

两个层面的问题：

1. **压缩时机不可控**：系统在上下文接近极限时自动压缩，可能正好在 Skill 执行中间（如 Round 2 验证中途），导致 Skill 的协议指令被压缩掉，后续行为偏离预期
2. **压缩前无状态保存**：关键的分析结论、工作流阶段、当前 Skill 的执行进度等信息没有在压缩前持久化到文件，压缩后可能丢失

### 解决方案

**A. 新增 PreCompact hook（`hooks/pre-compact.py`）**

在上下文压缩触发前自动执行：

```python
# hooks/pre-compact.py
# 触发时机：PreCompact 事件

def on_pre_compact():
    # 1. 读取当前 session-state.md，确保最新
    # 2. 追加当前工作流阶段到 session-state.md
    #    - current_skill: 当前正在执行的 Skill 名称
    #    - current_step: Skill 内部的执行步骤（如 impl-verify Round 2）
    #    - pending_work: 尚未完成的工作描述
    # 3. 如果有尚未写入文件的分析结论，输出警告：
    #    "⚠️ Context compaction imminent. Unsaved analysis in session."
    # 4. 返回 systemMessage 提示 Claude 在压缩后恢复状态：
    #    "After compaction, read .claude/ecw/session-state.md to restore workflow state."
```

**B. 在 Skill 协议中增加"阶段边界 compact 建议"**

在以下阶段转换点，Skill 主动建议用户手动 `/compact`：

| 阶段转换 | 建议 compact? | 理由 |
|---------|-------------|------|
| domain-collab 完成 → Phase 2 | **是** | domain-collab 12 个 agent 结果已写入 report 文件，对话中的 YAML 可清除 |
| writing-plans 完成 → spec-challenge | **是** | Plan 已写入文件，知识文件内容可清除 |
| spec-challenge 完成 → TDD | **是** | 审查结果已写入 report 文件 |
| TDD 完成 → impl-verify | **是** | 所有代码已 commit，TDD 过程可清除 |
| impl-verify 收敛 → biz-impact-analysis | **是** | 验证结论已输出，实现文件内容可清除 |

**C. 各 Skill 增加 "compact-safe checkpoint" 机制**

每个 Skill 在关键步骤完成后，将关键结论写入 artifact 文件（handoff file），确保即使压缩也不丢信息：

| Skill | Checkpoint 文件 | 内容 |
|-------|----------------|------|
| risk-classifier Phase 1 | `session-state.md` | 已有，保持 |
| requirements-elicitation | `.claude/ecw/session-data/requirements-summary.md` | **新增** |
| domain-collab | `domain-collab-report.md` + `knowledge-summary.md` | 已有，保持 |
| risk-classifier Phase 2 | `.claude/ecw/session-data/phase2-assessment.md` | **新增** |
| writing-plans | `.claude/plans/{feature}.md` | 已有（Plan 文件本身） |
| spec-challenge | `spec-challenge-report.md` | 已有，保持 |
| impl-verify | `impl-verify-findings.md` | 已有（>5 findings 时），改为始终写入 |

### 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `hooks/pre-compact.py` | **新增**：PreCompact hook，在压缩前保存工作流状态 |
| `hooks/hooks.json`（项目级） | 注册 PreCompact hook |
| `skills/risk-classifier/SKILL.md` | Phase 2 完成后写入 `session-data/phase2-assessment.md` |
| `skills/requirements-elicitation/SKILL.md` | 综合分析完成后写入 `session-data/requirements-summary.md` |
| `skills/domain-collab/SKILL.md` | Round 3 完成后增加 compact 建议 |
| `skills/writing-plans/SKILL.md` | Plan 写入后增加 compact 建议 |
| `skills/impl-verify/SKILL.md` | 改为始终写入 findings 文件（不限 >5 条） |

### 验收标准（Red Team）

1. **hook 触发验证**：模拟 PreCompact 事件，hook 应正确读取 session-state.md 并追加当前阶段信息
2. **状态恢复验证**：压缩发生后，新的 assistant turn 应能从 session-state.md 恢复工作流阶段（读取 current_skill, current_step, pending_work）
3. **artifact 完整性验证**：每个 Skill 的 checkpoint 文件包含足够信息让下游 Skill 冷启动（不依赖对话历史）
4. **compact 建议验证**：在 domain-collab → Phase 2 转换点，Skill 输出中包含 compact 建议文本
5. **回归验证**：PreCompact hook 不影响正常工作流——非压缩场景下，hook 不产生副作用

---

## 实施优先级与依赖关系

```
Issue #1 (TDD subagent) ──────────────────── 独立，最高优先
Issue #2 (impl-verify subagent) ──────────── 独立，可与 #1 并行
Issue #3 (writing-plans subagent) ─────┐
Issue #4 (Phase 2 subagent) ───────────┤── 共享 "产出物自治" 基础设施
Issue #5 (PreCompact + artifacts) ─────┘     #5 的 artifact 文件是 #3/#4 的基础
```

建议实施顺序：

1. **先做 Issue #5**（PreCompact + artifacts）——为后续 subagent 化提供状态持久化基础
2. **再做 Issue #1 + #2 并行**——直接消除 5/6 的压缩（TDD 3 次 + impl-verify 2 次）
3. **最后做 Issue #3 + #4**——消除最后 1 次压缩 + 优化 Plan 阶段上下文

---

## 红蓝对抗开发模式

### Blue Team（实现 Agent）

- 按 Issue 逐个实现，每个 Issue 作为一个独立 Task
- 修改 SKILL.md 中的协议文本
- 新增 hooks/pre-compact.py
- 修改后运行 `python tests/static/lint_skills.py` 验证 SKILL 格式
- 每个 Issue 实现后 commit

### Red Team（验证 Agent）

- 基于每个 Issue 的"验收标准"编写验证场景
- 验证方式：
  1. **静态验证**：检查 SKILL.md 修改后的文本是否覆盖所有规则（如 Issue #1 的多维度决策矩阵）
  2. **模式验证**：检查 subagent dispatch 模式是否正确（parallel vs sequential、prompt 模板完整性、返回格式约束）
  3. **回归验证**：确认未修改路径的行为不变
  4. **eval 场景扩展**：在 `tests/eval/scenarios/` 中新增上下文消耗相关的评估场景
- 每个 Issue 的验证独立于实现——Red Team 不看 Blue Team 的实现过程，只看结果

### 对抗规则

- Blue Team 提交后，Red Team 基于验收标准逐条验证
- 验收标准中任一条未通过 → Red Team 输出具体的 failure report（包含 expected vs actual）
- Blue Team 根据 failure report 修复 → 重新提交 → Red Team 重新验证
- 所有验收标准通过 → Issue 标记 Done
