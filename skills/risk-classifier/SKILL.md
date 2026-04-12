---
name: risk-classifier
description: >
  Use BEFORE any other skill when user proposes a change, feature, requirement,
  bug fix, or any code modification. Classifies change risk level (P0-P3) and
  determines which downstream workflow to invoke. This skill MUST run before
  ecw:requirements-elicitation. If ecw:requirements-elicitation would normally trigger,
  run risk-classifier first instead.
---

# Risk Classifier

## Overview

对任何代码变更进行风险分级（P0~P3），**驱动后续流程的详略程度**。分三个阶段执行：Phase 1（需求描述阶段，快速预判）、Phase 2（plan 完成后，精确定级）、Phase 3（实现完成后，基于 biz-impact 反馈校准预测准确度）。

**核心原则：** 改日志和改库存扣减的流程不应该一样重。

## Bug 修复路由

bug 修复同样先经过本 skill 进行风险预判，然后串联 `superpowers:systematic-debugging` 进行定位和修复：

```
bug 报告 → risk-classifier（Phase 1，快速预判）
  → systematic-debugging（定位 + 修复）
  → mvn test
  → ecw:biz-impact（如果 P0/P1）
  → Phase 3 校准（自动）
```

不论风险等级，bug 修复都跳过 ecw:requirements-elicitation（bug 不需要需求澄清，需要的是定位和修复）。

## When to Use

- 用户提出任何需求、功能变更、bug 修复、代码修改
- 用户说 "我想要..."、"需要改..."、"加个功能..."、"修一下..."
- **必须在 ecw:requirements-elicitation 之前执行**
- **bug 修复也必须先经过本 skill**，然后路由到 systematic-debugging

**When NOT to use:**
- 纯代码阅读/分析/提问（"这个类是做什么的？"）
- 用户明确说 "按 PX 走"（人工指定等级，跳过自动判定）
- 已经在当前会话中完成过 Phase 1 且等级未被质疑

## Skill Interaction

**本 skill 是所有变更类任务的入口。** 执行完 Phase 1 后，根据风险等级链接到对应的下游 skill：

### 需求类变更 — 单域（Step 1 匹配到 0~1 个域）

| 风险等级 | 下游 skill |
|---------|-----------|
| P0（极高）| → `ecw:requirements-elicitation` → **Phase 2** → `writing-plans` → `ecw:spec-challenge` → 实现 → `ecw:biz-impact` → **Phase 3** |
| P1（高） | → `ecw:requirements-elicitation` → **Phase 2** → `writing-plans` → 实现 → `ecw:biz-impact` → **Phase 3** |
| P2（中） | → `superpowers:writing-plans`（Phase 1 含轻量 MQ 检查，跳过完整需求澄清）|
| P3（低） | → 直接实现 |

### 需求类变更 — 跨域（Step 1 匹配到 2+ 个域）

当需求涉及多个业务域时，用 `ecw:domain-collab`（多域协作分析）**替代** `ecw:requirements-elicitation`。ecw:domain-collab 已包含各域深度分析 + Coordinator 交叉校验，产出足以驱动 plan 编写。

| 风险等级 | 下游 skill |
|---------|-----------|
| P0（极高）| → `ecw:domain-collab`（多域协作）→ **Phase 2** → `writing-plans` → `ecw:spec-challenge` → 实现 → `ecw:biz-impact` → **Phase 3** |
| P1（高） | → `ecw:domain-collab`（多域协作）→ **Phase 2** → `writing-plans` → `ecw:spec-challenge` → 实现 → `ecw:biz-impact` → **Phase 3** |
| P2（中） | → `ecw:domain-collab`（多域协作）→ **Phase 2** → `writing-plans` → 实现 → `ecw:biz-impact`（建议）→ **Phase 3** |
| P3（低） | → `ecw:domain-collab`（多域协作，简化输出）→ 直接实现 |

