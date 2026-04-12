# Enterprise Change Workflow

给 AI 在大型项目上"改一行代码，影响链路追踪"的能力。

## 解决什么问题

AI 编码助手在处理独立变更时表现出色，但在大型多模块项目中，一个组件的修改可能级联影响多个业务域。ECW 提供结构化的变更管理工作流，自动进行风险分级、跨域影响分析、对抗性审查，确保没有遗漏。

## 工作流总览

```
用户提出需求 / 变更 / Bug
        |
        v
  Risk Classifier (P0-P3)
        |
   +----+----------------+
   |                      |
 单域需求              跨域需求
   |                      |
 Requirements         Domain Collab
 Elicitation          (并行 agent 分析)
   |                      |
   +----+----------------+
        |
  Risk Phase 2 (精确定级)
        |
  Implementation Plan
        |
  [P0/P1: Spec Challenge]
        |
  Implementation
        |
  Business Impact Analysis
```

## Skills 一览

| Skill | 触发条件 | 说明 |
|-------|---------|------|
| `ecw:risk-classifier` | 任何变更/需求/Bug 请求 | P0-P3 风险分级，路由到对应工作流 |
| `ecw:domain-collab` | 跨域需求（涉及 2+ 域） | 并行域 agent 分析 + coordinator 交叉校验 |
| `ecw:requirements-elicitation` | 单域 P0/P1 需求 | 系统性提问，确保完全理解需求 |
| `ecw:spec-challenge` | Plan 产出后（P0, P1 跨域） | 独立对抗性审查，challenge-response 循环 |
| `ecw:biz-impact` | 实现完成 / CR 后 | Git diff -> 业务影响分析报告 |
| `/ecw-init` | 手动执行 | 初始化项目配置脚手架 |

## 快速开始

```bash
# 1. 安装插件
claude plugins install <repo>

# 2. 在目标项目中初始化
/ecw-init

# 3. 填充知识文档
#    按提示编辑 .claude/ecw/ 下的配置文件
#    填充 .claude/knowledge/ 下的业务知识

# 4. 开始使用
#    提出变更需求时 ECW 自动激活，无需手动调用
```

## 前置依赖

- **Claude Code CLI** -- ECW 是 Claude Code plugin，需要 CLI 环境
- **superpowers plugin** -- 提供 `writing-plans`、`executing-plans`、`systematic-debugging` 等基础 skill

## 配置参考

### 项目配置文件 (`.claude/ecw/`)

| 文件 | 说明 |
|------|------|
| `ecw.yml` | 项目配置：名称、语言、组件类型定义、代码扫描模式、路径映射 |
| `domain-registry.md` | 域注册表：域定义、知识目录位置、代码目录范围 |
| `change-risk-classification.md` | 风险分级校准：三维因子权重、关键词到等级映射、敏感度定义 |
| `ecw-path-mappings.md` | 代码路径到域的映射规则，`biz-impact-analyzer` 使用 |

### 知识文件 (`.claude/knowledge/`)

**跨域公共知识** (`common/`):

| 文件 | 说明 |
|------|------|
| `cross-domain-calls.md` | 域间直接调用矩阵 |
| `mq-topology.md` | MQ Topic 发布/消费关系 |
| `shared-resources.md` | 跨域共享资源表 |
| `external-systems.md` | 外部系统集成清单 |
| `e2e-paths.md` | 端到端关键业务链路 |

**域级知识** (每域 `<domain>/` 目录下 3 个文件):

| 文件 | 说明 |
|------|------|
| `00-index.md` | 域入口：链路速查、节点定位、Facade 地图 |
| `business-rules.md` | 业务规则：状态流转、判定逻辑、约束条件 |
| `data-model.md` | 数据模型：核心表、字段、关联关系 |

## Java/Spring 扫描脚本

`scripts/java/` 目录下提供了 Java/Spring 项目的辅助扫描脚本，用于自动提取：

- 跨域调用关系（`@Resource` / `@DubboReference` 注入分析）
- MQ 拓扑（发布/消费关系）
- 外部系统集成点

运行方式：

```bash
# 在目标项目根目录下执行
bash <plugin-path>/scripts/java/<script-name>.sh
```

扫描结果可直接填入对应的知识文件。

## 支持的项目类型

`ecw.yml` 中通过 `component_types` 和 `scan_patterns` 配置适配不同技术栈：

- **Java/Spring** -- BizService、Manager、DO、Controller、Mapper
- **Go** -- Handler、Repository、Service
- **Node/TypeScript** -- Service、Controller、Middleware
- **Python** -- Service、Repository、Handler

## License

MIT
