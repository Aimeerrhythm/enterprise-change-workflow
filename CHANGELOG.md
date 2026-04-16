# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。

## [0.4.1] - 2026-04-16

### 性能优化

- **Skill/Agent/Command 提示词中英文转换** — 14 个提示词文件从中文转为英文，总 token 从 52,859 降至 38,641（-26.9%）。P0 跨域工作流每次会话节省约 8,500-10,600 tokens（200K 上下文窗口释放约 7.1%），延迟上下文压缩触发
  - 已转换文件：risk-classifier、impl-verify、domain-collab、requirements-elicitation、ecw-init、biz-impact-analysis (agent+skill)、spec-challenge (agent+skill)、ecw-validate-config、ecw-upgrade、cross-review、implementer-prompt、CLAUDE.md
  - 3 轮子 Agent 语义校验：语义保真度 → 结构完整性 → 术语一致性，零残留中文、零含义漂移

## [0.4.0] - 2026-04-15

### Breaking Change

- **移除 superpowers 依赖** — ECW 现在完全自包含，无需安装 superpowers 插件。所有 `superpowers:*` 引用替换为 `ecw:*` 自有 Skill
- **移除 `ecw_version` 字段** — ecw.yml 不再需要 `ecw_version` 字段。`/ecw-upgrade` 改为纯幂等迁移：扫描所有迁移步骤并通过幂等检查判断是否已应用，无需版本号追踪。插件更新后无需手动同步版本号

### 新增

- **`ecw:writing-plans`** — 替代 `superpowers:writing-plans`。风险感知 Plan 编写（P0/P1 完整步骤、P2 可合并简单 Task），域上下文注入（ecw-path-mappings + business-rules.md），下游自动衔接（spec-challenge / tdd / impl-orchestration）
- **`ecw:tdd`** — 替代 `superpowers:test-driven-development`。按 P0-P3 差异化强制程度（P0 含验证日志、P1 完整循环、P2 简化、P3 推荐不强制），ecw.yml `tdd.enabled` 联动，Skip 确认协议
- **`ecw:systematic-debugging`** — 替代 `superpowers:systematic-debugging`。域知识驱动根因定位：P0/P1 完整跨域追踪（§1 cross-domain-calls、§2 mq-topology、§3 shared-resources），P2/P3 简化仅查 §3
- **`ecw:impl-orchestration`** — 替代 `superpowers:subagent-driven-development`。风险感知 review 深度（P0 双重 review、P1 仅 spec review），移除 final code reviewer（由 ecw:impl-verify 替代），Subagent Ledger 追踪
- **`templates/upgrades/0.4.0/migration.md`** — 现有用户升级迁移指南

### 移除

- superpowers 插件依赖声明
- 所有 `superpowers:writing-plans`、`superpowers:test-driven-development`、`superpowers:systematic-debugging`、`superpowers:subagent-driven-development` 引用

### 修复

- **P2 跨域路由矛盾** — P2 跨域路由包含 Phase 2，但 Phase 2 规则明确排除 P2。移除 P2 路由中的 Phase 2 步骤
- **Phase 2 章节名语言不匹配** — Phase 2 引用英文章节名 "Data Changes"/"Process Flow"，但 requirements-elicitation 输出中文 "数据变更"/"流程"
- **domain-collab 无条件要求 Phase 2** — 新增 P2 豁免分支，P2 跳过 Phase 2 直接进入 ecw:writing-plans
- **tdd Enforcement 表缺 Bug/Emergency 行** — 补充 Bug（强制复现测试）和 Emergency（跳过）行
- **writing-plans 未更新 session-state.md 实现策略** — Plan 完成后根据 Task 数量确定策略并写入 session-state.md
- **impl-orchestration 缺 P2 排除声明** — "Don't use when" 新增 P2
- **impl-orchestration 缺 session-state 退化处理** — 新增 AskUserQuestion 兜底
- **implementer-prompt 缺跨域知识路径** — 新增 Cross-Domain Knowledge 和 Test Base Class 字段
- **spec-challenge 流程图 `writing-plans` 缺 `ecw:` 前缀** — 统一为 `ecw:writing-plans`
- **plugin.json description 过时** — 从 6 项能力扩展为 11 项
- **紧急通道未显式声明跳过 TDD** — 紧急通道输出和核心要点中增加 TDD 跳过说明
- **Phase 3 触发机制不明确** — 明确由路由任务创建的 Phase 3 Task 驱动执行
- **tdd graphviz 歧义边** — 分离 verify_green 和 verify_refactor 两个校验节点
- **Skill 名引用一致性** — 全部 bare `writing-plans` 引用统一为 `ecw:writing-plans`
- **README.zh-CN.md 缺版本 badge** — 补充 License 和 Version badge

## [0.3.2] - 2026-04-15

### 新增

- **实现策略路由** — risk-classifier 新增「实现策略选择」章节，根据 Plan Task 数量 × 风险等级自动选择直接实现或 `subagent-driven-development`，减少不必要的 subagent 调度开销
- **Post-impl 自动衔接** — Phase 1 用户确认后通过 TaskCreate + blockedBy 创建 impl-verify → biz-impact-analysis → Phase 3 的 pending Task 链，确保实现后流程不遗漏
- **Subagent Ledger** — session-state.md 新增 Subagent Ledger 表，各 skill 的 Coordinator 在 Agent 调度完成后追加记录，支持 subagent 消耗可观测性
- **impl-verify 输出约束** — ≤5 must-fix 直接输出 / >5 写文件仅输出摘要 / 零 must-fix ≤3 行 / 复验轮增量输出，减少 token 消耗和上下文压缩风险

