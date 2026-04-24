# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。

## [1.0.0] - 2026-04-24

### 新增



### 修复



### 增强



## [0.9.9] - 2026-04-24

### 新功能

- **知识库维护能力** — 新增 3 个 Skill + 配套脚本 + verify-completion hook 闭环
  - `ecw:knowledge-audit`：知识库健康度审计（内容构成分析 + 三条件合规 + 新鲜度检测），产出 stale-refs 供 hook 消费
  - `ecw:knowledge-track`：文档利用追踪（hit/miss/redundant/misleading/code-derived），积累数据量化知识库 ROI
  - `ecw:knowledge-repomap`：代码结构索引自动生成，从 ecw.yml component_types 驱动
  - `check-freshness.sh`：检测知识库文档中引用的 Java 类名是否存在 + last-verified 超期
  - `generate-repo-map.sh`：自动提取组件类名和方法签名，按目录分组输出
  - `verify-completion` hook 新增 `check_knowledge_maintenance()`：消费 stale-refs / doc-tracker misleading / 组件结构变更三个信号
- **ecw-init 集成** — scanner 步骤后自动生成 doc-tracker 模板 + repo-map
- **ecw-upgrade Check H** — 检测 knowledge_maintenance 配置段
- **biz-impact-analysis 下游提示** — Phase 3 前提示运行 knowledge-track
- **ecw.yml 新增 knowledge_maintenance 配置段** — stale_days、repomap_group_by_dir

## [0.9.8] - 2026-04-22

### 重构

- **ecw-upgrade Check C 改为检测 Java 项目后自动开启 TDD** — 原来通过搜索项目 `CLAUDE.md` 的 TDD 文字判断，现改为检测 `pom.xml` 确认 Java 项目，直接校验 `ecw.yml` 的 `tdd.enabled` 字段，Java 项目默认开启 TDD，非 Java 项目跳过
- **精简为 Java only 支持** — 移除 ecw-init/ecw-validate-config/tdd/writing-plans/ecw.yml 模板中 go/python/node/typescript 相关语言检测表、测试命令和代码示例，当前仅支持 Java 项目

## [0.9.7] - 2026-04-22

### 修复

