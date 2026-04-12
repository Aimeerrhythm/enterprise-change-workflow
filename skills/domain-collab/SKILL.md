---
name: domain-collab
description: |
  Use when user describes a business requirement spanning 2+ domains.
  Triggers multi-domain collaborative analysis: parallel domain agents + coordinator cross-check.
  TRIGGER when: requirement involves 2+ domain keywords defined in project CLAUDE.md routing table,
  user asks "分析影响", "影响哪些域", or risk-classifier routes here for cross-domain needs.
  DO NOT TRIGGER when: single-domain need (use ecw:requirements-elicitation), already have code diff
  (use ecw:biz-impact), pure technical refactoring with no business logic change.
---

# Domain Collab — 多域协作分析

接收涉及 2+ 域的自然语言需求，并行派发域专属 Agent 进行分析，Coordinator 交叉校验后输出结构化报告。

> **单域需求** 由 `ecw:requirements-elicitation` 处理，本 skill 专注多域场景。

## 触发方式

- **手动**: `/domain-collab <需求或改动描述>`
- **自动识别**: 用户描述业务需求时触发

## 前置步骤

1. 读取 ecw.yml `paths.domain_registry` 指定的文件（默认 `.claude/ecw/domain-registry.md`）获取域定义
2. 确认 ecw.yml `paths.knowledge_common` 下的 `cross-domain-rules.md` 存在

## 流程总览

```
用户输入需求/改动描述
        │
        ▼
┌─────────────────────┐
│ Phase 1: 域识别      │
│ 对照域注册表关键词    │
│ 匹配涉及的域         │
└────────┬────────────┘
         │
    ┌────┴────┐
    ▼         ▼
 2+ 域      0~1 域
 继续分析   → 提示：单域走 ecw:requirements-elicitation
```

## Phase 1: 域识别

1. 从项目 CLAUDE.md 的域路由部分（关键词→域映射表）读取关键词，匹配用户输入，识别涉及的域
2. 从 domain-registry 读取匹配域的元数据（知识目录、代码目录等）
3. 判断是否适用：
   - 匹配 0 个域 → 提示用户："无法识别涉及的业务域，请补充描述或指定域名"
   - 匹配 1 个域 → 提示："单域需求建议使用 `/requirements-elicitation`，本 skill 专注多域协作分析"
   - 匹配 2+ 域 → 继续执行协作分析
4. 如果由 risk-classifier 调用并已传入域列表，**跳过确认**，直接执行。
5. 如果手动触发（`/domain-collab`），向用户确认："识别到涉及 {域列表}，将进行多域协作分析。"

---

## 多域协作分析（2 轮）

### Round 1: 独立分析（并行）

为每个匹配到的域派发一个 Agent（使用 Agent tool，`subagent_type: general-purpose`）。

**前置步骤（Coordinator 在派发 Agent 前执行）：** 读取 `.claude/ecw/ecw.yml` 获取 project.name 和 component_types，读取 ecw.yml `paths.domain_registry` 获取域定义。

**所有域 Agent 使用统一的 prompt 模板：**

```
你是 {project_name} {domain_name}域专家 Agent。你的任务是分析一个需求对你负责的域的影响。
（project_name 从 `.claude/ecw/ecw.yml` 读取）

## 你的域信息
- 域ID: {domain_id}
- 域名: {domain_name}
- 职责: {description}

## 你的知识文档（必须按顺序读取）
1. 先读知识入口: {knowledge_root}{index} — 了解域整体结构
2. 再读业务规则: {knowledge_root}{business_rules} — 了解核心约束
3. 再读数据模型: {knowledge_root}{data_model} — 了解实体和状态
4. 根据需求关键词，定位到相关链路/节点文档并读取
{extra_knowledge_lines}

## 代码目录（需要时可以 grep 验证）
- 主目录: {code_root}
{related_code_dirs}

## 需求描述
---
{user_requirement}
---

## 分析要求
1. 基于你的知识文档分析需求对本域的影响
2. 识别需要变更的组件（从 `.claude/ecw/ecw.yml` 的 `component_types` 字段读取可选值）
3. 识别状态流转变化
4. 识别可能影响其他域的风险点
5. 不要猜测，只基于你读到的文档和代码做判断
6. 如果本域完全不受影响，说明原因

## 输出格式（严格按此 YAML 格式输出，用 ```yaml 代码块包裹）
domain: {domain_id}
impact_level: none | low | medium | high
summary: "一句话概述需求对本域的影响"
affected_components:
  - type: "从 ecw.yml component_types 读取可选值"
    name: "类名或资源名"
    change: "需要做什么变更"
state_changes:
  - entity: "实体名"
    from: "原状态"
    to: "新状态"
    trigger: "触发条件"
cross_domain_risks:
  - target: "目标域ID"
    type: "direct_call | mq | shared_resource"
    resource: "资源名"
    reason: "为什么可能受影响"
