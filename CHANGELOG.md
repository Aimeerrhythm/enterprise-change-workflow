# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。

## [0.2.1] - 2026-04-14

### 修复

- **`spec-challenge` 用户决策权缺失** — spec-challenger 报告返回后 AI 直接自行回应所有致命缺陷，用户无参与机会。改为：展示报告原文 → 逐条 AskUserQuestion 让用户选择处理方式 → AI 按用户决策执行 → 用户最终确认通过

## [0.2.0] - 2026-04-14

### 新增

- **TDD 流程集成** — 在 ECW 工作流中嵌入测试先行（TDD）阶段
  - `risk-classifier` 路由表在实现步骤前插入 TDD:RED（P0-P2 强制，P3 推荐，紧急通道跳过）
  - Bug 修复路由嵌入复现测试步骤（TDD:RED → 修复 GREEN）
- **`/ecw-upgrade` 升级命令** — 版本化项目配置升级，支持版本检测、迁移列表、逐步执行、幂等保护
- **版本化迁移模板体系** — `templates/upgrades/{version}/` 目录结构，每个版本包含 migration.md + snippet 模板
- **ecw.yml `tdd` 配置节** — 控制 TDD 流程行为（enabled / check_test_files / base_test_class）
- **ecw.yml `ecw_version` 字段** — 跟踪项目 ECW 配置版本，`/ecw-upgrade` 基于此判断升级状态

### 增强

- **`impl-verify` Round 3 测试验证** — 新增测试覆盖、测试质量、测试先行三个验证维度
- **`impl-verify` 偏差模式** — 新增断言缺失、Mock 滥用两个常见偏差模式
- **完成验证 Hook** — 新增 TDD 测试覆盖提醒（非阻塞），检查 BizService/Manager 是否有对应测试文件
- **CLAUDE.md.snippet 职责边界重构** — snippet 瘦身为纯域路由模板，文档同步规则/影响分析工具区分等通用规则移至插件 CLAUDE.md
- **升级命令健壮性** — 部分迁移失败时不更新版本号，支持重跑修复

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

[0.2.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.2.0
[0.1.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.1.0
