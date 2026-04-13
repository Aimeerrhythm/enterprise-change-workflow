---
name: cross-review
description: >
  Structured multi-round consistency verification. Triggered after implementation
  is complete, before marking task as done. Runs dimension-based verification
  rounds until convergence (one clean round with zero findings). Checks both
  intra-file and cross-file consistency. Also invocable manually via /ecw:cross-review.
---

# Cross-Review — 结构化交叉验证

在实现完成后、标记任务完成前，对所有变更文件执行多轮交叉一致性验证，直到一轮零发现才退出。

## 为什么需要

单次自查有确认偏差——作者是自己作品最差的审查者。同一概念在同一文件的不同章节或多个文件中的描述容易出现不一致（表格行数不同、列表遗漏、术语混用）。结构化多维度验证 + 收敛循环能系统性消除这类问题。

## 触发方式

- **自动**：实现完成后，标记 task complete 之前。
- **手动**：`/ecw:cross-review`

## 与其他审查组件的关系

| 组件 | 审什么 | 区别 |
|------|--------|------|
| **ecw:cross-review（本 skill）** | 文件内/跨文件内容一致性、需求完整性 | 多轮收敛循环，聚焦一致性 |
| superpowers:code-reviewer | 代码质量、计划对标、架构 | 独立 agent 一次性审查，聚焦质量 |
| ecw:spec-challenge | 方案盲点、边界条件 | 方案阶段，非实现阶段 |
| verify-completion hook | 引用存在性、编译、知识同步 | 机械硬拦截，非语义检查 |

**互补关系**：cross-review 查一致性，code-reviewer 查质量。P0/P1 变更建议两者都做。

## 执行协议

### Round 1 — 跨文件一致性矩阵

**目标**：同一概念在多个文件中的描述是否一致。

**操作**：

1. 列出本次变更的所有文件（`git diff --name-only` 或从 task context 获取）
2. 提取每个文件中的**结构化内容**：
   - 表格行（markdown table rows）
   - 列表项（bulleted/numbered lists）
   - 枚举值（如"4 项检查"、"6 个知识文件"）
   - 配置项（YAML keys、JSON fields）
   - 维度/字段列表（如对比表的行）
3. 对同一概念出现在 2+ 文件的情况，逐项交叉比对：
   - 表格 A 的行数 = 表格 B 的行数？
   - 列表 A 的条目 = 列表 B 的条目？内容相同？
   - 术语/命名在所有文件中是否一致？（如"Phase 3" vs "Risk Phase 3"）
   - 数量引用（"4 项检查"）是否匹配实际内容？
4. 对每个不一致项，记录：`[文件A:行号] vs [文件B:行号] — 描述差异`

### Round 2 — 需求→实现追踪

**目标**：原始需求/计划的每一项是否都有对应实现。

**操作**：

1. 回溯原始需求描述（用户消息 / plan 文件 / task 描述）
2. 逐项列出需求条目
3. 对每条标注实现位置（文件:行号）或标注"未实现"
4. 检查是否有需求外的额外变更（如计划外新增了功能、修改了不相关的文件）

### Round 3+（条件触发）— 修复副作用检查

**仅当 Round 1 或 Round 2 发现了问题并修复后才触发。**

**操作**：

1. 对修复涉及的文件，重新执行 Round 1 的交叉比对
2. 确认修复没有引入新的不一致
3. 如果本轮又有发现，修复后继续下一轮

### 收敛条件

**最近一轮零发现 → 退出，输出验证通过报告。**

## 输出格式

每轮输出：

```markdown
### Cross-Review Round {N} — {维度名称}

**检查范围**：{文件列表}

**发现**：

| # | 文件A | 文件B | 不一致描述 | 严重度 |
|---|-------|-------|-----------|--------|
| 1 | README.md:148 | ecw-validate-config.md:132 | 知识文件列表差 1 项（缺 cross-domain-rules.md） | 必须修复 |
| 2 | SKILL.md:395 | SKILL.md:320 | Step 4 表格 4 行，Step 1 表格 5 行（缺"外部系统"） | 必须修复 |

**本轮发现 {N} 个问题。修复后将执行 Round {M}。**
```

零发现时输出：

```markdown
### Cross-Review Round {N} — {维度名称}

**检查范围**：{文件列表}

**发现**：无

**本轮零发现，验证通过。**
```

最终通过时输出总结：

```markdown
## Cross-Review 验证通过

经过 {N} 轮验证（修复了 {M} 个问题），所有变更文件的交叉一致性检查通过。
可以标记任务完成。
```

## 约束

- **循环上限**：最多 5 轮。超过 5 轮仍有发现，输出所有未解决项并建议用户介入。
- **可跳过场景**：纯格式修改、仅改注释/日志等明显无业务逻辑变更的场景。
- **不做的事**：不评估代码质量（code-reviewer 的职责）、不分析业务影响（biz-impact-analysis 的职责）、不检查编译/引用（hook 的职责）。

## 常见交叉不一致模式

供 Round 1 重点关注：

| 模式 | 示例 |
|------|------|
| **列表长度不一致** | README 说"6 个知识文件"，validate-config 只检查 5 个 |
| **表格维度遗漏** | 对比表 Step 1 有 5 行维度，Step 4 模板只有 4 行 |
| **术语不统一** | 一处叫"Phase 3"，另一处叫"Risk Phase 3" |
| **组件引用遗漏** | 新增了命令，但 ecw-init 的"下一步"没提到它 |
| **路由链不完整** | 工作流图有某步骤，但 Skill Interaction 表没有 |
| **配置与实现脱节** | 模板增加了字段，但验证命令没检查该字段 |
