# Enterprise Change Workflow (ECW) Plugin

## Overview

ECW 为大型多模块项目提供结构化的变更管理工作流。核心能力：

1. **风险分级** (`ecw:risk-classifier`) — 对代码变更进行 P0~P3 分级，驱动后续流程详略
2. **多域协作分析** (`ecw:domain-collab`) — 跨域需求的并行分析 + 交叉校验
3. **需求澄清** (`ecw:requirements-elicitation`) — 系统性提问直至完全理解需求
4. **实现规划** (`ecw:writing-plans`) — 风险感知的 Plan 编写 + 域上下文注入
5. **对抗审查** (`ecw:spec-challenge`) — 方案产出后的独立对抗性评审
6. **测试先行** (`ecw:tdd`) — 风险差异化的 TDD 流程 + ecw.yml 联动
7. **实现编排** (`ecw:impl-orchestration`) — Subagent 驱动的 Plan 执行 + 风险感知 review
8. **系统调试** (`ecw:systematic-debugging`) — 域知识驱动的根因分析 + 跨域追踪
9. **实现正确性验证** (`ecw:impl-verify`) — 代码 ↔ 需求/规则/Plan/标准 多维度收敛验证
10. **业务影响分析** (`ecw:biz-impact-analysis`) — 代码变更后分析对业务流程的影响
11. **交叉一致性验证** (`ecw:cross-review`) — 文件间结构一致性验证（手动可选工具）

## 工作流

```
ecw:risk-classifier (Phase 1 快速预判)
  ├─ 单域需求 → ecw:requirements-elicitation → Phase 2 → ecw:writing-plans → [P0: ecw:spec-challenge]
  ├─ 跨域需求 → ecw:domain-collab → Phase 2 → ecw:writing-plans → [P0/P1跨域: ecw:spec-challenge]
  ├─ P2 → ecw:writing-plans
  ├─ P3 → 直接实现
  └─ Bug → ecw:systematic-debugging
实现完成后 → ecw:impl-verify → ecw:biz-impact-analysis → [P0/P1: Phase 3 反馈校准]
```

## 依赖

- **无外部插件依赖** — ECW 自包含所有 Skill（writing-plans、tdd、systematic-debugging、impl-orchestration 等），无需安装其他插件。
- **Skill 检查优先级**：ECW 已有 `ecw:risk-classifier` 作为变更类任务的统一入口。收到变更/需求/bug 类请求时，直接走 ecw:risk-classifier，不需要额外的 skill 适用性检查。

## 项目配置

**重要：域路由和业务知识定义在你的项目中，不在本 plugin 中。**

安装后运行 `/ecw-init` 进行项目初始化，或手动创建以下文件：

### 必需文件

| 文件 | 用途 |
|------|------|
| `.claude/ecw/ecw.yml` | 项目配置（名称、语言、组件类型、扫描模式、路径） |
| `.claude/ecw/domain-registry.md` | 域注册表（域定义、知识目录、代码目录） |
| `.claude/ecw/change-risk-classification.md` | 风险因子校准（关键词→等级映射、敏感度定义） |
| `.claude/ecw/ecw-path-mappings.md` | 代码路径→域映射（biz-impact-analysis 使用） |

### ECW 产出物文件（自动生成）

| 文件 | 写入时机 | 用途 |
|------|---------|------|
| `.claude/ecw/session-state.md` | risk-classifier Phase 1 输出后 | ECW 流程状态记录 + Subagent Ledger，新 session 恢复用 |
| `.claude/plans/domain-collab-report.md` | domain-collab Round 3 完成后 | 完整多域协作分析报告 |
| `.claude/ecw/knowledge-summary.md` | domain-collab Round 3 完成后 | 知识文件摘要，跨 skill 复用 |
| `.claude/ecw/spec-challenge-report.md` | spec-challenge agent 返回后 | 对抗评审报告 |
| `.claude/ecw/impl-verify-findings.md` | impl-verify 发现 >5 must-fix 时 | 修复清单（会话内仅输出摘要） |

### 知识文件（按需填充）

| 文件 | 用途 |
|------|------|
| `.claude/knowledge/common/cross-domain-rules.md` | 跨域调用规则与全局约束 |
| `.claude/knowledge/common/cross-domain-calls.md` | 域间直接调用矩阵 |
| `.claude/knowledge/common/mq-topology.md` | MQ Topic 发布/消费关系 |
| `.claude/knowledge/common/shared-resources.md` | 跨域共享资源表 |
| `.claude/knowledge/common/external-systems.md` | 外部系统集成 |
| `.claude/knowledge/common/e2e-paths.md` | 端到端关键链路 |