> **判定方法：** Step 1 域定位时，对照项目 CLAUDE.md 的域路由部分（关键词→域映射表）统计匹配到的域数量。匹配 2+ 个域 = 跨域需求。
>
> **确认节点合并：** risk-classifier 的 AskUserQuestion 一次性输出等级 + 域列表 + 模式 + 后续路由。用户确认后下游 skill（ecw:domain-collab / ecw:requirements-elicitation）**跳过自身的确认步骤**，直接执行。

### Bug 修复类变更

| 风险等级 | 下游 skill |
|---------|-----------|
| 任何等级 | → invoke `superpowers:systematic-debugging`（定位 + 修复）→ mvn test → ecw:biz-impact（P0/P1）→ **Phase 3** |

Bug 修复不走 ecw:requirements-elicitation，但风险等级仍然决定事后的 ecw:biz-impact 要求。

**Phase 2** 在需求分析（ecw:requirements-elicitation / ecw:domain-collab）完成后、writing-plans 之前自动执行（见下方 Phase 2 章节）。

---

## Phase 1：快速预判

### 触发时机

用户描述完需求后，**第一个 skill 触发前**。

### 执行步骤

#### Step 1：关键词提取与域定位

从用户的需求描述中提取：
- **业务关键词** → 映射到域（参考项目 CLAUDE.md 的域路由部分（关键词→域映射表））
- **操作关键词** → 判定操作类型（增删改查、状态变更、消息格式等）
- **敏感词** → 直接触发高风险标记
- **域匹配计数** → 统计匹配到几个不同的域（用于判定单域/跨域路由，参见 Skill Interaction）

**域匹配判定：** 从项目 CLAUDE.md 的域路由部分（关键词→域映射表）读取关键词，逐一匹配用户输入。记录匹配到的域列表和数量，输出到 Phase 1 报告中。

**敏感词判定：** → 读取 ecw.yml `paths.risk_factors` 指定的文件（默认 `.claude/ecw/change-risk-classification.md`）§快速参考 获取完整的关键词→预估等级映射表。命中任一敏感词 → 至少 P1。

#### Step 2：快速查共享资源表

读取 ecw.yml `paths.knowledge_common` 下的 `shared-resources.md`（§3），检查用户提到的类/方法是否在共享资源表中。

→ 读取 ecw.yml `paths.risk_factors` 指定的文件（默认 `.claude/ecw/change-risk-classification.md`）§因子 1：影响范围 获取域依赖数量→风险等级的阈值映射。

**注意：** Phase 1 查 §3（共享资源）+ §2（MQ 拓扑，仅检查用户提到的关键词是否涉及 MQ Topic）。不查 §1/§4/§5（Phase 2 再查）。

**P2 轻量检查：** 对于 P2 单域需求（跳过 ecw:requirements-elicitation，无需求分析产物），Phase 1 的 §3 + §2 检查结果即为最终风险信号。如果发现涉及共享资源或 MQ Topic 的写操作变更，**当场升级为 P1**，不等 Phase 2。

#### Step 3：综合判定

```
总风险 = max(关键词预估等级, 共享资源等级)
跨域判定 = Step 1 匹配到的域数量 >= 2 ? "跨域" : "单域"
```

> 完整的三维因子定义（影响范围 / 变更类型 / 业务敏感度）参见 ecw.yml `paths.risk_factors` 指定的文件 §三维风险因子。Phase 1 只用前两维快速判定，Phase 2 使用完整三维。

如果信息不足以判定，**默认 P2**（宁可多做不能少做）。

根据"总风险 + 跨域判定"查 Skill Interaction 路由表确定后续流程。

### Phase 1 输出格式

先输出简要评估（不超过 5 行）：

```markdown
## 变更风险预判（Phase 1）

**P{X}** | {单域/跨域}（{域列表}）| {多域协作/B/无} | {一句话判定理由}

后续路由：{完整路由链，如 ecw:domain-collab(多域协作) → Phase 2 → writing-plans → 实现 → CR + ecw:biz-impact}
```

