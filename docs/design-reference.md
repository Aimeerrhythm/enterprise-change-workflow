# ECW 设计参考

ECW 贡献者的参考指南。本文档不由 lint 强制执行——强制规则见 `templates/rules/common/ecw-development.md`。

## Token 预算指南

| Skill 类型 | 目标值 | 示例 |
|-----------|--------|---------|
| 简单单步 | ~2,500 tokens | cross-review |
| 标准多步 | ~4,000 tokens | requirements-elicitation、tdd、biz-impact-analysis |
| 复杂编排器 | ~5,000 tokens | risk-classifier、impl-orchestration |

运行 `python3 tests/static/lint_skills.py --check tokens` 查看当前实际值。警告阈值为 20,000 tokens。

## 模型选择指南

| 模型 | 适用场景 | 示例 |
|-------|----------|---------|
| opus | 深度推理、对抗性审查、跨域分析 | spec-challenge、biz-impact-analysis、domain-collab Round 1 |
| sonnet | 实现、机械执行 | implementer、TDD cycle subagent、spec-reviewer |
| haiku | 保留用于轻量机械任务 | 目前未使用 |

**原则**：模型选择由推理密度决定，而非任务"重要程度"。一个简单但关键的配置变更仍使用 sonnet；一个对 P3 变更的复杂分析仍使用 opus。

模型默认值在 `ecw.yml` 的 `models.defaults.*` 下配置，可按项目覆盖。

## 上下文管理

- **新会话阈值**：上下文超过约 100K tokens 时考虑拆分
- **状态真实来源**：`session-state.md` 是唯一的跨会话恢复状态
- **PreCompact hook**：自动保存检查点——各 skill 无需手动写检查点逻辑
- **`Next` 字段**：每个 skill 在交接前更新此字段；pre-compact 和 session-start hook 用它实现精确恢复

## Subagent 规模分类

| 规模 | Token 范围 | 典型用途 |
|-------|------------|-------------|
| small | <20K tokens | 单文件分析、定向验证 |
| medium | 20-80K tokens | 多文件扫描、域分析 |
| large | >80K tokens | 包含多个知识文件的全局分析 |

用于 Subagent Ledger 条目中的容量规划和超时校准。

## Prompt 工程技巧

### Lost-in-Middle 效应

将关键指令放在 prompt 的**开头**和**结尾**。位于中间的信息所获注意力较少。对于长 agent prompt，Boundary 块应靠近末尾，作为最后的强化。

### 结构化输出

明确指定输出格式（表格优于散文）。当 agent 必须返回数据时，使用带有定义 schema 的 YAML。当 agent 为人类生成报告时，使用带有必要章节标题的 Markdown。

### 常见自我合理化模式

使用"你的想法 → 现实"对照表，预先封堵 Claude 常见的自我合理化路径。每条针对模型可能绕过 skill 协议的一种具体方式。每个 skill 的条目保持唯一——共用的反模式应放在公共位置，不要重复。

### Subagent Boundary 块

每个 agent 模板需要明确的边界声明：
1. 身份声明（"你是一个单任务 agent"）
2. 禁止项（"不要调用/加载/派生其他 skill"）
3. 范围限制（"你唯一的工作是……"）

缺少此声明时，agent 可能尝试调用超出其范围的 skill 或派生子 agent。
