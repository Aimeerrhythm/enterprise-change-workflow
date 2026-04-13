# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。

## [0.1.0] - 2025-04-13

ECW (Enterprise Change Workflow) Claude Code 插件首次发布。

### 新增

- **风险分级** (`ecw:risk-classifier`) — 三阶段 P0~P3 风险分级，支持反馈校准
  - Phase 1：基于关键词的快速预判
  - Phase 2：基于完整依赖图（§1-§5）的精确定级
  - Phase 3：实现后根据实际业务影响进行校准
- **多域协作** (`ecw:domain-collab`) — 多域并行分析，三轮流程：独立分析、跨域协商、协调员验证
- **需求澄清** (`ecw:requirements-elicitation`) — 9 维度系统性提问，适用于单域 P0/P1 需求
- **对抗审查** (`ecw:spec-challenge`) — 通过独立 Agent 进行对抗性方案评审，适用于 P0 及 P1 跨域方案
- **交叉验证** (`ecw:cross-review`) — 结构化多轮交叉一致性验证，每轮零发现时收敛
- **业务影响分析** (`ecw:biz-impact-analysis`) — 基于 Git diff 的业务影响分析，委派给专用 Agent 执行
- **Agents**：`biz-impact-analyzer`（5 步影响分析）和 `spec-challenger`（4 维度对抗评审）
- **Commands**：`/ecw-init`（项目初始化向导，支持 Attach/Manual/Scaffold 三种模式）、`/ecw-validate-config`（7 步配置验证）
- **完成验证 Hook** — PreToolUse hook，含 4 项硬拦截（断裂引用、残留引用、Java 编译、Java 测试）和 1 项定向提醒（知识文档同步）
- **Java/Spring 扫描器** — Shell 脚本，用于提取跨域调用、共享资源、MQ 拓扑
- **模板系统** — 配置模板（ecw.yml、domain-registry、risk-classification、path-mappings、calibration-log）和知识文件模板（公共 §1-§5、域级 index/rules/model）
- **CLAUDE.md 集成** — 插件级指引，包含工作流图、Skill 触发条件、完成验证规则

[0.1.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.1.0