然后**立即使用 `AskUserQuestion` 工具**让用户确认（一次性确认等级 + 域 + 路由），不要输出大段文字等用户手动回复。用户确认后下游 skill 直接执行，不再二次确认。

**AskUserQuestion 调用方式：**

```
问题: "风险等级 P{X}，按上述流程继续？"
选项:
  1. "继续（推荐）" — 按当前等级和路由执行
  2. "调整等级" — 升级或降级风险等级（选后追问目标等级）
  3. "只分析" — 完成影响分析，不进入实现
  4. "紧急修复" — 走快速通道，跳过完整流程
```

如果是 **P0/P1 且涉及库存、状态机、MQ 等高敏感变更**，在选项前追加一个多选确认问题：

```
问题: "以下情况是否存在？（影响风险判定）"
multiSelect: true
选项:
  1. "大促前冻结期" — 当前处于发版冻结窗口
  2. "需外部系统配合" — 需要其他团队同步发版
  3. "均不涉及" — 以上都不存在
```

用户选择后直接执行对应路由，不再需要二次确认。

---

## 紧急通道（Fast Track）

### 适用场景

- 线上故障紧急修复（hotfix）
- 用户明确说 "紧急"/"hotfix"/"线上问题"/"先修再补流程"

### 执行逻辑

> 流程步骤和跳过项参见 ecw.yml `paths.risk_factors` 指定的文件 §紧急通道。

核心要点：保留 Phase 1 记录等级 → 1 轮简化确认 → 精简 plan → 实现 + mvn test → 事后补做 ecw:biz-impact（标注 `[紧急通道]`）。

### 紧急通道输出格式

Phase 1 输出中追加：

```markdown
### 模式：紧急通道

> 已进入紧急修复模式，跳过完整需求澄清和对抗审查。
> 修复完成后将补做 ecw:biz-impact 分析。

### 快速确认（3 个问题）
1. 问题现象和影响范围？
2. 修复方案（改什么、怎么改）？
3. 是否有临时止血措施已上线？
```

---

## Phase 2：精确定级

> **一句话**：Phase 1 靠关键词猜，Phase 2 靠依赖图查。P0/P1 需求分析完成后、writing-plans 之前自动执行。

### 快速参考

| 项 | 说明 |
|----|------|
| **谁执行** | risk-classifier 自身（不派 agent） |
| **何时** | ecw:requirements-elicitation / ecw:domain-collab 完成后，writing-plans 之前 |
| **适用** | P0/P1（有需求分析产物） |
| **不适用** | P2（Phase 1 轻量检查已覆盖）、P3 |
| **输入** | 需求分析产出的变更组件列表 |
| **输出** | 精确等级 + 升降级处理 |
| **升级** | 强制补充缺失流程步骤 |
| **降级** | 建议用户可简化，由用户决定 |

**重要：** Phase 1 输出时将 "Phase 2 精确定级" 加入 TaskCreate 的 todo list，确保不遗漏。

### 执行步骤

#### Step 1：提取需求分析产出的变更组件列表

从需求分析结果中提取所有将要修改的：
- ecw:requirements-elicitation → 从需求摘要的"Data Changes"和"Process Flow"章节提取实体/组件
- ecw:domain-collab → 从各域的 `affected_components` YAML 字段提取类名和资源名

> 信息粒度为类级（非方法级），足以做依赖图查询。

#### Step 2：完整依赖图查询

对每个受影响的类/方法：

| 查询 | 数据源 | 目的 |
|------|--------|------|
| 域间调用 | §1 `cross-domain-calls.md` | 谁调用了这个类？这个类调用了谁？（2 跳） |
| MQ 影响 | §2 `mq-topology.md` | 涉及的 Topic 有哪些消费方/发布方？ |
| 共享资源扇出 | §3 `shared-resources.md` | 完整使用方域列表 |
| 外部系统 | §4 `external-systems.md` | 出入站接口影响 |
| 端到端链路 | §5 `e2e-paths.md` | 落在哪条链路的哪个 step |

