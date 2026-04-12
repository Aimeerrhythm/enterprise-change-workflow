# Enterprise Change Workflow (ECW)

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
  [Completion Verification Hook]
        |
  Business Impact Analysis
```

## Skills & 组件

| 组件 | 类型 | 触发条件 | 说明 |
|------|------|---------|------|
| `ecw:risk-classifier` | Skill | 任何变更/需求/Bug 请求 | P0-P3 风险分级，路由到对应工作流 |
| `ecw:domain-collab` | Skill | 跨域需求（涉及 2+ 域） | 并行域 agent 分析 + coordinator 交叉校验 |
| `ecw:requirements-elicitation` | Skill | 单域 P0/P1 需求 | 系统性提问，确保完全理解需求 |
| `ecw:spec-challenge` | Skill | Plan 产出后（P0, P1 跨域） | 独立对抗性审查，challenge-response 循环 |
| `ecw:biz-impact` | Skill | 实现完成 / CR 后 | Git diff -> 业务影响分析报告 |
| `/ecw-init` | Command | 手动执行 | 初始化项目配置脚手架 |
| `biz-impact-analyzer` | Agent | `ecw:biz-impact` 调度 | 结构化依赖图查询 + 代码扫描 |
| `spec-challenger` | Agent | `ecw:spec-challenge` 调度 | 对抗性技术审查 |
| `verify-completion` | Hook | TaskUpdate(completed) | 自动技术检查：断裂引用、残留引用 |

## 安装

### 前置依赖

- **Claude Code CLI** — ECW 是 Claude Code plugin，需要 CLI 环境
- **superpowers plugin** — 提供 `writing-plans`、`executing-plans`、`systematic-debugging` 等基础 skill

### 第一步：注册 Marketplace

在 `~/.claude/settings.json` 的 `extraKnownMarketplaces` 中添加：

```json
{
  "extraKnownMarketplaces": {
    "enterprise-change-workflow": {
      "source": {
        "source": "github",
        "repo": "Aimeerrhythm/enterprise-change-workflow"
      }
    }
  }
}
```

### 第二步：安装插件

在终端执行：

```bash
claude plugin install ecw@enterprise-change-workflow
```

验证安装成功：

```bash
claude plugin list
```

应能看到 `ecw@enterprise-change-workflow` 在列表中。

### 第三步：启用插件

确认 `~/.claude/settings.json` 的 `enabledPlugins` 中包含：

```json
{
  "enabledPlugins": {
    "ecw@enterprise-change-workflow": true
  }
}
```

> `claude plugin install` 通常会自动添加此条目。如果没有，手动添加。

### 第四步：重启 Claude Code

插件在下次会话启动时加载。退出当前会话，重新启动 Claude Code 即可。

### 第五步：初始化项目配置

在目标项目目录下启动 Claude Code，执行：

```
/ecw-init
```

按提示填充以下配置文件：

```
.claude/ecw/
├── ecw.yml                      # 项目配置：名称、语言、组件类型、扫描模式
├── domain-registry.md           # 域注册表：域定义、知识目录、代码目录
├── change-risk-classification.md # 风险分级校准：因子权重、关键词映射
└── ecw-path-mappings.md         # 代码路径→域映射（biz-impact 使用）
```

### 第六步：配置 CLAUDE.md

在项目的 `CLAUDE.md` 中添加 ECW 集成配置。参考 `templates/CLAUDE.md.snippet`，核心内容：

1. **域级知识路由表** — 关键词→域的映射，供 `ecw:risk-classifier` 和 `ecw:domain-collab` 匹配
2. **自动化规则** — 收到变更类需求时自动调用 `ecw:risk-classifier`
3. **完成验证规则** — 标记完成前的结构化自查要求
4. **影响分析工具区分** — `ecw:domain-collab`（需求阶段）vs `ecw:biz-impact`（代码阶段）

## 知识文件体系

ECW 依赖项目中的知识文件做出准确的域判断和影响分析。知识文件放在 `.claude/knowledge/` 下。

### 跨域公共知识 (`common/`)

| 文件 | 说明 |
|------|------|
| `cross-domain-calls.md` | 域间直接调用矩阵 |
| `mq-topology.md` | MQ Topic 发布/消费关系 |
| `shared-resources.md` | 跨域共享资源表 |
| `external-systems.md` | 外部系统集成清单 |
| `e2e-paths.md` | 端到端关键业务链路 |

### 域级知识（每域一个目录）

| 文件 | 说明 |
|------|------|
| `00-index.md` | 域入口：链路速查、节点定位、Facade 地图 |
| `business-rules.md` | 业务规则：状态流转、判定逻辑、约束条件 |
| `data-model.md` | 数据模型：核心表、字段、关联关系 |

## 完成验证 Hook

ECW 包含一个 PreToolUse hook，在 AI 标记任务完成时自动拦截并执行技术检查：

- **断裂引用检查** — 本次修改的文件中是否引用了不存在的 `.claude/` 路径
- **残留引用检查** — 本次删除的文件是否还被其他文件引用

技术检查失败会阻止任务标记为完成，强制修复后重试。技术检查通过后，会注入语义验证提醒（需求对标、产出验证、残留检查），确保 AI 完成结构化自查。

## Java/Spring 扫描脚本

`scripts/java/` 提供 Java/Spring 项目辅助扫描脚本，用于自动提取：

- 跨域调用关系（`@Resource` / `@DubboReference` 注入分析）
- MQ 拓扑（发布/消费关系）
- 外部系统集成点

```bash
# 在目标项目根目录下执行
bash <plugin-path>/scripts/java/<script-name>.sh
```

扫描结果可直接填入对应的知识文件。

## 支持的项目类型

`ecw.yml` 中通过 `component_types` 和 `scan_patterns` 配置适配不同技术栈：

- **Java/Spring** — BizService、Manager、DO、Controller、Mapper
- **Go** — Handler、Repository、Service
- **Node/TypeScript** — Service、Controller、Middleware
- **Python** — Service、Repository、Handler

## 项目结构

```
enterprise-change-workflow/
├── .claude-plugin/
│   ├── plugin.json              # 插件元数据（name: "ecw"）
│   └── marketplace.json         # Marketplace 描述
├── skills/
│   ├── risk-classifier/         # 风险分级 skill
│   ├── domain-collab/           # 跨域协作分析 skill
│   ├── requirements-elicitation/# 需求澄清 skill
│   ├── spec-challenge/          # 对抗审查 skill
│   └── biz-impact/              # 业务影响分析 skill
├── agents/
│   ├── biz-impact-analyzer.md   # 影响分析 agent
│   └── spec-challenger.md       # 对抗审查 agent
├── commands/
│   └── ecw-init.md              # 项目初始化命令
├── hooks/
│   ├── hooks.json               # Hook 注册
│   └── verify-completion.py     # 完成验证 hook
├── templates/                   # 配置模板
├── scripts/                     # 辅助扫描脚本
├── CLAUDE.md                    # 插件级指引
├── package.json                 # 版本信息
└── README.md
```

## License

MIT
