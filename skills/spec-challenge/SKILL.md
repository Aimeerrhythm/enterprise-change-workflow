---
name: spec-challenge
description: |
  Triggers adversarial review of a design spec or solution document.
  Can be invoked manually via /spec-challenge or automatically after writing-plans completes (P0 changes, P1 cross-domain changes).
  Orchestrates: challenge → author response → resolution loop.
---

# Spec Challenge — 方案对抗评审

在方案/设计文档产出后，调度 `spec-challenger` agent 进行独立的对抗性评审，然后由方案作者（你）逐条回应。

## 触发方式

- **手动**：`/spec-challenge <文件路径>` — 对指定文档发起评审
- **手动（无参数）**：`/spec-challenge` — 自动查找当前会话中最近产出的 spec 文件
- **自动**：P0 变更、P1 跨域变更的 writing-plans 完成后，自动触发

## 流程

```
┌─────────────────────────────────────────────┐
│ 1. 收集评审材料                               │
│    - 待评审文档（必须）                         │
│    - 项目知识引用（可选，按需附加）               │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│ 2. 调度 spec-challenger agent                │
│    - 独立上下文（不带作者推理过程）               │
│    - 传入文档内容 + 项目知识                     │
│    - 等待返回评审报告                           │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│ 3. 作者逐条回应                               │
│    对每条致命缺陷（F1, F2, ...）：              │
│    ✅ 同意 → 说明修改方案，立即更新文档           │
│    ❌ 不同意 → 给出具体技术反驳理由               │
│    ❓ 需要确认 → 转给用户决策                    │
│                                              │
│    对每条改进建议（I1, I2, ...）：              │
│    ✅ 采纳 → 更新文档                          │
│    ⏭️ 延后 → 记录到后续迭代                     │
│                                              │
│    对盲区标注：                                 │
│    确认是否需要在文档中明确标注                    │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│ 4. 输出回应摘要                               │
│    展示所有条目的处理结果                        │
│    如有"需要确认"项，等待用户决策                 │
│    所有致命缺陷解决后，标记评审通过               │
└─────────────────────────────────────────────┘
```

## 调度 Agent 的 Prompt 模板

调度 spec-challenger agent 时，使用以下 prompt 结构：

```
请评审以下技术方案文档。

## 待评审文档

{文档完整内容}

## 项目背景（供验证用）

先读取 `.claude/ecw/ecw.yml` 获取 project.name，读取 ecw.yml `paths.domain_registry` 获取域列表。
构造项目背景：
"本项目是一个 {project.name}，包含以下业务域：{从 domain-registry 提取的域中文名列表}"

项目知识文档位于 .claude/knowledge/，包含各域的业务规则、数据模型、节点 Spec。
跨域调用关系记录在 ecw.yml `paths.knowledge_common` 下的 `cross-domain-rules.md`。

{如果有相关的项目知识文件内容，附加在这里}

## 评审要求

按你的评审维度（准确性、信息质量、边界与盲区、健壮性）逐一评审。
严格按规定的输出格式返回评审报告。
```

## 作者回应规则

作为方案作者，在回应 challenger 的质疑时遵循以下规则：

### 对致命缺陷（Fatal）

**必须逐条回应，不能跳过。**

- **同意**：说明具体怎么改，然后立即修改文档。格式：
  ```
  ✅ [F1] 同意 — {修改方案概述}
  ```

- **不同意**：必须给出**具体的技术理由**，不能只说"我认为不是问题"。格式：
  ```
  ❌ [F1] 不同意 — {技术反驳理由}
  ```

- **需要确认**：当你无法判断时，转给用户决策。格式：
  ```
  ❓ [F1] 需要确认 — {问题描述 + 你的倾向 + 需要用户提供的信息}
  ```

### 对改进建议（Improvement）

- **采纳**：更新文档。
- **延后**：记录到文档的"后续迭代"章节。
- 可以批量处理，不需要逐条详细解释。

### 对盲区标注

- 确认每个盲区是否需要在文档的"非目标"或"已知限制"章节中明确标注。
- 如果 challenger 指出的盲区实际上方案已覆盖，指出具体章节。

## 回应摘要格式

所有条目回应完毕后，输出汇总表：

```markdown
## 评审回应摘要

| 编号 | 类型 | 标题 | 处理 | 说明 |
|------|------|------|------|------|
| F1 | 致命 | ... | ✅ 同意并修改 | ... |
| F2 | 致命 | ... | ❌ 不同意 | ... |
| F3 | 致命 | ... | ❓ 需用户确认 | ... |
| I1 | 改进 | ... | ✅ 采纳 | ... |
| I2 | 改进 | ... | ⏭️ 延后 | ... |

**状态**：{所有致命缺陷已解决 → 评审通过 / 有未解决项 → 等待用户决策}
```

## 评审完成条件

- 所有致命缺陷要么被修复，要么被技术理由反驳，要么被用户确认可接受
- 文档已更新反映所有"同意"的修改
- 盲区已在文档中明确标注

## 与流程的集成

### 自动触发场景

writing-plans 完成后，以下场景自动触发 ecw:spec-challenge 对抗审查：

- **P0 变更**（任何域模式）
- **P1 跨域变更**（涉及 2+ 域的高风险变更，跨域耦合风险需要独立审查）

流程：

1. writing-plans 输出 plan 文件
2. **先触发 ecw:spec-challenge** — 对 plan 进行对抗性评审
3. challenge-response 完成后，将更新后的 plan 交给用户 review
4. 用户 review 通过后进入实现

```
ecw:risk-classifier (P0 / P1跨域)
  → ecw:requirements-elicitation / ecw:domain-collab
  → Phase 2
  → writing-plans: write plan
  → ecw:spec-challenge (adversarial review + author response)
  → user review (with challenge results visible)
  → implementation
```

### 手动触发

任何时候对任意 spec/plan 文件执行 `/spec-challenge <文件路径>`。