#### Step 3：变更类型分析

分析 plan 中描述的变更模式：
- 是否涉及状态机变更？
- 是否删除/重命名公开方法？
- 是否修改方法签名？
- 是否涉及 SQL 写操作变更？

#### Step 4：重新评定风险等级

```
Phase 2 等级 = max(影响范围, 变更类型, 业务敏感度)
```

参考 ecw.yml `paths.risk_factors` 指定的文件中的三维因子表。

#### Step 5：与 Phase 1 比较，处理升降级

| 场景 | 动作 |
|------|------|
| Phase 2 > Phase 1（升级） | **强制**：告知用户，补充缺失的流程步骤 |
| Phase 2 < Phase 1（降级） | **建议**：告知用户可简化后续流程，由用户决定 |
| Phase 2 = Phase 1 | 确认判定，继续执行 |

### Phase 2 输出格式

```markdown
## 变更风险精确评估（Phase 2）

### 风险等级：P{X}（Phase 1 预判：P{Y}，{升级/降级/不变}）

### 分级因子
| 因子 | 等级 | 原因 |
|------|------|------|
| 影响范围 | P{X} | {详细说明：涉及哪些共享资源/跨域调用/MQ Topic} |
| 变更类型 | P{X} | {详细说明：状态机/签名/SQL 等} |
| 业务敏感度 | P{X} | {详细说明：库存/任务/订单等} |

### 影响范围明细
- **共享资源：** {列表}
- **跨域调用：** {列表}
- **MQ Topic：** {列表}
- **端到端链路：** {链路编号 + 受影响 step}
- **外部系统：** {列表}

### 等级变更
{升级 → 列出需要补充的流程步骤}
{降级 → 列出可以跳过的流程步骤（建议，用户决定）}
{不变 → "Phase 1 预判准确，按原计划继续"}

### 后续流程（更新）
{根据最终等级列出剩余流程步骤}
```

---

## Phase 3：反馈校准（实现完成后）

> **一句话**：Phase 1/2 靠规则预测，Phase 3 靠 biz-impact 实际数据校验预测准确度，输出配置校准建议。

### 快速参考

| 项 | 说明 |
|----|------|
| **谁执行** | risk-classifier 自身（不派 agent） |
| **何时** | ecw:biz-impact 报告产出后自动执行 |
| **适用** | P0/P1（必做）、P2（建议做） |
| **不适用** | P3、紧急通道（事后补做时执行） |
| **输入** | Phase 1/Phase 2 的预测数据 + ecw:biz-impact 报告 |
| **输出** | 校准建议（不自动修改配置） |

### 触发时机

ecw:biz-impact 报告产出后自动执行。仅当当前会话中 Phase 1 或 Phase 2 产出了风险等级时触发。

### 执行步骤

#### Step 1：对比预测 vs 实际

从 biz-impact 报告中提取实际影响指标，与 Phase 1/Phase 2 的预测对比：

| 维度 | Phase 1 预测 | Phase 2 精确 | biz-impact 实际 | 偏差 |
|------|-------------|-------------|----------------|------|
| 影响域数 | {predicted} | {refined} | {actual} | {+/-N} |
| 跨域调用 | {predicted} | {refined} | {actual} | {+/-N} |
| MQ Topic | {predicted} | {refined} | {actual} | {+/-N} |
| 外部系统 | {predicted} | {refined} | {actual} | {+/-N} |
| 端到端链路 | {predicted} | {refined} | {actual} | {+/-N} |
| 变更文件数 | — | — | {actual} | — |

#### Step 2：判定预测准确性

根据 biz-impact 的实际影响范围，反推"实际应有等级"：

| 场景 | 判定 |
|------|------|
| 预测等级 = 实际应有等级 | **准确** |
| 预测过高（例如 P0 但实际只影响 1 个域、0 MQ） | **过度预警** |
| 预测过低（例如 P2 但实际影响了 3+ 域、多个 MQ） | **漏报** |

