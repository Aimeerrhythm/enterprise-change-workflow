# Enterprise Change Workflow (ECW)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.6.5-blue.svg)

[English](README.md)

> 给 AI 在大型项目上"改一行代码，追踪全链路影响"的能力。

## 解决什么问题

AI 编码助手在处理独立变更时表现出色，但在大型多模块项目中，一个组件的修改可能级联影响多个业务域。典型痛点：

- 改了一个 Facade 方法签名，不知道有 5 个其他域在调用它
- 修了一个 MQ 消息格式，遗漏了 3 个外部系统的消费方
- 做了一个"简单需求"，实际涉及状态机变更、共享资源、端到端链路

ECW 提供结构化的变更管理工作流，让 AI 在动手之前先评估风险、分析影响、交叉验证，确保没有遗漏。

## 核心概念

### 三阶段风险分级

ECW 的核心是对变更进行 **P0~P3 四级风险分级**，驱动后续流程的详略程度：

| 等级 | 风险 | 流程详略 | 典型场景 |
|------|------|---------|---------|
| **P0** | 极高 | 全流程：需求澄清 → 精确定级 → 完整方案 → 对抗审查 → 实现 → 实现验证 → 影响分析 → 校准 | 多域状态机变更、核心链路改造 |
| **P1** | 高 | 完整流程但跳过对抗审查（跨域除外） | 共享资源修改、MQ 消息格式变更 |
| **P2** | 中 | 简化流程：方案 → 实现 → 实现验证 → 影响分析 | 单域新增字段、局部逻辑调整 |
| **P3** | 低 | 直接实现 | 日志调整、文案修改、配置更新 |

**核心原则：改日志和改库存扣减的流程不应该一样重。**

### 三个阶段

| 阶段 | 时机 | 数据源 | 目的 |
|------|------|--------|------|
| **Phase 1** | 用户描述需求后 | 关键词匹配 + 共享资源表 | 快速预判风险等级，确定流程路径 |
| **Phase 2** | 需求分析完成后 | 完整依赖图（§1~§5） | 精确定级，必要时升降级 |
| **Phase 3** | 实现 + 影响分析完成后 | biz-impact-analysis 报告 | 校准预测准确度，改进分级规则 |

### 知识驱动的影响分析

ECW 依赖项目级知识文件做出精准判断。五类跨域知识构成依赖图：

| 编号 | 知识文件 | 内容 | 谁使用 |
|------|---------|------|--------|
| §1 | `cross-domain-calls.md` | 域间直接调用矩阵 | Phase 2, domain-collab, biz-impact-analysis |
| §2 | `mq-topology.md` | MQ Topic 发布/消费关系 | Phase 1(轻量), Phase 2, biz-impact-analysis |
| §3 | `shared-resources.md` | 2+ 域共享的服务/组件 | Phase 1, Phase 2, biz-impact-analysis |
| §4 | `external-systems.md` | 外部系统集成清单 | Phase 2, biz-impact-analysis |
| §5 | `e2e-paths.md` | 端到端关键业务链路 | Phase 2, biz-impact-analysis |

## 工作流总览

```
用户提出需求 / 变更 / Bug
        |
        v
  Risk Classifier — Phase 1（快速预判 P0~P3）
        |
   +----+----+----------------+--------+
   |         |                |        |
 单域需求  跨域需求(2+域)    P2/P3   Bug
   |         |                |        |
 Requirements  Domain Collab  |   Systematic
 Elicitation   (并行 agent    |   Debugging
 (P0/P1)        分析+交叉校验) |   (定位+修复)
   |         |                |        |
   +----+----+                |        |
        |                     |        |
  Phase 2（精确定级）          |        |
        |                     |        |
  Implementation Plan  <------+        |
        |                              |
  [P0; P1 跨域: Spec Challenge]          |
        |                              |
  Implementation  <--------------------+
        |
  Impl-Verify（实现正确性 + 质量验证）
        |
  Business Impact Analysis
        |
  [P0/P1: Phase 3 反馈校准]
        |
  标记完成 → Completion Verification Hook（自动技术检查）
```

## 组件一览

### Skills（11 个）

