---
name: biz-impact-analysis
description: |
  Triggers business impact analysis for code changes.
  Analyzes which business domains, downstream/upstream flows, external systems,
  and end-to-end paths are affected by the diff.
  Can be invoked manually via /biz-impact-analysis or automatically after CR.
---

# Business Impact Analysis — 业务流程影响分析

在代码变更后，调度 `biz-impact-analyzer` agent 分析变更对业务流程的影响。

## 触发方式

- **手动**：`/biz-impact-analysis` — 分析当前分支 vs master 的全部变更
- **手动（指定范围）**：`/biz-impact-analysis HEAD~3` — 分析最近 N 个 commit
- **自动**：CR 流程完成后自动追加

## 流程

```
┌─────────────────────────────────────────────┐
│ 1. 确定 Diff 范围                            │
│    - 无参数 → git diff master...HEAD         │
│    - 有参数 → git diff {参数}               │
│    - 获取变更文件列表                         │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│ 2. 调度 biz-impact-analyzer agent           │
│    - 传入 diff 范围参数                      │
│    - 等待返回影响分析报告                     │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│ 3. 呈现分析报告                              │
│    - 直接输出 agent 返回的格式化报告           │
│    - 如有未登记的跨域调用，提醒更新依赖图       │
└─────────────────────────────────────────────┘
```

## 调度 Agent 的 Prompt 模板

调度 biz-impact-analyzer agent 时，使用以下 prompt 结构：

```
请分析以下代码变更的业务影响。

## Diff 范围

{diff_range}

## 说明

按照你的 5 步分析流程执行：
1. Diff 解析与域定位
2. 依赖图查询
3. 增量代码扫描
4. 外部系统影响评估
5. 生成影响报告

输出完整的业务影响分析报告。
```

## 参数解析规则

| 输入 | Diff 命令 |
|------|----------|
| `/biz-impact-analysis` | `git diff master...HEAD` |
| `/biz-impact-analysis HEAD~3` | `git diff HEAD~3...HEAD` |
| `/biz-impact-analysis abc123` | `git diff abc123...HEAD` |
| `/biz-impact-analysis abc123 def456` | `git diff abc123...def456` |

## 与 CR 的集成

当 `superpowers:requesting-code-review` 完成后：

1. Code-reviewer agent 完成代码质量审查
2. 调度 biz-impact-analyzer agent，基于同一 diff 范围
3. 两份报告分段呈现：先代码质量，再业务影响

**P0/P1 变更为必要步骤**，P2+ 建议执行。ecw:risk-classifier Phase 1 输出的路由链中已包含 `CR + ecw:biz-impact-analysis`，Phase 1 输出时会将其加入 TaskCreate 的 todo list。

## 注意事项

- 分析结果依赖 ecw.yml `paths.knowledge_common` 下的依赖图数据质量
- 报告中的"分析覆盖度"段落标注了哪些维度可能有遗漏
- 报告中标记的"未登记跨域调用"需要人工确认后更新依赖图
- 报告中标记的"疑似过期条目"需要人工确认后清理