- **cost-tracker 1M context 误报** — 移除硬编码 `MAX_CONTEXT = 200_000`，从 `ANTHROPIC_MODEL` 环境变量检测 `[1m]` 后缀自动识别 context window 大小（200K / 1M），修复 1M context 模型下压缩建议过早触发的问题
- **config-protect 误拦截 templates/ 和 state/** — `EDITABLE_PATH_PREFIXES` 补充 `templates/` 和 `.claude/ecw/state/` 前缀，工作流过程产出物和模板文件不再被 config-protect 拦截

### 测试

- **TestMaxContext** — 4 项测试覆盖 `_get_max_context()` 的 200K 默认值、Opus 1M、Sonnet 1M、空环境变量场景

## [0.9.6] - 2026-04-21

### 改进

- **Gateguard 白名单模式** — 从黑名单排除法改为白名单模式，通过 ecw.yml `hooks.gateguard_extensions` 配置受保护的扩展名（如 `.java`、`.xml`）；未配置则 gateguard 完全不生效，彻底解决非 ECW 项目被误拦截问题
- **Bash sed -i 绕过防护** — bash-preflight 新增 `sed -i` 绕过检测，当命令修改 gateguard 保护的文件类型时拦截并提示使用 Edit 工具
- **移除环境变量控制** — 删除 `ECW_GATEGUARD_DISABLED` 环境变量，gateguard 行为完全由 ecw.yml 配置控制

## [0.9.5] - 2026-04-20

### 新增

- **hooks.exempt_paths 配置化** — hook 拦截路径白名单从 Python 硬编码迁移到 ecw.yml `hooks.exempt_paths`，支持用户自定义相对路径前缀；config-protect 和 gateguard 均读取此配置

### 修复

- **config-protect relpath 误拦截** — `file_path.startswith(cwd)` 路径规范化不一致时 fallback 为绝对路径，导致 `templates/ecw.yml` 等合法编辑被拦截；改用 `os.path.relpath()` 无条件计算相对路径

### 测试

- **Skill 间数据契约验证** — `data_contracts.yaml` 定义 11 个 Skill 的文件 I/O 契约（writes/reads/条件），`test_data_contracts.py` 7 项交叉验证（路径存在性、上游 writer、session-state 字段超集、路由链依赖覆盖、降级文档）
- **工作流模拟器** — `workflow_traces.yaml` 定义 13 条完整路由轨迹，`test_workflow_simulator.py` 7 项测试交叉验证 routing_matrix × data_contracts × traces（routing 一致性、mode 单调性、checkpoint 写入、依赖满足、ask_user 一致性、路由完备性）
- **lint CHECK 22 data-contracts** — lint_skills.py 新增数据契约交叉验证检查，验证 writes path_pattern 在 SKILL.md 中可找到、reads key 有对应 writer
- **PromptFoo 边界场景 s22-s25** — 4 个新场景：P2 共享资源升级（s22）、歧义域边界（s23）、Bug 含敏感词（s24）、路由顺序验证（s25）
- **Makefile 集成** — 新增 `test-contracts`、`test-simulator` target，纳入 `all` 日常流水线

## [0.9.4] - 2026-04-20

### 新增

- **output_language 产出物本地化** — ecw.yml 新增 `project.output_language` 字段（默认 zh-CN），6 个 SKILL.md + 6 个 agent 模板读取并遵循此配置，artifact-schemas.md 增加全局 Localization 规则
- **ecw-upgrade Check F/G** — 自动迁移 `output_language` 字段和 `hooks` 配置段

## [0.9.3] - 2026-04-20

### 修复

- **Gateguard 新文件放行** — Write 新建文件时 gateguard-fact-force hook 误拦截（要求调查 callers），加 `os.path.exists` 检查跳过不存在的文件
- **impl-orchestration 协调器禁止直接实现** — 协调器在剩余 Task 少时跳过子代理自己写代码，绕过 ecw.yml models 配置和 gateguard hook；Serial Fallback 明确 serial ≠ coordinator-direct，Never Rules + Common Rationalizations 双重防护
- **Spec Review 后必须派发 repair 子代理** — 协调器 Spec Review 发现问题后直接 Edit 修复，同样绕过配置；改为强制派发 repair implementer subagent

### 改进

- **TDD subagent-driven 快速路由** — 当实现策略为 subagent-driven 时，TDD skill 从冗余 pass-through 改为明确的两步快速路由（更新 session-state → 立即 invoke impl-orchestration）

## [0.9.2] - 2026-04-20

### 修复

- **Agent 模板路径解析** — 技能执行时 `agents/*.md` 模板因相对路径按项目 cwd 解析导致读取失败；改用 `subagent_type` 自动注入机制，coordinator 仅在 prompt 中传递动态上下文，消除路径依赖

## [0.9.1] - 2026-04-20

### 新增

- **SessionStart 版本校验** — 启动时比对项目 `ecw.yml` 的 `ecw_version` 与插件 `package.json` 版本，不一致时强制提示执行 `/ecw-upgrade`

### 修复

- **config-protect marker 机制** — ecw-upgrade / ecw-init 执行时自动创建 `.claude/ecw/.config-edit-allowed` 标记文件临时放行配置编辑，完成后自动清理；解决升级命令被自身 hook 拦截的鸡生蛋问题

## [0.9.0] - 2026-04-20

### 架构改进

- **Agent 加固** — 7 个 Agent 模板全部新增 Subagent Boundary 守卫（单任务身份声明 + 禁止 invoke/spawn）、反谄媚指令、源码读取上限声明
- **SKILL.md 标准化** — 11 个 SKILL.md 统一添加 Mode Switch、Announce-at-Start、Common Rationalizations 表格（≤5 条独特反模式）
- **SKILL.md 瘦身** — 从 5 个 SKILL.md 中提取 REFERENCE/TEMPLATE 内容到补充文件，降低主文件行数
- **risk-classifier 优化** — SKILL.md 从 566→486 行，消除冗余（TDD 细节引用 ecw:tdd、Bug 路由引用 Skill Interaction 表、合并 session-state 重复段落）

### 新增

- **Auto-Flow** — 标准化 skill 间过渡机制 + 精确压缩恢复（PreCompact 注入自动继续指令，消除转场确认弹窗）
- **全自动执行链路** — 移除 spec-challenge session 分裂确认，`auto_confirm: true` 时整条链仅剩 spec-challenge 致命缺陷确认一个人工交互点
- **Skill 独立调用** — 7 个 skill 单独调用时默认 P0 完整模式，不再 AskUserQuestion 询问风险等级；requirements-elicitation 解除 risk-classifier 前置依赖
- **产出物 Schema** — `templates/artifact-schemas.md` 统一定义 7 个 ECW 过程产出物的结构、字段、写入方/读取方
- **impl-verify 执行状态检查** — verify-completion hook 检查 `impl-verify-findings.md` 是否存在，未执行时输出精确提醒（替代旧的通用文字提醒）
- **ecw-upgrade auto_flow 迁移** — Check B 显式列出 `auto_flow:` 配置段，已有项目升级自动补上
- **可配置模型路由** — ecw.yml 新增 `models` 配置段，9 个 SKILL.md 模型引用从硬编码改为配置化路由；session-start 注入模型配置
- **工程规则框架** — `templates/rules/` 新增 Agent 引用 + session-start 注入机制
- **Token 成本追踪** — `cost-tracker.py` hook，基于 token 用量的成本追踪和预算告警
- **Fact-Forcing Gate 守卫** — `gateguard-fact-force.py` hook，PreToolUse 阶段检查 implementer 事实溯源合规性
- **设计规范三层体系** — 机器校验（lint）+ Claude 行为规则（rules）+ 参考文档（docs）：
  - `templates/rules/common/ecw-development.md` — ECW 内部开发规则（15 条 must-follow + 5 条 recommended）
  - `docs/design-reference.md` — Token 预算、模型选择、上下文管理、Subagent 规模分类指南
  - `lint_skills.py` 新增 3 项检查（skill-length / agent-structure / hook-fail-open），总计 21 项
  - `test_design_standards.py` 新增 ~15 个 pytest 测试覆盖规范合规

### 测试

- Agent 加固测试（boundary / anti-sycophancy / reading limits）
- Mode-switch / announce-at-start / rationalization 表格测试
- 模型路由、成本追踪、规则框架 RED 测试
- **总计 654 测试用例**（从 488 增至 654）

### 修复

- ecw.yml 并行 worktree 合并后的重复 `rules` 段
- anchor_keywords.yaml impl-orchestration agent 文件名过时引用

### 数据

| 指标 | v0.8.1 | v0.9.0 | 变化 |
|------|--------|--------|------|
| Lint 检查项 | 18 | 21 | +3 |
| 单元测试 | 488 | 654 | +166 |
| Hook 模块 | 10 | 12 | +2 (cost-tracker, gateguard-fact-force) |
| risk-classifier 行数 | 566 | 486 | -14% |

## [0.8.1] - 2026-04-19

### 修复

- **bash-preflight force-push 误拦截** (Finding-01) — `--force-with-lease` 被正则一刀切拦截（自相矛盾建议用它却拦截它），改用负向前瞻排除；tag push 降级为 warning
- **skill 过渡 auto-continue** (Finding-02/04) — 用户选择"Proceed"后下游 skill 过渡仍弹确认，添加 CRITICAL 指令强制 IMMEDIATELY invoke，禁止输出确认文本
- **ecw-init 缺少 Write 权限配置** (Finding-03) — ecw-init 未配置 `.claude/settings.local.json` Write 权限，导致产出物写入触发权限确认弹窗
- **spec-challenge Plan 修订策略** (Finding-05) — Step 4 未指定修订方式，LLM 派 subagent 用 Edit 在 75KB Plan 上逐段替换导致 33 分钟瓶颈；明确 coordinator 直接用 Write 覆写
- **session 切换体验差** (Finding-06) — 翻转推荐为"继续当前 session"，移除吓人措辞，添加 PreCompact hook 保护说明
- **ecw.yml 重复键** (F-12) — 合并两个 `impl_orchestration` 段，消除 YAML 解析歧义
- **session-end.py 路径 bug** (F-1) — `_find_session_state()` 搜索错误路径 `ecw/state/`，改用 `marker_utils.find_session_state()`
- **dispatcher.py get_profile 路径 bug** — `get_profile()` 搜索不存在的 `ecw/state/session-state.md`，导致 risk profile 始终退化为 "standard"，P0 无法获得 "strict" profile
- **compact-suggest 计数器跨 session 不重置** — `tool-call-count.txt` 未被 session-end 清理，新 session 继承旧计数导致过早弹出压缩建议

### 测试

- **test_auto_continue.py** — 4 个测试验证 skill 过渡 auto-continue 机制
- **test_ecw_init_permissions.py** — 2 个测试验证 ecw-init Write 权限配置
- **test_spec_challenge.py 新增 6 个测试** — Plan 修订策略 (3) + session 推荐翻转 (3)
- **test_bash_preflight.py 新增 6 个测试** — force-with-lease 放行 + tag push 降级

### 改进

- **Hook 共享模块** (DC-1/PC-6) — 新增 `ecw_config.py`，5 个 Hook 消除 `_find_session_state` / `_read_ecw_config` 重复定义，统一使用 `marker_utils` + `ecw_config`
- **lint_skills.py 新增 3 项检查** — CHECK 15 (共享模块强制)、CHECK 16 (subagent 安全四要素)、CHECK 17 (eval 覆盖报告)

### 新增

- **test_hook_exception_safety.py** (DC-4) — AST 检查所有 Hook `__main__` 必须有 try/except + 禁止 sys.exit(1)
- **test_yaml_template_validity.py** (PC-4) — YAML 模板无重复键检查
- **test_workflow_guard.py** (DC-2) — verify-completion 工作流完整性检查占位
- **test_artifact_schema.py** (DC-5) — artifact-schemas.md schema 覆盖占位

## [0.8.0] - 2026-04-18

### 新增

- **impl-orchestration 并行执行** — 依赖图分析 + worktree 隔离并行调度 implementer subagent。串行 N 个 Task 压缩为 L 层并行（WMS 案例: 13 Task 串行 93min → 理论 5 层 ~25min）。含文件级冲突检测、最大并行度控制（默认 3）、合并冲突处理、串行 fallback
- **ecw.yml `impl_orchestration` 配置段** — 新增 parallel/max_parallelism/pre_check/merge_compile_check 四项配置，ecw-upgrade 自动补充
- **ecw-monitor 告警扫描** — assistant text content 关键词扫描（超时/timeout/fallback/失控/error/失败/degraded/异常），命中时输出 Alerts section

### 改进

- **calibration 双文件分工明确化** — `calibration-log.md`（完整维度对比，人工 review 用）与 `calibration-history.md`（简洁索引，Phase 1 自动检索用）。risk-classifier SKILL.md、CLAUDE.md、模板均补充分工说明

## [0.7.0] - 2026-04-18

### 修复

- **impl-orchestration → impl-verify 自动路由** (Issue-6) — 完成所有 Task 后直接执行 impl-verify，不再询问用户确认
- **impl-verify findings 持久化** (Issue-7) — 每轮验证后将 findings 写入 `session-data/{workflow-id}/impl-verify-findings.md`
- **Subagent Ledger 完整记录** (Issue-8) — impl-orchestration 每批 Task 完成后更新 session-state Ledger
- **spec-challenge-report.md 独立生成** (Artifact-1) — findings 在回写 Plan 前先独立持久化到 session-data/
- **writing-plans/spec-challenge 分裂建议不冲突** — P0/P1 后续有 spec-challenge 时，writing-plans 不提前触发 compact 建议，由 spec-challenge 完成后统一走 new session 分裂点
- **verify-completion 知识文档白名单** (Issue-5) — `.claude/knowledge/`、`session-data/`、`plans/` 路径跳过编译/测试验证
- **Plan subagent 动态超时** (Issue-2) — 根据预估 Task 数设置超时（≤5: 180s, 6-10: 300s, >10: 420s），超时后跳过重试直接 fallback Direct
- **PreCompact auto-continue 前置** (Issue-1) — auto-continue 指令移至 systemMessage 最前，提高 compact 后自动恢复可靠性
- **知识库跨域调用自动回填** (Warning-3) — biz-impact-analysis 发现未注册跨域调用时自动追加到 cross-domain-calls.md

### 新增

- **impl-orchestration 首 Task 前预检** (Warning-1) — 执行前运行 compile+test 预检，提前暴露基础设施问题。可通过 ecw.yml `impl_orchestration.pre_check` 关闭

## [0.6.6] - 2026-04-17

### 修复

- **subagent timeout prevention** — spec-challenge 增加 10 文件读取上限防止 2400s 超时；writing-plans/spec-challenge 超时后先重试 subagent 再降级 Direct 模式
- **implementer runaway prevention** — Fact-Forcing Gate 改为仅分析主域引用（跨域仅计数），100 tool call 硬停，自审改为单次
- **P0 downstream auto-routing** — writing-plans 完成后自动进入 spec-challenge，不再 AskUserQuestion
- **verify-completion runtime paths** — 跳过 `state/` 和 `session-data/` 目录的 broken reference 检查

### 改进

- **context compression UX** — pre-compact hook 注入自动继续指令；stop-persist hook 检测阶段转换写入 context-health advisory
- **session-data 路径隔离** — session-state.md、knowledge-summary.md、domain-collab-report.md、spec-challenge-report.md 迁移至 `session-data/{workflow-id}/`，防止多需求并行时互相覆盖。更新 11 个 SKILL.md + 3 个 hook + agent + 文档

## [0.6.5] - 2026-04-17

### 移除

- **rules 系统** — `.claude/ecw/rules/` 路径下的规则文件不会被 Claude Code 自动加载（仅 `.claude/rules/*.mdc` 生效），整个 rules 安装机制是无效的。移除 `templates/rules/` 模板目录、ecw-init 的规则安装步骤、ecw-upgrade 的 rules 跳过引用、CLAUDE.md 的 rules 表行

## [0.6.4] - 2026-04-17

### 改进

- **ecw-upgrade 重写为纯幂等模式** — 去除版本目录遍历，改为 7 项独立幂等检查（A-G）。新增 CLAUDE.md ECW 入口注入、ecw.yml 结构同步、术语更新、域路由检查。升级完成后自动执行 `/ecw-validate-config`

### 修复

- **risk-classifier 自动触发** — skill description 改用 BLOCKING 前置 + folded 格式确保可见；CLAUDE.md 触发指令强化为 BLOCKING RULE。配合 ecw-upgrade Check A 注入项目级触发指令，三层保障自动触发

## [0.6.3] - 2026-04-17

### 修复

- **risk-classifier description 被截断** — skills list 对 `|` 多行格式只显示第一行，导致 BLOCKING 指令不可见。改用 `>` 折叠格式，BLOCKING 置于首位，控制在 170 字符内确保完整显示

### 改进

- **ecw-upgrade 重写为纯幂等模式** — 去除版本目录遍历（`templates/upgrades/{version}/migration.md`），改为 7 项独立幂等检查（A-G），可重复执行。新增 Check A（CLAUDE.md ECW 入口注入）、Check C（ecw.yml 结构同步 — 补缺失字段/删废弃字段）、Check F（术语更新）、Check G（域路由表检查）。升级完成后自动执行 `/ecw-validate-config`

## [0.6.2] - 2026-04-17

### 修复

- **risk-classifier 自动触发失败** — skill description 使用排序建议语气（"Use BEFORE"）而非触发条件格式，导致模型遇到项目 CLAUDE.md 的"先读文档"等指令时优先执行后者，跳过 ECW 入口。改为 TRIGGER when / BLOCKING / DO NOT TRIGGER 三段式，与 biz-impact-analysis、spec-challenge 等已生效 skill 格式一致
- **CLAUDE.md 触发优先级强化** — Dependencies 段的 "Skill check priority" 改为 "BLOCKING RULE"，明确 "before reading code, before reading documentation, before any analysis"

## [0.6.1] - 2026-04-17

### 优化

- **高判断力 Agent 升级 Opus** — 按认知需求和错误代价差异化分配模型，5 个关键 Agent/Subagent 从 sonnet 升级为 opus：
  - `spec-challenge`：对抗性审查需要最强推理找方案盲区
  - `biz-impact-analysis`：最终安全网，遗漏影响面直接导致生产事故
  - `domain-analyst`：域级分析需要深度理解业务规则和状态机
  - `domain-negotiator`：跨域冲突检测和 companion change 推理
  - `writing-plans` subagent：Plan 质量驱动全部下游实现
- **保持 sonnet 的组件** — impl-verifier（规则对照）、spec-reviewer（规格匹配）、risk-classifier Phase 2（结构化查询）、tdd cycles（测试编写）
- **保持三级分层的组件** — implementer（haiku/sonnet/opus 按 Task 复杂度自动选择）

### 修复

- **package.json 版本同步** — 从 0.4.2 补齐到 0.6.1（v0.6.0 时遗漏）

## [0.6.0] - 2026-04-17

### 架构升级 — ECC 对标全面改进

基于 [everything-claude-code](https://github.com/affaan-m/everything-claude-code) 最佳实践，对 ECW 插件进行 4 波次 9 类 34 项系统性改进。

#### Wave 1 — 基座层

- **Hook 调度器模式 (B-1~B-3)** — `hooks/dispatcher.py` 统一 PreToolUse 入口，子模块通过注册表串联；风险等级 Profile 门控（P0→strict, P1/P2→standard, P3→minimal）；`post-edit-check.py` PostToolUse 反模式检测
- **工程规则层 (F-1~F-2)** — `templates/rules/common/` 5 个通用规则文件（coding-style/security/testing/performance/design-patterns）；Java/Go 语言专项规则
- **代码质量工具链 (I-1, I-3)** — markdownlint + ruff 集成；CONTRIBUTING.md + TROUBLESHOOTING.md

#### Wave 2 — 核心层

- **Session 生命周期 (A-1~A-4)** — SessionStart 自动注入 session-state/checkpoint/ecw.yml 上下文；Stop hook marker-based 状态持久化；PreCompact 压缩恢复引导增强；SessionEnd 清理
- **Agent 架构 (G-1~G-4)** — 全部 SKILL.md subagent dispatch 指定 model（haiku/sonnet/opus）；7 个 agent 文件独立化提取（implementer/spec-reviewer/impl-verifier/domain-analyst/domain-negotiator/biz-impact-analysis/spec-challenge）；impl-orchestration 最大迭代 + 熔断；subagent 返回值 schema 检查 + 重试 + 降级
- **配置文件保护 (C-1)** — config-protect 子模块阻止 AI 修改 ecw.yml/domain-registry 等关键配置

#### Wave 3 — 深化层

- **Skill 内部质量 (H-1~H-6)** — 11 个 SKILL.md 统一错误处理（失败→Ledger记录→重试→降级）；全部 subagent dispatch 增加 timeout；交互循环终止条件（最大轮次 + 无改善升级）；systematic-debugging/tdd/requirements-elicitation/domain-collab 增加 session-data 检查点；知识文件存在性检查 + 降级标注；impl-verify Diff Read Strategy 矛盾修复
- **Context 管理 (E-1~E-3)** — `compact-suggest.py` tool-call 计数器主动压缩建议；`marker_utils.py` 共享幂等更新模块；session-state 工作模式声明（analysis/planning/implementation/verification）
- **安全加固 (C-2~C-5)** — `secret-scan.py` 敏感数据检测（AWS/JWT/GitHub Token/Private Key/Generic Secret）；`bash-preflight.py` 危险命令预检（--no-verify/push --force/rm -rf）；Fact-Forcing Gate 实现者事实溯源门控；Subagent Ledger 增加 Started/Duration 列治理审计

#### Wave 4 — 增值层

- **持续学习 (D-1~D-3)** — Phase 3 校准历史持久化（calibration-history.md）；Instinct 注入框架（confidence > 0.7 由 SessionStart 注入）；session-data 按 workflow-id 隔离
- **测试覆盖扩展 (I-2)** — domain-collab（6 场景）、tdd（7 场景）、impl-verify（6 场景）promptfoo eval 套件
- **语言硬编码清理 (H-7)** — verify-completion/post-edit-check/bash-preflight/secret-scan 中文提示语提取为 `_MESSAGES` 字典

### 数据

| 指标 | v0.5.0 | v0.6.0 | 变化 |
|------|--------|--------|------|
| Hook 模块 | 3 | 10 | +7 |
| Agent 文件 | 2 | 7 | +5 |
| SKILL.md 总 token | ~43K | ~44.5K | +3.5% |
| 单元测试 | 204 | 301 | +97 |
| Eval 套件 | 1 (risk-classifier) | 4 (+domain-collab/tdd/impl-verify) | +3 |
| Lint warnings | 3 | 0 | -3 |

## [0.5.0] - 2026-04-17

### 性能优化

- **上下文压缩问题系统性治理** — 基于 WMS 项目 P0 跨 4 域实际 session 数据（6 次压缩、169 次文件读取），定位 5 大上下文消耗瓶颈并逐一优化。理论上 6/6 次压缩均可避免

#### Issue #1: 实现策略多维度化 (Critical)

- **risk-classifier 策略表升级** — Implementation Strategy Selection 从单维度（Task 数量，6 行）改为三维度决策矩阵（Task 数 × 文件数 × 域数，9 行），新增 `涉及文件 ≥ 6` 和 `≥ 2 域代码修改` 两个 impl-orchestration 触发条件
- **TDD Subagent Delegation** — tdd SKILL.md 新增 "Subagent Delegation for Heavy TDD" 段落：strategy=subagent-driven 时 TDD 在 impl-orchestration subagent 中执行；strategy=direct 但文件 ≥ 6 时每个 RED-GREEN cycle 封装为独立 subagent

#### Issue #2: impl-verify 并行 Subagent 化 (High)

- **4 轮并行 subagent 派发** — impl-verify 的 Round 1-4 验证从 coordinator 顺序执行改为 4 个并行 subagent（model: sonnet），每轮返回结构化 YAML findings，coordinator 只持有变更文件列表和合并后的 findings
- **增量收敛循环** — must-fix 修复后只重新 dispatch 有 must-fix 的轮次的 subagent（增量 diff），不重跑全部 4 轮

#### Issue #3: writing-plans Subagent 化 (High)

- **Subagent Dispatch Architecture** — writing-plans 新增 subagent 派发架构：触发条件（≥ 2 域或 ≥ 3 知识文件）时 coordinator 只传文件路径，subagent 在自己的上下文中读取知识文件、生成 Plan、直接 Write 文件，返回 ≤ 500 tokens 摘要（model: sonnet）
- **domain-collab 下游读取声明强化** — 明确下游 skill 必须从 `domain-collab-report.md` 和 `knowledge-summary.md` 文件读取，不依赖对话历史中的 agent 中间结果

#### Issue #4: Phase 2 Subagent 化 (Medium)

- **Phase 2 依赖图查询下沉** — risk-classifier Phase 2 的 5 类知识文件查询（cross-domain-calls、mq-topology、shared-resources、external-systems、e2e-paths）从 coordinator inline 执行改为 subagent 派发（model: sonnet），Steps 1-4 标记 `[Subagent]`，Step 5（升降级决策）保留 coordinator
- **knowledge-summary 优先使用** — Phase 2 subagent 在 knowledge-summary.md 存在时优先读取，减少原始知识文件重复读取

#### Issue #5: 主动压缩策略 (Medium)

- **PreCompact hook** — 新增 `hooks/pre-compact.py`，在上下文压缩前注入 systemMessage 引导 Claude 从 session-state.md 恢复工作流状态
- **session-data checkpoints** — 新增 `.claude/ecw/session-data/` 目录，3 个 checkpoint 文件确保压缩后下游 skill 可冷启动：
  - `requirements-summary.md`（requirements-elicitation 完成后写入）
  - `phase2-assessment.md`（Phase 2 完成后写入）
  - `impl-verify-findings.md`（每次 impl-verify 后始终写入，移除 >5 条阈值）
- **阶段边界 compact 建议** — domain-collab Round 3 和 writing-plans 完成后建议用户 `/compact`

### 新增

- **7 个上下文压缩测试文件**（58 个测试函数）
  - `test_strategy_selection.py` — 11 tests，验证三维度策略表完整性和回归
  - `test_impl_verify_subagent.py` — 10 tests，验证 4 轮并行 subagent 架构
  - `test_writing_plans_subagent.py` — 10 tests，验证 writing-plans subagent 派发 + domain-collab 下游声明
  - `test_phase2_subagent.py` — 10 tests，验证 Phase 2 subagent 标记和结构
  - `test_pre_compact.py` — 6 tests，验证 PreCompact hook 行为
  - `test_session_data_checkpoints.py` — 6 tests，验证 3 个 checkpoint 文件的写入声明
  - `test_hooks_json.py` — 5 tests，验证 hooks.json 注册完整性
- **4 个 eval 场景**（tdd 路由覆盖 0 → 4）
  - `s18-p0-4domain-dense.yaml` — WMS-like P0 4 域密集场景，复现分析报告原始场景
  - `s19-p1-cross-domain-tdd.yaml` — P1 跨域含 tdd 路由验证
  - `s20-p2-requirement-tdd.yaml` — P2 单域含 tdd 但排除 spec-challenge/biz-impact-analysis
  - `s21-bug-excludes-tdd.yaml` — Bug 排除 tdd 反面验证
- **promptfooconfig.yaml tdd 路由规则** — 系统 prompt 新增 4 条 tdd 路由约束（P0-P2 requirement MUST include tdd；P3/bug/fast-track 不包含 tdd）

> 与 v0.3.0-v0.3.1 合计效果（INPUT 优化 + OUTPUT 优化 + subagent 架构 + 压缩策略）：P0 跨域工作流理论上可从 6 次压缩降至 0 次。需在实际项目验证。

## [0.4.2] - 2026-04-16

### 新增

- **三层提示词验证体系** — 完整的测试套件，覆盖 11 个 SKILL.md 的结构完整性和 risk-classifier 的路由决策正确性
  - **Layer 1**：Python 静态扫描（14 项检查，<3s，$0）— frontmatter、互引完整性、产出物路径、路由 DAG、锚点关键词、session-state 合约、路由矩阵验证等
  - **Layer 1b**：pytest Hook 单元测试（56 用例，<10s，$0）— 覆盖 `verify-completion.py` 全部公开函数
  - **Layer 2**：promptfoo + Claude API 行为 Eval（17 场景，~5s，~$0.20）— tool_use 结构化输出，验证 risk-classifier 路由决策，覆盖 routing_matrix 全部 13 条链路
- **routing_matrix.yaml** — 13 条路由 golden fixture，覆盖 {P0-P3} × {单域/跨域} × {需求/Bug/紧急} 全组合，区分高危 Bug（P0/P1 含 biz-impact-analysis）和低危 Bug（P2/P3 排除 biz-impact-analysis）
- **s16-p2-bug / s17-p3-bug** — 补全 P2/P3 Bug 路由场景，验证低危 Bug 排除 biz-impact-analysis 的规则
- **classify_result tool schema** — 带 routing enum 约束的结构化输出工具定义，将 LLM 路由名限定为 9 个有效 ECW skill 名
- **anchor_keywords.yaml** — 11 个 skill 的锚点关键词 fixture
- **Makefile** — `make lint` / `make test-hook` / `make eval-quick` / `make eval-full` / `make all` / `make clean`
- **tests/README.md** — 设计思路 + 维护手册，含 6 个维护场景的操作指南和 CI 集成示例

### 修复

- **README.md lint 命令 python → python3** — macOS 无 `python` 命令，统一为 `python3`

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

[0.9.1]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.9.1
[0.9.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.9.0
[0.8.1]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.8.1
[0.8.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.8.0
[0.7.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.7.0
[0.6.6]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.6.6
[0.6.5]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.6.5
[0.6.4]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.6.4
[0.6.3]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.6.3
[0.6.2]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.6.2
[0.6.1]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.6.1
[0.6.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.6.0
[0.5.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.5.0
[0.4.2]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.4.2
[0.4.1]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.4.1
[0.4.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.4.0
[0.3.2]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.3.2
[0.3.1]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.3.1
[0.3.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.3.0
[0.2.2]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.2.2
[0.2.1]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.2.1
[0.2.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.2.0
[0.1.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.1.0
[1.0.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v1.0.0