## 完成验证规则

**声明任务"完成"之前的验证链路：**

1. **`ecw:impl-verify`** — 实现正确性验证，多轮收敛直到零「必须修复」。交叉对照代码 vs 需求/领域知识/Plan/工程标准，同时覆盖代码质量审查（替代 code-reviewer）。
2. **`verify-completion` hook（自动）** — 机械检查：引用完整性、编译、测试、知识同步。技术检查不过会阻止完成。

> hook 由 PreToolUse 自动执行，无需手动调用。hook 的硬拦截包括：断裂引用检查、残留引用检查、Java 编译检查、Java 测试检查（ecw.yml `verification.run_tests` 控制开关）。定向提醒包括：知识文档同步提醒、TDD 测试覆盖提醒（ecw.yml `tdd.check_test_files` 控制开关）。
>
> impl-verify 在标记完成前执行（P3 或纯格式/注释变更可跳过）。发现问题先修，修完再验。**不要把验证推迟到用户要求时才做。**
>
> **实现阶段审查与 impl-verify 的关系**：使用 `ecw:impl-orchestration` 时，其自带的 per-task spec review + code quality review（P0）提供即时反馈，避免错误级联到后续 Task。impl-verify 在实现全部完成后做更高层次的需求/领域知识/Plan/工程标准交叉验证。两者互补，不互相替代。实现策略选择规则见 risk-classifier 的"实现策略选择"章节。
>
> `ecw:cross-review` 作为手动可选工具（`/ecw:cross-review`），适用于文档密集型变更的跨文件结构一致性检查，不在必经链路中。

## 文档同步规则

**代码变更后必须同步对应的知识文件。按变更涉及的层级检查：**

- **项目结构**（模块/组件/依赖/数据模型变更）→ 更新 `project/` 下对应文档
- **业务逻辑**（状态流转/业务规则变更）→ 更新 `.claude/knowledge/<域>/business-rules.md`
- **跨域集成**（调用关系/MQ/共享资源/外部系统/端到端链路）→ 更新 `.claude/knowledge/common/` 下对应文档

## 影响分析工具区分

| 工具 | 阶段 | 输入 | 用途 |
|------|------|------|------|
| `ecw:domain-collab` | **需求阶段**（实现前） | 自然语言需求描述 | 分析需求涉及哪些域、各域需要什么变更、跨域依赖和冲突 |
| `ecw:biz-impact-analysis` | **代码阶段**（实现后） | git diff | 分析已完成的代码变更实际影响了哪些业务流程、外部系统、端到端链路 |

**不要混用**：需求分析阶段用 `ecw:domain-collab`，代码变更后用 `ecw:biz-impact-analysis`。

### 项目 CLAUDE.md 集成

需要在项目 CLAUDE.md 中添加：
1. **域级知识路由表** — 关键词→域的映射，供 ecw:risk-classifier 和 ecw:domain-collab 匹配用

参考 `templates/CLAUDE.md.snippet` 获取模板。

## Skill 触发条件

| Skill | 自动触发 | 手动触发 |
|-------|---------|---------|
| ecw:risk-classifier | 用户提出变更/需求/bug | `/ecw:risk-classifier` |
| ecw:domain-collab | risk-classifier 路由（跨域） | `/ecw:domain-collab <描述>` |
| ecw:requirements-elicitation | risk-classifier 路由（单域 P0/P1） | `/ecw:requirements-elicitation` |
| ecw:writing-plans | 需求分析/Phase 2 完成后（P0-P2） | `/ecw:writing-plans` |
| ecw:spec-challenge | ecw:writing-plans 完成后（P0 任意; P1 仅跨域） | `/ecw:spec-challenge <文件>` |
| ecw:tdd | 实现代码前（P0-P2，risk-classifier 路由） | `/ecw:tdd` |
| ecw:impl-orchestration | Plan 执行时（4+ Tasks，P0/P1） | `/ecw:impl-orchestration` |
| ecw:systematic-debugging | Bug/测试失败（risk-classifier 路由） | `/ecw:systematic-debugging` |
| ecw:impl-verify | 实现完成后（P0-P2） | `/ecw:impl-verify` |
| ecw:biz-impact-analysis | impl-verify 完成后 | `/ecw:biz-impact-analysis [范围]` |
| ecw:cross-review | — | `/ecw:cross-review`（手动可选） |

| Command | 说明 |
|---------|------|
| `/ecw-init` | 初始化项目 ECW 配置 |
| `/ecw-validate-config` | 检查配置完整性和正确性 |
| `/ecw-upgrade` | 升级项目 ECW 配置到最新插件版本 |