| 组件 | 触发条件 | 说明 |
|------|---------|------|
| `ecw:risk-classifier` | 任何变更/需求/Bug | P0-P3 风险分级 + 流程路由，三阶段（预判→精确→校准） |
| `ecw:domain-collab` | 跨域需求（2+ 域） | 并行域 agent 独立分析 → 相互评估 → Coordinator 交叉校验 |
| `ecw:requirements-elicitation` | 单域 P0/P1 需求 | 9 维度系统性提问，确保完全理解需求 |
| `ecw:writing-plans` | 需求分析后（P0-P2） | 风险感知实现规划 + 域上下文注入 + 下游自动衔接 |
| `ecw:spec-challenge` | Plan 产出后（P0; P1 仅跨域） | 调度独立 agent 对方案进行对抗性审查，challenge-response 循环 |
| `ecw:tdd` | 实现代码前（P0-P2） | 风险差异化测试先行 + ecw.yml 联动 |
| `ecw:impl-orchestration` | Plan 执行（4+ Tasks，P0/P1） | 每 Task 独立 subagent + 风险感知 review 门控 |
| `ecw:systematic-debugging` | Bug/测试失败/异常行为 | 域知识驱动根因分析 + 跨域追踪（§1-§5） |
| `ecw:impl-verify` | 实现完成后（P0-P2） | 多轮收敛：代码 ↔ 需求/规则/Plan/工程标准，严重度分级退出 |
| `ecw:biz-impact-analysis` | impl-verify 完成后 | Git diff → 调度 agent 分析业务影响，输出结构化报告 |
| `ecw:cross-review` | 仅手动（`/ecw:cross-review`） | 跨文件结构一致性验证，用于文档密集型变更（可选工具） |

### Agents（7 个）

| 组件 | 调度方 | 说明 |
|------|--------|------|
| `biz-impact-analysis` | `ecw:biz-impact-analysis` | 5 步分析：Diff 解析 → 依赖图查询 → 代码扫描 → 外部系统评估 → 报告生成 |
| `spec-challenge` | `ecw:spec-challenge` | 4 维评审：准确性 / 信息质量 / 边界与盲区 / 健壮性 → 致命缺陷 + 改进建议 |
| `domain-analyst` | `ecw:domain-collab` | R1 独立域分析 — 各域 agent 独立评估影响范围 |
| `domain-negotiator` | `ecw:domain-collab` | R2 跨域协商 — 各域相互评估对方方案 |
| `implementer` | `ecw:impl-orchestration` | 按 Task 实现，含 Fact-Forcing Gate 事实溯源 |
| `spec-reviewer` | `ecw:impl-orchestration` | 按 Task 规格合规审查 |
| `impl-verifier` | `ecw:impl-verify` | 并行 4 轮验证（需求/域规则/Plan/工程标准） |

### Commands（3 个）

| 组件 | 说明 |
|------|------|
| `/ecw-init` | 项目初始化向导（3 种模式：Attach/Manual/Scaffold） |
| `/ecw-validate-config` | 验证 ECW 配置完整性（7 步检查，输出 pass/warn/fail 报告） |
| `/ecw-upgrade` | 升级项目 ECW 配置到最新插件版本（幂等迁移，部分失败保护） |

### Hooks（6 个事件点，Dispatcher 架构）

ECW 使用统一的 Dispatcher 模式管理 Hook。`hooks.json` 注册 6 个事件点：

| 事件 | 文件 | 说明 |
|------|------|------|
| `SessionStart` | `session-start.py` | 自动注入 session-state / checkpoint / ecw.yml 上下文 + instinct |
| `Stop` | `stop-persist.py` | Marker-based 状态持久化 |
| `PreToolUse` | `dispatcher.py` | 统一调度器，含 5 个子模块（见下） |
| `PostToolUse` | `post-edit-check.py` | 反模式检测（Edit/Write） |
| `PreCompact` | `pre-compact.py` | 上下文压缩前恢复引导注入 |
| `SessionEnd` | `session-end.py` | 会话结束清理 |

**Dispatcher 子模块**（风险等级 Profile 门控：P0→strict, P1/P2→standard, P3→minimal）：

| 子模块 | Profile | 说明 |
|--------|---------|------|
| `verify-completion` | minimal, standard, strict | 完成验证（4 项硬拦截 + 1 项提醒） |
| `config-protect` | minimal, standard, strict | 阻止 AI 修改 ECW 关键配置文件 |
| `compact-suggest` | minimal, standard, strict | 基于 tool-call 计数的主动压缩建议 |
| `secret-scan` | standard, strict | 敏感数据检测（AWS 密钥、JWT、GitHub Token、私钥） |
| `bash-preflight` | standard, strict | 危险命令预检（--no-verify、push --force、rm -rf） |

