# SKILL.md 修改参考模式

> 从 ECC 提炼 + ECW 现有模式总结，用于指导类别 G/H 的 Skill 改进

## 1. Subagent Dispatch 标准格式

**ECW 现有模式** (writing-plans 为例):
```
dispatch via Agent tool
- description: "..."
- prompt: "coordinator 组装的轻量 prompt"
- model: sonnet
```

**改进后标准格式**:
```
dispatch via Agent tool
- description: "[Skill名]-[Round/Phase]-[功能]"
- prompt: "... (包含: 目标、输入文件路径列表、期望输出格式、错误处理指引)"
- model: {haiku|sonnet|opus} (参照 conventions.md 的 model 选择标准)
- timeout 建议: {60|180|300}s

**返回值处理**:
1. 验证必填字段存在 (如 risk_level, impact_level, findings 等)
2. 格式错误 → 记录 Ledger + 重试一次 (同 model)
3. 重试仍失败 → 降级处理:
   - 验证类 agent: 跳过该 round, 标注 [incomplete: {round_name}]
   - 分析类 agent: 输出 "[degraded]" 标注, 用 coordinator 本地分析替代
   - 实现类 agent: 升级给用户
```

## 2. 错误处理标准模板

**每个步骤的错误处理格式**:

```markdown
### Step N: {步骤名}

{正常流程描述}

**Error handling**:
- **Agent dispatch failed**: 记录 Ledger `[FAILED: {agent}, reason: timeout/error]` → {降级路径}
- **File not found** ({具体文件}): 标注 `[degraded: {file} not found]` → 继续后续步骤
- **Write failed**: 重试一次 → 仍失败则将内容直接输出到会话中, 提示用户手动保存
```

**Ledger 记录格式**:
```
| {Skill名} | {时间} | {状态} | {结果摘要} |
```
状态值: `✅ completed` | `⚠️ degraded` | `❌ failed` | `⏭️ skipped`

## 3. 循环终止标准

| 循环类型 | 最大轮次 | 升级条件 | 示例 Skill |
|---------|---------|---------|-----------|
| 交互问答 | P0:15, P1:10, P2:5 | 用户连续 2 次回答"不确定" | requirements-elicitation |
| 收敛验证 | 5 (已有) | 连续 2 轮 must-fix 数量不减少 | impl-verify |
| 讨论循环 | 3 | 超过 3 轮 "Needs discussion" | spec-challenge |
| Fix-verify | 5 (已有) | 同一 finding 出现 3 次 | impl-verify, cross-review |
| Spec review | 3 | 同一 Task 被 reviewer 拒绝 3 次 | impl-orchestration |
| Re-dispatch | 2 | 同一 Task BLOCKED 2 次 | impl-orchestration |

**升级行为**: 暂停循环 → 汇总当前状态 → AskUserQuestion 请求决策（继续/跳过/调整）

## 4. 检查点写入时机

| Skill | 检查点文件 | 写入时机 |
|-------|-----------|---------|
| risk-classifier | session-data/phase2-assessment.md | Phase 2 subagent 返回后 |
| requirements-elicitation | session-data/requirements-summary.md | 每轮 Q&A 后追加 |
| domain-collab | session-data/domain-round1.md | Round 1 所有 agent 返回后 |
| domain-collab | session-data/domain-round2.md | Round 2 所有 agent 返回后 |
| systematic-debugging | session-data/debug-evidence.md | Phase 1 完成后 |
| tdd | session-data/tdd-cycles.md | 每个 RED-GREEN cycle 完成后追加 |
| impl-verify | session-data/impl-verify-findings.md | 每轮验证完成后 (已有) |

## 5. 知识文件读取防御

```markdown
**Before reading knowledge file**:
1. Check existence: `Read {file_path}` — if file not found:
   - Log: `[Warning: {file_path} not found, analysis degraded]`
   - Continue with available information
   - Mark output as `[degraded]` where this file's input was needed
2. Check basic format: 验证文件非空 + 包含期望的 section header
   - Format error: 尝试 best-effort 解析 + 标注 `[parse warning: {file}]`
```

## 6. Model 选择矩阵 (改进后)

| Subagent 用途 | Model | 理由 |
|-------------|-------|------|
| risk-classifier Phase 2 精确评估 | sonnet | 需要结构化分析能力 |
| domain-collab 域分析 agent | sonnet | 需要深度领域理解 |
| domain-collab 简单域 (impact_level: none 预判) | haiku | 轻量检查即可 |
| requirements-elicitation synthesis | sonnet | 需要综合推理 |
| writing-plans subagent | sonnet | 已有，保持 |
| spec-challenge 对抗审查 | sonnet | 需要批判性思维 |
| impl-orchestration 机械性 Task | haiku | 简单代码修改 |
| impl-orchestration 集成/设计 Task | sonnet | 需要上下文理解 |
| impl-orchestration 架构 Task | opus | 需要深度推理 |
| impl-verify verification rounds | sonnet | 已有，保持 |
| biz-impact-analysis | sonnet | 需要业务理解 |