notes: "其他需要注意的事项"
```

**Coordinator 操作步骤：**
1. 从 domain-registry 读取每个匹配域的元数据
2. 用上方模板填充变量，为每个域生成 prompt
3. 使用 Agent tool 并行派发所有域 Agent（在一条消息中发出多个 Agent tool 调用）
4. 收集所有 Agent 返回的 YAML 结果

### Round 2: Coordinator 交叉校验与汇总

**Coordinator 自己完成以下步骤（不派发 Agent）：**

**2a. 跨域冲突检测**

遍历所有域的 `cross_domain_risks`，检查：
- 是否有两个域对同一资源提出了不兼容的变更 → 标记为"域间冲突"
- 是否有域 A 的 `cross_domain_risks` 指向域 B，但域 B 报了 `impact_level: none` → 标记为"疑似遗漏"

**2b. 跨域规则校验（遗漏检测）**

读取以下文件做最终校验（按需读取，不要一次全部读取）：
- `cross-domain-calls.md` → 验证各域提到的直接调用关系是否登记
- `mq-topology.md` → 验证各域提到的 MQ 关系是否登记
- `shared-resources.md` → 检查是否有被忽略的共享资源影响

**3c. 代码验证**

对每个 `affected_component` 执行 Grep 验证。从 ecw.yml `component_types` 读取组件类型及其对应的验证模式：
- 服务层组件 → `Grep pattern="class {name}" path=项目根目录`
- 消息队列组件 → `Grep pattern="{name}" path=项目根目录`
- 领域模型组件 → `Grep pattern="class {name}" path=领域模型目录`

标记验证结果：
- 找到 → 已验证
- 未找到 → 文档过期（知识文档说有但代码中找不到）
- 代码中存在但知识文档未提及 → 未登记（建议补充到知识文档）

对每个 `cross_domain_risk`：
- `Grep pattern="{resource}" path=项目根目录` 确认调用关系确实存在

**3d. 输出报告**

```markdown
# 多域协作分析报告

## 需求概述
{user_requirement}

## 涉及域总览
| 域 | 影响等级 | 变更组件数 | 预估文件数 | 概述 |
|---|---------|----------|----------|------|
| {domain_name} | {impact_level} | {count} | {estimated_files} | {summary} |

## 各域详细分析

### {domain_name}域
**影响等级**: {impact_level}
**概述**: {summary}

**需要变更的组件：**
| 类型 | 名称 | 变更内容 | 验证 |
|------|------|---------|------|
| {type} | {name} | {change} | verified/stale |

**状态变更：**
- {entity}: {from} → {to}（{trigger}）

**跨域风险：**
- → {target}: {reason}（{type}: {resource}）

### （下一个域...）

## Coordinator 交叉校验发现
### 遗漏检测
- {domain}: 域 A 指出 cross_domain_risk 指向 {domain}，但 {domain} 报了 none — 建议确认

### 域间冲突
- {domain} vs {with_domain}: {description}
  建议: {suggestion}

## 跨域依赖与实施顺序
（根据 cross_domain_risks 的依赖关系，给出建议的实施顺序）
1. 先改 {被依赖域}（被其他域调用/消费）
2. 再改 {依赖域}
3. 最后改 {下游域}

## 代码验证结果
- verified: {name} — 已确认存在
- stale: {name} — 知识文档记录有但代码中未找到，建议确认

## 风险点汇总
- {各域 notes 中的注意事项}
```

---

---

## 兜底逻辑

如果所有域 Agent 返回 `impact_level: none`：

1. 检查用户输入是否涉及共享层关键词：
   - `CoreBizService`, `Manager`, `common`, `infra`, `util`, `share`
2. 如果涉及：
   - 读取 `shared-resources.md`，查找相关共享资源的所有使用方域
   - 输出警告："此改动不属于特定业务域，但涉及共享资源 {resource}，被 {域列表} 使用，建议逐一确认影响"
3. 如果不涉及：
   - 输出："分析完成，未发现业务域影响。此改动可能是纯技术改造。"

---

## 后续衔接：risk-classifier Phase 2

**协作分析报告输出后，立即执行 risk-classifier Phase 2（精确定级）。**

Phase 2 会基于本 skill 产出的协作分析报告（各域 `affected_components`、`cross_domain_risks`、Coordinator 交叉校验发现）重新评估风险等级。Phase 2 完成后再进入 `writing-plans`。

**不要跳过 Phase 2 直接进入 writing-plans** — 协作分析可能发现 Phase 1 未预见的跨域依赖，导致等级需要升级。

衔接流程：
```
ecw:domain-collab 报告 → risk-classifier Phase 2 → writing-plans → [P0/P1跨域: ecw:spec-challenge] → 实现
```

---

## 注意事项

- 每轮 Agent 派发使用 Agent tool 的并行调用（单条消息多个 Agent tool call）
- Agent prompt 中的变量用 domain-registry 的数据填充
- 代码验证使用 Grep tool，不使用 bash grep
- 跨域规则文件按需读取，不要一次全部读入
- 分析结果中的每个跨域风险都要标注来源（知识文档 / 跨域规则 / 代码扫描）