**verify-completion 硬拦截（失败 → 阻止完成）：**
1. 断裂引用检查 — 修改的文件引用了不存在的 `.claude/` 路径
2. 残留引用检查 — 删除的文件仍被其他文件引用
3. Java 编译检查 — 修改 `.java` 文件时自动执行 `mvn compile`
4. Java 测试检查 — 修改 `.java` 文件时自动执行 `mvn test`（受 `ecw.yml` `verification.run_tests` 控制）

## 安装

### 前置依赖

- **Claude Code CLI** — ECW 是 Claude Code plugin，需要 CLI 环境

### Step 1：注册 Marketplace

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

### Step 2：安装插件

```bash
claude plugin install ecw@enterprise-change-workflow
```

验证安装成功：

```bash
claude plugin list
# 应能看到 ecw@enterprise-change-workflow
```

### Step 3：启用插件

确认 `~/.claude/settings.json` 的 `enabledPlugins` 中包含：

```json
{
  "enabledPlugins": {
    "ecw@enterprise-change-workflow": true
  }
}
```

> `claude plugin install` 通常会自动添加此条目。如果没有，手动添加。

### Step 4：重启 Claude Code

插件在下次会话启动时加载。退出当前会话，重新启动 Claude Code。

### Step 5：初始化项目配置

在目标项目目录下启动 Claude Code，执行：

```
/ecw-init
```

初始化向导支持 3 种模式：

| 模式 | 适用场景 | 创建内容 |
|------|---------|---------|
| **Attach** | 项目已有文档体系 | 仅 ECW 配置文件（5 个），不动现有文档 |
| **Manual** | 文档在非标准位置 | 配置文件 + 用户指定路径 |
| **Scaffold** | 全新项目 | 配置文件 + 完整知识文件模板 |

生成的配置文件：

```
.claude/ecw/
├── ecw.yml                      # 项目配置：名称、语言、组件类型、扫描模式、验证设置
├── domain-registry.md           # 域注册表：域定义、知识目录、代码目录
├── change-risk-classification.md # 风险分级校准：因子权重、关键词映射
├── ecw-path-mappings.md         # 代码路径→域映射（biz-impact-analysis 使用）
└── calibration-log.md           # Phase 3 校准历史（自动追加）
```

### Step 6：配置项目 CLAUDE.md

在项目的 `CLAUDE.md` 中添加 ECW 集成配置。参考 `templates/CLAUDE.md.snippet`，核心内容：

1. **域级知识路由表** — 关键词→域的映射，供 risk-classifier 和 domain-collab 匹配
2. **完成验证规则** — 标记完成前的结构化自查要求
3. **影响分析工具区分** — `ecw:domain-collab`（需求阶段）vs `ecw:biz-impact-analysis`（代码阶段）

### Step 7：填充知识文件

知识文件质量直接决定影响分析的准确度。Java/Spring 项目可使用内置扫描脚本自动提取：

```bash
# 在目标项目根目录下执行
bash <plugin-path>/scripts/java/scan-cross-domain-calls.sh <project_root> <path_mappings_file>
bash <plugin-path>/scripts/java/scan-shared-resources.sh <project_root> <path_mappings_file>
bash <plugin-path>/scripts/java/scan-mq-topology.sh <project_root>
```

扫描结果输出 Markdown 表格到 stdout，可直接填入对应的知识文件。扫描基于 grep 启发式，高召回但可能有误报，建议人工审查后提交。

### 验证安装

```
/ecw-validate-config
```

该命令会执行 7 步检查，输出每个配置文件的 pass/warn/fail 状态，帮助你确认配置完整性。

## 知识文件体系

ECW 依赖项目中的知识文件做出准确的域判断和影响分析。知识文件放在 `.claude/knowledge/` 下。

### 跨域公共知识（`common/`）

