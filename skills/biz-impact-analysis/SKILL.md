---
name: biz-impact-analysis
description: |
  Use when code changes are complete and need business impact assessment.
  TRIGGER when: impl-verify passes (automatic for P0/P1), or manually via
  /biz-impact-analysis. DO NOT use for pre-implementation requirement analysis
  (use ecw:domain-collab instead).
---

# Business Impact Analysis — 业务流程影响分析

在代码变更后，调度 `biz-impact-analysis` agent 分析变更对业务流程的影响。

## 触发方式

- **手动**：`/biz-impact-analysis` — 分析当前分支 vs master 的全部变更
- **手动（指定范围）**：`/biz-impact-analysis HEAD~3` — 分析最近 N 个 commit
- **自动**：ecw:impl-verify 完成后自动追加

## 流程

1. **确定 Diff 范围** — 无参数用 `git diff master...HEAD`，有参数用 `git diff {参数}`，获取变更文件列表
2. **Coordinator 预处理** — Agent 派发前执行：
   1. 执行 `git diff --stat {diff_range}` 获取变更统计
   2. 执行 `git diff --name-only {diff_range}` 获取文件列表
   3. 读取 `ecw-path-mappings.md`，将文件列表映射到域
   4. 将上述结果填入 Agent prompt，替代完整 diff
3. **调度 biz-impact-analysis agent** — 传入预处理结果，等待返回影响分析报告
4. **呈现分析报告** — 直接输出 agent 返回的格式化报告，如有未登记的跨域调用则提醒更新依赖图

## 调度 Agent 的 Prompt 模板

调度 biz-impact-analysis agent 时，使用以下 prompt 结构：

```
请分析以下代码变更的业务影响。

## Diff 范围

{diff_range}

## 变更文件概要（Coordinator 预处理结果）

{git_diff_stat_output}

## 域定位结果

{file_to_domain_mapping}

## 说明

按照你的 5 步分析流程执行。
注意：完整 diff 内容由 Coordinator 预处理提供了文件列表和域定位。
Step 1 中，只对需要检查方法签名变更的文件执行 `git diff {diff_range} -- {文件路径}`。
Step 3 增量扫描中，只对命中 scan_patterns 的文件读取具体变更内容。
不要对所有文件执行 `git diff {diff_range}` 获取完整变更内容。

请使用中文输出影响分析报告。
```

## 参数解析规则

| 输入 | Diff 命令 |
|------|----------|
| `/biz-impact-analysis` | `git diff master...HEAD` |
| `/biz-impact-analysis HEAD~3` | `git diff HEAD~3...HEAD` |
| `/biz-impact-analysis abc123` | `git diff abc123...HEAD` |
| `/biz-impact-analysis abc123 def456` | `git diff abc123...def456` |

## 与 impl-verify 的集成

当 `ecw:impl-verify` 完成后：

1. impl-verify 完成代码正确性 + 质量验证（零「必须修复」）
2. 调度 biz-impact-analysis agent，基于同一 diff 范围
3. 输出业务影响分析报告

**P0/P1 变更为必要步骤**，P2+ 建议执行。ecw:risk-classifier Phase 1 输出的路由链中已包含 `ecw:impl-verify + ecw:biz-impact-analysis`，Phase 1 输出时会将其加入 TaskCreate 的 todo list。

## 与 Phase 3 的集成

biz-impact-analysis 报告输出后：

1. 如当前为 **P0/P1** 变更（从 `.claude/ecw/session-state.md` 读取风险等级），**立即执行 Phase 3 校准** — 使用 Skill 工具 invoke `ecw:risk-classifier`，附带参数 `--phase3`
2. 如当前为 **P2** 变更，建议执行 Phase 3（非强制，由用户决定）
3. Phase 3 不再需要手动触发 — biz-impact-analysis 完成后自动衔接

如果 TaskList 中有 pending 的 "Phase 3 校准" Task，标记 biz-impact-analysis Task 为 completed 后该 Task 自动解除阻塞。

## Subagent Ledger 更新

Agent 返回后，向 `.claude/ecw/session-state.md` 的 Subagent Ledger 表追加一行：

```
| biz-impact-analysis | analyst | ecw:biz-impact-analysis | large |
```

Scale 参考：small（<20K tokens）、medium（20-80K）、large（>80K）。biz-impact-analysis agent 通常 large（需读取多个知识文件 + 代码扫描）。

## 注意事项

- 分析结果依赖 ecw.yml `paths.knowledge_common` 下的依赖图数据质量
- 报告中的"分析覆盖度"段落标注了哪些维度可能有遗漏
- 报告中标记的"未登记跨域调用"需要人工确认后更新依赖图
- 报告中标记的"疑似过期条目"需要人工确认后清理
