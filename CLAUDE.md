# Enterprise Change Workflow (ECW) Plugin

## Overview

ECW 为大型多模块项目提供结构化的变更管理工作流。核心能力：

1. **风险分级** (`ecw:risk-classifier`) — 对代码变更进行 P0~P3 分级，驱动后续流程详略
2. **多域协作分析** (`ecw:domain-collab`) — 跨域需求的并行分析 + 交叉校验
3. **需求澄清** (`ecw:requirements-elicitation`) — 系统性提问直至完全理解需求
4. **对抗审查** (`ecw:spec-challenge`) — 方案产出后的独立对抗性评审
5. **交叉验证** (`ecw:cross-review`) — 文件内/跨文件一致性验证，多轮收敛
6. **业务影响分析** (`ecw:biz-impact`) — 代码变更后分析对业务流程的影响

## 工作流

```
ecw:risk-classifier (Phase 1 快速预判)
  ├─ 单域需求 → ecw:requirements-elicitation → Phase 2 → superpowers:writing-plans → [P0: ecw:spec-challenge]
  ├─ 跨域需求 → ecw:domain-collab → Phase 2 → superpowers:writing-plans → [P0/P1跨域: ecw:spec-challenge]
  ├─ P2 → superpowers:writing-plans
  ├─ P3 → 直接实现
  └─ Bug → superpowers:systematic-debugging
实现完成后 → ecw:cross-review → CR → ecw:biz-impact → [P0/P1: Phase 3 反馈校准]
```

## 依赖

- **superpowers** plugin — 本 plugin 的 skill 链接到 `superpowers:writing-plans`、`superpowers:systematic-debugging`、`superpowers:executing-plans` 等。必须先安装 superpowers。

## 项目配置

**重要：域路由和业务知识定义在你的项目中，不在本 plugin 中。**

安装后运行 `/ecw-init` 进行项目初始化，或手动创建以下文件：

### 必需文件

| 文件 | 用途 |
|------|------|
| `.claude/ecw/ecw.yml` | 项目配置（名称、语言、组件类型、扫描模式、路径） |
| `.claude/ecw/domain-registry.md` | 域注册表（域定义、知识目录、代码目录） |
| `.claude/ecw/change-risk-classification.md` | 风险因子校准（关键词→等级映射、敏感度定义） |
| `.claude/ecw/ecw-path-mappings.md` | 代码路径→域映射（biz-impact-analyzer 使用） |

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

1. **`ecw:cross-review`** — 结构化交叉验证，多轮收敛直到零发现。检查文件内/跨文件内容一致性（表格、列表、术语、数量）和需求完整性。
2. **`verify-completion` hook（自动）** — 机械检查：引用完整性、编译、知识同步。技术检查不过会阻止完成。

> hook 由 PreToolUse 自动执行，无需手动调用。hook 的硬拦截包括：断裂引用检查、残留引用检查、Java 编译检查。定向提醒包括：知识文档同步提醒。
>
> cross-review 在标记完成前执行（纯格式/注释变更等可跳过）。发现问题先修，修完再验。**不要把验证推迟到用户要求时才做。**

### 项目 CLAUDE.md 集成

需要在项目 CLAUDE.md 中添加：
1. **域级知识路由表** — 关键词→域的映射，供 ecw:risk-classifier 和 ecw:domain-collab 匹配用
2. **自动化规则** — 收到变更类需求时自动调用 ecw:risk-classifier

参考 `templates/CLAUDE.md.snippet` 获取模板。

## Skill 触发条件

| Skill | 自动触发 | 手动触发 |
|-------|---------|---------|
| ecw:risk-classifier | 用户提出变更/需求/bug | `/ecw:risk-classifier` |
| ecw:domain-collab | risk-classifier 路由（跨域） | `/ecw:domain-collab <描述>` |
| ecw:requirements-elicitation | risk-classifier 路由（单域 P0/P1） | `/ecw:requirements-elicitation` |
| ecw:spec-challenge | writing-plans 完成后（P0/P1跨域） | `/ecw:spec-challenge <文件>` |
| ecw:cross-review | 实现完成后 | `/ecw:cross-review` |
| ecw:biz-impact | CR 完成后 | `/ecw:biz-impact [范围]` |

| Command | 说明 |
|---------|------|
| `/ecw-init` | 初始化项目 ECW 配置 |
| `/ecw-validate-config` | 检查配置完整性和正确性 |