| 文件 | 说明 | Phase 1 | Phase 2 | biz-impact-analysis |
|------|------|---------|---------|------------|
| `cross-domain-rules.md` | 索引文件，知识使用指南 | — | 参考 | 参考 |
| `cross-domain-calls.md` (§1) | 域间直接调用矩阵 | — | 查询 | 查询 |
| `mq-topology.md` (§2) | MQ Topic 发布/消费关系 | 关键词 | 查询 | 查询 |
| `shared-resources.md` (§3) | 跨域共享资源表 | 查询 | 查询 | 查询 |
| `external-systems.md` (§4) | 外部系统集成清单 | — | 查询 | 查询 |
| `e2e-paths.md` (§5) | 端到端关键业务链路 | — | 查询 | 查询 |

### 域级知识（每域一个目录）

| 文件 | 说明 |
|------|------|
| `00-index.md` | 域入口：链路速查、节点定位、Facade 地图、外部系统交互 |
| `business-rules.md` | 业务规则：并发控制、幂等性、状态机、验证规则、跨域约束 |
| `data-model.md` | 数据模型：核心表结构、枚举定义、ER 关系、索引 |

## 支持的项目类型

`ecw.yml` 中通过 `component_types` 和 `scan_patterns` 配置适配不同技术栈：

| 技术栈 | 典型组件类型 | 扫描模式 |
|--------|------------|---------|
| **Java/Spring** | BizService, Manager, DO, Controller, Mapper | @Resource, @DubboReference, RocketMQ |
| **Go** | Handler, Repository, Service | import, interface |
| **Node/TypeScript** | Service, Controller, Middleware | import/require, EventEmitter |
| **Python** | Service, Repository, Handler | import, Celery |

## 项目结构

```
enterprise-change-workflow/
├── .claude-plugin/
│   ├── plugin.json              # 插件元数据
│   └── marketplace.json         # Marketplace 描述
├── skills/                      # 11 个核心 Skill
│   ├── risk-classifier/         # 风险分级（P0-P3，三阶段）
│   ├── domain-collab/           # 跨域协作分析（三轮：独立→协商→综合）
│   ├── requirements-elicitation/# 需求澄清（9 维度系统性提问）
│   ├── writing-plans/           # 风险感知实现规划
│   ├── tdd/                     # 测试先行（风险差异化）
│   ├── impl-orchestration/      # Subagent 驱动 Plan 执行（风险感知 review）
│   ├── systematic-debugging/    # 域知识驱动调试
│   ├── spec-challenge/          # 对抗审查（challenge-response 循环）
│   ├── impl-verify/             # 实现正确性验证（多轮收敛，最多 5 轮）
│   ├── cross-review/            # 跨文件一致性验证（手动可选工具）
│   └── biz-impact-analysis/     # 业务影响分析（5 步结构化）
├── agents/                      # 7 个 Agent 定义
│   ├── biz-impact-analysis.md   # 影响分析 Agent
│   ├── spec-challenge.md        # 对抗审查 Agent
│   ├── domain-analyst.md        # domain-collab R1 独立域分析 Agent
│   ├── domain-negotiator.md     # domain-collab R2 跨域协商 Agent
│   ├── implementer.md           # impl-orchestration 按 Task 实现 Agent
│   ├── spec-reviewer.md         # impl-orchestration 规格审查 Agent
│   └── impl-verifier.md         # impl-verify 并行验证 Agent
├── commands/
│   ├── ecw-init.md              # 项目初始化向导
│   ├── ecw-validate-config.md   # 配置验证命令
│   └── ecw-upgrade.md           # 配置升级命令（版本化迁移）
├── hooks/                       # 6 事件点 Hook 架构
│   ├── hooks.json               # Hook 注册（6 事件：SessionStart/Stop/PreToolUse/PostToolUse/PreCompact/SessionEnd）
│   ├── dispatcher.py            # PreToolUse 统一调度器（5 子模块，Profile 门控）
│   ├── verify-completion.py     # 子模块：完成验证（4 硬拦截 + 1 定向提醒）
│   ├── config-protect.py        # 子模块：配置文件保护
│   ├── compact-suggest.py       # 子模块：主动压缩建议
│   ├── secret-scan.py           # 子模块：敏感数据检测
│   ├── bash-preflight.py        # 子模块：危险命令预检
│   ├── post-edit-check.py       # PostToolUse 反模式检测
│   ├── session-start.py         # SessionStart 上下文注入 + instinct 加载
│   ├── stop-persist.py          # Stop marker-based 状态持久化
│   ├── pre-compact.py           # PreCompact 压缩恢复引导
│   ├── session-end.py           # SessionEnd 会话清理
│   └── marker_utils.py          # 共享幂等标记更新工具库
├── templates/                   # 配置和知识文件模板
│   ├── ecw.yml                  # 项目配置模板
│   ├── domain-registry.md       # 域注册表模板
│   ├── change-risk-classification.md # 风险分级校准模板
│   ├── calibration-log.md       # 校准历史模板
│   ├── ecw-path-mappings.md     # 路径映射模板
│   ├── CLAUDE.md.snippet        # CLAUDE.md 集成片段
│   ├── knowledge/               # 知识文件模板
│   │   ├── common/              # 跨域公共知识（6 个文件）
│   │   └── domain/              # 域级知识（3 个文件）
│   └── rules/                   # 工程规则模板
│       ├── common/              # 通用规则（security, testing, coding-style, performance, design-patterns）
│       ├── java/                # Java 专项规则
│       └── go/                  # Go 专项规则
├── scripts/
│   ├── java/                    # Java/Spring 项目扫描脚本（3 个）
│   └── README.md                # 扫描输出格式规范
├── tests/                       # 三层测试套件
│   ├── Makefile                 # lint / test-hook / eval-* 目标
│   ├── static/                  # Layer 1：Python 静态扫描（14 项）+ pytest Hook 单元测试（301 用例）
│   └── eval/                    # Layer 2：promptfoo 行为 Eval（4 套件：risk-classifier/domain-collab/tdd/impl-verify）
├── CLAUDE.md                    # 插件级指引
├── CHANGELOG.md                 # 版本历史
├── CONTRIBUTING.md              # 开发约定与审查清单
├── TROUBLESHOOTING.md           # 故障排查指南
├── package.json                 # 版本信息
├── ruff.toml                    # Python lint 配置
├── .markdownlint.json           # Markdown lint 配置
├── LICENSE                      # MIT License
├── README.md                    # English documentation
└── README.zh-CN.md
```