#### Step 3：输出校准建议

**偏差显著时**（等级差 ≥ 2 级，或关键维度偏差 ≥ 50%），输出校准建议：

```markdown
## 风险预测校准建议（Phase 3）

### 预测 vs 实际
| 维度 | Phase 1 预测 | Phase 2 精确 | biz-impact 实际 |
|------|-------------|-------------|----------------|
| 风险等级 | P{x} | P{y} | 实际应为 P{z} |
| 影响域数 | {n} | {n} | {n} |
| 跨域调用 | {n} | {n} | {n} |
| MQ Topic | {n} | {n} | {n} |
| 外部系统 | {n} | {n} | {n} |

### 偏差分析
{原因分析：为什么预测不准？}
- 关键词匹配遗漏？→ change-risk-classification.md 需补充关键词
- 共享资源表不全？→ shared-resources.md 需补充使用方域列表
- 域注册表范围不准？→ domain-registry.md 需调整代码目录
- 跨域调用矩阵缺失？→ cross-domain-calls.md 需补充调用关系

### 建议调整
- `change-risk-classification.md`: {具体建议，如"将 XXX 关键词从 P2 提升到 P1"}
- `shared-resources.md`: {如"补充 XXX 共享资源的使用方域列表"}
- `domain-registry.md`: {如"XXX 域的代码目录范围需要扩大"}
- `cross-domain-calls.md`: {如"补充 A→B 的调用关系"}

> 以上为建议，需要用户确认后手动修改配置文件。
```

**预测准确时**，输出简短确认：

```
Phase 3 校准完成：预测等级 P{x} 与实际影响一致，无需调整。
```

**轻微偏差时**（等级差 1 级且关键维度偏差 < 50%），记录但不输出建议：

```
Phase 3 校准完成：预测等级 P{x}，实际接近 P{y}，轻微偏差在可接受范围内。
```

### 注意事项

- Phase 3 **不自动修改任何配置文件**，只输出建议
- 校准建议基于单次变更，建议用户积累多次后批量调整
- 紧急通道的事后 biz-impact 同样触发 Phase 3

---

## 手动触发

除自动触发外，支持以下手动场景：

| 命令 | 用途 |
|------|------|
| `/risk-classify` | 对当前需求手动触发 Phase 1 |
| `/risk-classify P0` | 人工强制指定等级，跳过自动判定 |
| `/risk-classify --recheck` | 重新执行 Phase 2（实现中途发现范围变大时使用） |
| `/risk-classify --hotfix` | 进入紧急通道，走简化修复流程 |

---

## 常见错误

| 错误 | 后果 | 修正 |
|------|------|------|
| Phase 1 没等用户确认就继续 | 用户无法调整等级 | 必须等用户确认后再 invoke 下游 skill |
| P0 变更跳过了 ecw:spec-challenge | 方案盲点未暴露 | 回退，补做 ecw:spec-challenge |
| Phase 2 升级后没有补充流程 | 高风险变更走了低风险流程 | 升级是强制的，必须补充 |
| 降级后直接跳过流程 | 人没确认就简化了 | 降级是建议的，需人确认 |
| 只看关键词不查 §3 | 遗漏共享资源影响 | Phase 1 必须查 §3 |
| 跨域需求走了 ecw:requirements-elicitation | 缺少各域独立分析和交叉审查 | 2+ 域匹配时必须走 ecw:domain-collab |
| CR 完成后忘了跑 ecw:biz-impact | 代码变更的业务影响未评估 | P0/P1 变更 CR 完成后必须调用 `/biz-impact` |
| biz-impact 后跳过 Phase 3 | 预测偏差没有被发现，规则无法改进 | biz-impact 报告产出后必须执行 Phase 3 校准 |
| Phase 3 建议未经用户确认就修改配置 | 单次变更可能有偶然性，自动修改可能引入偏差 | Phase 3 只输出建议，由用户决定是否采纳 |