### 修复

- **superpowers 冲突** — 移除与 `superpowers:subagent-driven-development` "Never skip reviews" 规则冲突的"跳过 per-task review"指令，改为"两者互补不替代"
- **impl-verify 下一步路由** — 明确从 session-state.md 读取风险等级；新增退化处理：文件不存在时用 AskUserQuestion 询问用户
- **biz-impact-analysis Agent 职责边界** — Agent Step 1 标题和知识加载规则明确 Coordinator 负责域定位，Agent 接收预处理结果
- **spec-challenge 策略提示** — 区分 4-8 和 >8 Task，>8 时提醒合并简单 Task；恢复 P2 分支判断，与 risk-classifier 路由表完全对齐
- **session-state 时序** — 移除 `{task_id}` 占位符（Phase 1 写入时 Task 尚未创建）；`实现策略` 默认值改为 TBD
- **Bug 修复 Task 创建** — 明确 Bug 修复路由的 Task 创建规则（所有等级创建 impl-verify；P0/P1 额外创建 biz-impact-analysis → Phase 3）
- **新 session 恢复** — 明确 TaskCreate 不跨 session 持久化，新 session 需从 session-state.md `实现后任务` 字段重建 Tasks
- **`--phase3` 手动触发** — risk-classifier 手动触发表新增 `--phase3` 选项

### 增强

- **合并简单 Task 规则** — 补充具体判定启发式：单文件 + 无条件分支 = 可合并；状态机/跨域/多文件联动 = 必须独立
- **实现策略单一源** — risk-classifier 为实现策略的权威定义源，spec-challenge 和 CLAUDE.md 引用而非重复定义

## [0.3.1] - 2026-04-15

### 性能优化

- **domain-collab OUTPUT 约束** — R1/R2 YAML 长度上限（30/20 行），none-impact 域仅输出 3 个字段；R3 完整报告写入 `.claude/plans/domain-collab-report.md`，会话内仅保留 30 行摘要
- **risk-classifier 状态持久化** — Phase 1 输出后写入 `.claude/ecw/session-state.md`，支持跨 session 恢复和压缩韧性
- **session 分割建议** — Phase 1 对 P0 跨域给出轻量提示；spec-challenge 完成后通过 AskUserQuestion 推荐新 session 执行实现
- **CLAUDE.md 产出物清单** — 新增 ECW 产出物文件表，明确各文件写入时机和用途

> 与 v0.3.0 合计效果：分析阶段上下文 83.5% → 53.5%，0 次压缩；结合 session 分割，全流程压缩次数 6 → 2-3

## [0.3.0] - 2026-04-15

### 性能优化

- **domain-collab INPUT 优化** — R1 知识按需加载，R2 输入压缩 + skip 规则（无影响域跳过 R2）
- **biz-impact-analysis 优化** — Coordinator 预处理替代全量 diff 嵌入，条件化知识加载
- **impl-verify 优化** — diff-once 策略（读一次 diff 全轮复用）+ 章节级知识范围限定
- **spec-challenge 优化** — 文件路径引用替代内容嵌入，域级知识范围限定
- **跨 skill 知识复用** — `knowledge-summary.md` 由 domain-collab 生成，risk-classifier/impl-verify 复用

> 预估 ECW 阶段 token 消耗降低 40%，压缩次数 6 → 2-3

## [0.2.2] - 2026-04-14

### 修复

- **Agent/Skill 命名统一** — Agent 文件名与 Skill 名不一致（`spec-challenger` vs `spec-challenge`、`biz-impact-analyzer` vs `biz-impact-analysis`），导致 AI 混淆名字调用 Skill 工具失败后降级直调 Agent，跳过 Skill 编排逻辑。统一 Agent 名 = Skill 名，消除歧义

### 新增

- **`release.sh` 发布脚本** — 统一版本号更新 + git tag + push 流程

## [0.2.1] - 2026-04-14

### 修复

- **`spec-challenge` 用户决策权缺失** — spec-challenger 报告返回后 AI 直接自行回应所有致命缺陷，用户无参与机会。改为：展示报告原文 → 逐条 AskUserQuestion 让用户选择处理方式 → AI 按用户决策执行 → 用户最终确认通过
- **marketplace source 外部化** — marketplace source 改为外部 URL 引用，支持标准 plugin update 流程

## [0.2.0] - 2026-04-14

### 新增

- **TDD 流程集成** — 在 ECW 工作流中嵌入测试先行（TDD）阶段
  - `risk-classifier` 路由表在实现步骤前插入 TDD:RED（P0-P2 强制，P3 推荐，紧急通道跳过）
  - Bug 修复路由嵌入复现测试步骤（TDD:RED → 修复 GREEN）
- **`/ecw-upgrade` 升级命令** — 版本化项目配置升级，支持版本检测、迁移列表、逐步执行、幂等保护
- **版本化迁移模板体系** — `templates/upgrades/{version}/` 目录结构，每个版本包含 migration.md + snippet 模板
- **ecw.yml `tdd` 配置节** — 控制 TDD 流程行为（enabled / check_test_files / base_test_class）
- **ecw.yml `ecw_version` 字段** — ~~跟踪项目 ECW 配置版本~~ 已在 v0.4.0 移除，改为纯幂等迁移

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

[0.4.1]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.4.1
[0.4.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.4.0
[0.3.2]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.3.2
[0.3.1]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.3.1
[0.3.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.3.0
[0.2.2]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.2.2
[0.2.1]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.2.1
[0.2.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.2.0
[0.1.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.1.0