## 升级插件

### 更新到最新版本

```bash
claude plugin update ecw@enterprise-change-workflow
```

或在 Claude Code 会话中执行 `/plugin update ecw`，然后重启会话即可使用新增的 skill 和 command。

### 升级项目配置

插件更新后，如果新版本包含配置迁移（如新增 ecw.yml 字段、新增知识文件模板等），在目标项目中执行：

```
/ecw-upgrade
```

该命令会检测项目的 ECW 配置版本与插件版本的差异，列出待执行的迁移，逐步应用变更。

## 故障排查

### 常见问题

**Q: 更新插件后新命令/skill 没有出现？**

A: 确认已执行 `claude plugin update ecw@enterprise-change-workflow` 并重启了 Claude Code 会话。

**Q: `/ecw-init` 执行后，`/ecw-validate-config` 报告大量 warn？**

A: 正常现象。`ecw-init` 生成的是模板文件，需要根据你的项目填充实际内容。按 validate 报告中的优先级逐项完成。

**Q: verify-completion hook 报"断裂引用"？**

A: 你修改的文件中引用了 `.claude/` 下不存在的路径。检查路径拼写是否正确，或者引用的文件是否已被移动/删除。

**Q: Java 编译检查失败阻止了任务完成？**

A: 编译不过就不能标记完成。修复编译错误后重新标记即可。如果 mvn 不在 PATH 中，编译检查会自动跳过。

**Q: Phase 1 判定的风险等级明显不准？**

A: 两个常见原因：(1) `change-risk-classification.md` 中的关键词映射不够全面 — 补充缺失的关键词；(2) `shared-resources.md` 中缺少共享资源条目 — 重新运行扫描脚本或手动补充。Phase 3 的校准建议可以帮助你系统性改进。

**Q: 知识文件为空，影响分析效果差？**

A: 知识文件质量直接决定分析质量。Java/Spring 项目建议先用 `scripts/java/` 下的扫描脚本自动提取，再人工审查补充。其他技术栈需要手动填充。

## 依赖

- **Claude Code CLI** — ECW 是 Claude Code 插件，需要 CLI 环境
- **无外部插件依赖** — ECW 自包含所有 Skill（writing-plans、tdd、systematic-debugging、impl-orchestration 等），无需安装其他插件

## License

[MIT](LICENSE)
