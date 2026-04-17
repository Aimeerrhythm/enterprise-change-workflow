# ECW 改进问题全清单

> 基于 [everything-claude-code](https://github.com/affaan-m/everything-claude-code/tree/main) (ECC) 优秀实践的对比分析
> 生成日期: 2026-04-17
> 建议按类别拆分到独立 session 中逐一优化

---

## 类别 A：Session 生命周期管理

**目标**: 解决冷启动、进度丢失、会话恢复三大核心体验问题

### A-1. SessionStart hook — 自动注入工作流上下文 (P0)

**问题**: ECW 每次新会话完全冷启动，需要手动读取 `session-state.md`、`session-data/` 下的检查点文件。ECC 在 SessionStart 自动注入上下文，实现"热启动"。

**当前状态**: 无 SessionStart hook

**ECC 参考**:
- [`scripts/hooks/session-start.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/session-start.js) — 会话匹配(worktree/project/recent)、instinct 注入、项目检测
- [`hooks/memory-persistence/session-start.js`](https://github.com/affaan-m/everything-claude-code/tree/main/hooks/memory-persistence) — 记忆持久化恢复

**应做的事**:
1. 新建 `hooks/session-start.py`，注册为 `SessionStart` hook
2. 自动检测 `.claude/ecw/state/session-state.md` 是否存在，存在则注入为 `additionalContext`
3. 检测 `.claude/ecw/session-data/` 下最新检查点文件，注入摘要
4. 注入当前 `ecw.yml` 的项目名、语言、风险等级等关键配置
5. 注入 TaskList 恢复提示（如果存在未完成任务）

---

### A-2. Stop hook — 会话结束时自动持久化状态 (P0)

**问题**: ECW 的 `session-state.md` 依赖 Skill 内部手动写入。如果会话异常中断、用户直接退出、或 context 压缩后遗忘写入，进度丢失。ECC 在每次响应结束后自动持久化。

**当前状态**: 无 Stop hook

**ECC 参考**:
- [`scripts/hooks/session-end.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/session-end.js) — JSONL transcript 解析、marker-based 幂等更新、header merge
- [`the-longform-guide.md`](https://github.com/affaan-m/everything-claude-code/blob/main/the-longform-guide.md) — "Using a Stop hook rather than UserPromptSubmit prevents latency during sessions"

**应做的事**:
1. 新建 `hooks/stop-persist.py`，注册为 `Stop` hook
2. 从 stdin 解析当前会话信息（tools used、files modified）
3. 使用 `<!-- ECW:STATE:START -->` / `<!-- ECW:STATE:END -->` marker 做幂等更新
4. 更新 session-state.md 的"Last Updated"时间戳和活动摘要
5. 保证异常不阻塞正常工作流（`sys.exit(0)` on error）

---

### A-3. Pre-compact hook 增强 — 标记压缩边界 + 检查点提醒 (P1)

**问题**: 当前 `pre-compact.py` 仅注入一条恢复提示。ECC 的做法更完善：在 session 文件中标注压缩时间点，帮助后续上下文理解"什么时候丢失了什么"。

**当前状态**: `hooks/pre-compact.py` 仅输出 systemMessage 提示

**ECC 参考**:
- [`scripts/hooks/pre-compact.js`](https://github.com/affaan-m/everything-claude-code/blob/main/hooks/strategic-compact) — 在 session 文件中追加 `[Compaction occurred at HH:MM]` marker
- [`scripts/hooks/suggest-compact.js`](https://github.com/affaan-m/everything-claude-code/blob/main/hooks/strategic-compact/compact-suggest.js) — 基于 tool-call 计数器的主动压缩建议

**应做的事**:
1. 在 `session-state.md` 中追加压缩时间戳标记（不是覆盖）
2. 注入更精确的恢复指令：列出哪些 `session-data/` 文件需要重读
3. (可选) 新增 PreToolUse 计数器，在工具调用达到阈值时建议压缩

---

### A-4. SessionEnd hook — 会话退出清理 (P2)

**问题**: 无会话退出时的清理机制。多个并行会话可能留下孤立的 worktree 或过期的 session-state 文件。

**当前状态**: 无 SessionEnd hook

**ECC 参考**:
- [`scripts/hooks/session-end-marker.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/session-end-marker.js) — lease-based observer 清理，最后一个 session 退出时停止 observer

**应做的事**:
1. 新建 `hooks/session-end.py`，注册为 `SessionEnd` hook
2. 清理 `.claude/worktrees/` 中与当前 session 关联的过期 worktree
3. 标记 session-state.md 为"已结束"状态

---

## 类别 B：Hooks 基础设施升级

**目标**: 从 2 个 hook 扩展到完善的 hook 体系，同时保持性能和可维护性

### B-1. Hook 调度器模式 — 多路复用替代单独注册 (P1)

**问题**: 当前 `hooks.json` 为每个 hook 单独注册，每次触发都 spawn 一个 Python 进程。ECC 使用 multiplexed dispatcher，将多个子 hook 合并为一次调用。

**当前状态**: 2 个独立 hook（PreToolUse + PreCompact）

**ECC 参考**:
- [`scripts/hooks/bash-hook-dispatcher.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/bash-hook-dispatcher.js) — 单个 dispatcher 串联 6+ pre-hooks 和 4+ post-hooks
- [`scripts/hooks/run-with-flags.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/run-with-flags.js) — 在进程内直接 `require()` 而非 spawnSync，节省 50-100ms/次

**应做的事**:
1. 创建 `hooks/dispatcher.py` 作为统一入口
2. 将 `verify-completion.py` 的各检查项拆分为可独立启用的子模块
3. 新增的 hook（如安全检查、配置保护）注册为子模块而非独立 hook
4. 在 `hooks.json` 中注册 dispatcher 而非各子 hook

---

### B-2. 风险等级驱动的 Hook Profile (P1)

**问题**: 所有检查对所有风险等级一视同仁。P3 微小改动经过与 P0 相同的完成验证，浪费时间。

**当前状态**: `verify-completion.py` 无风险等级感知

**ECC 参考**:
- [`scripts/lib/hook-flags.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/lib/hook-flags.js) — `minimal | standard | strict` 三级 profile，每个子 hook 声明适用 profile
- [`hooks/hooks.json`](https://github.com/affaan-m/everything-claude-code/blob/main/hooks/hooks.json) — profile 参数传递给 run-with-flags

**应做的事**:
1. 定义 ECW hook profile 映射：P0→strict, P1→standard, P2→standard, P3→minimal
2. 从 `session-state.md` 或环境变量读取当前风险等级
3. 各子 hook 声明 `profiles: ["standard", "strict"]` 适用范围
4. P3 跳过知识文件同步检查、TDD 覆盖检查等非必须项

---

### B-3. PostToolUse 质量门禁 — 编辑后即时反馈 (P1)

**问题**: ECW 仅在"标记完成"时做检查（PreToolUse on TaskUpdate），错过了编辑过程中的即时反馈机会。问题积累到最后才发现，增加 impl-verify 迭代轮数。

**当前状态**: 无 PostToolUse hook

**ECC 参考**:
- [`scripts/hooks/quality-gate.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/quality-gate.js) — 编辑后自动格式检查（Biome/Prettier/gofmt/ruff）
- [`scripts/hooks/post-edit-accumulator.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/post-edit-accumulator.js) — 累积编辑文件列表，Stop 时批量处理
- [`scripts/hooks/design-quality-check.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/design-quality-check.js) — 编辑后启发式质量信号检测

**应做的事**:
1. 新建 `hooks/post-edit-check.py`，注册为 `PostToolUse` on `Edit|Write`
2. 轻量检查：修改的文件是否属于已知受保护路径、是否引入明显反模式
3. 累积已修改文件列表，供 impl-verify 使用（免重新 git diff）
4. 检测常见反模式：空 catch 块、TODO 注释、hardcoded credentials

---

## 类别 C：安全与治理

**目标**: 为企业场景补齐安全基线，保护关键配置文件和敏感数据

### C-1. 配置文件保护 — 防止 Agent 意外修改 ECW 配置 (P0)

**问题**: `ecw.yml`、`domain-registry.md`、`change-risk-classification.md` 等是 ECW 运行的基石。Agent 在实现过程中可能误修改这些文件。

**当前状态**: 无配置保护机制

**ECC 参考**:
- [`scripts/hooks/config-protection.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/config-protection.js) — 保护 ~30 个 linter/formatter 配置文件，basename 匹配，exit code 2 阻断，"fix the source, not the config" 消息

**应做的事**:
1. 在 PreToolUse dispatcher 中新增 config-protection 子模块
2. 保护文件列表：`ecw.yml`, `domain-registry.md`, `change-risk-classification.md`, `ecw-path-mappings.md`, `cross-domain-rules.md`
3. 阻断消息：引导修改源代码或知识文件而非配置
4. 提供 `--allow-config-edit` 环境变量供手动覆盖

---

### C-2. 敏感数据扫描 — Secret/PII 检测 (P1)

**问题**: ECW 处理需求描述、代码 diff、knowledge 文件，这些内容可能包含密码、API key、客户数据。当前无任何检测。

**当前状态**: 无敏感数据检测

**ECC 参考**:
- [`scripts/hooks/governance-capture.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/governance-capture.js) — 5 类 secret 模式检测（AWS key、generic secret、private key、JWT、GitHub token）、命令指纹、severity 分级
- [`the-security-guide.md`](https://github.com/affaan-m/everything-claude-code/blob/main/the-security-guide.md) — 完整的安全架构：隔离、权限最小化、内容消毒、审批边界

**应做的事**:
1. 在 verify-completion 中新增 secret 扫描子模块
2. 检测模式：AWS key (`AKIA`/`ASIA`)、generic secret (`password|token|api_key=`)、private key、JWT、hardcoded IP/port
3. 对写入 `.env`、`credentials`、`*.pem`、`*.key` 的操作发出警告
4. 在 impl-verify 的 subagent prompt 中增加"不得在代码中硬编码 secret"规则

---

### C-3. Bash 命令预检 — 阻断危险操作 (P1)

**问题**: Agent 在 impl-orchestration 中可能执行危险命令（`git push --force`、`rm -rf`、`--no-verify`），当前无拦截。

**当前状态**: 无 Bash PreToolUse 检查

**ECC 参考**:
- [`scripts/hooks/block-no-verify.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/block-no-verify.js) — 精确解析 git 命令，阻断 `--no-verify` 和 `core.hooksPath` 覆盖
- [`scripts/hooks/gateguard-fact-force.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/gateguard-fact-force.js) — 破坏性命令（`rm -rf`, `git reset --hard`, `DROP TABLE`）需先提供事实证据

**应做的事**:
1. 在 PreToolUse dispatcher 中新增 bash-preflight 子模块
2. 阻断 `--no-verify`、`git push --force`、`git reset --hard`
3. 对 `rm -rf`、`DROP TABLE`、`DELETE FROM` 要求确认
4. 白名单：`git status`、`git diff`、`git log` 等只读命令放行

---

### C-4. Fact-Forcing Gate — 编辑前要求调查 (P2)

**问题**: Agent 可能在未充分理解影响范围的情况下直接修改文件。ECC 的 gateguard 是最创新的 hook：不问"你确定吗"（LLM 总是回答"是"），而是要求提供具体事实。

**当前状态**: 无事实强制机制

**ECC 参考**:
- [`scripts/hooks/gateguard-fact-force.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/gateguard-fact-force.js) — 首次编辑文件时要求：列出所有 import 该文件的文件、列出受影响的 public API、引用用户指令原文

**应做的事**:
1. 在 impl-orchestration 的 subagent prompt 中嵌入类似要求
2. 要求 implementer subagent 在编辑前引用 Plan 中对应 Task 的原文
3. 对跨域文件修改（path-mappings 中不在当前域的文件）要求额外的影响分析
4. (可选) 实现为 PreToolUse hook，对 Edit/Write 首次操作做事实检查

---

### C-5. 治理审计与成本追踪 (P2)

**问题**: 企业场景需要操作审计线索和成本可见性。ECW 的 P0 工作流（risk-classifier 三阶段 + domain-collab 三轮 + spec-challenge + impl-orchestration）token 消耗可观，但用户无感知。

**当前状态**: 无审计/成本追踪

**ECC 参考**:
- [`scripts/hooks/cost-tracker.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/cost-tracker.js) — Stop 时记录 token 用量到 JSONL，按模型估算成本
- [`scripts/hooks/governance-capture.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/governance-capture.js) — 命令指纹 + severity 分级事件
- [`scripts/hooks/session-activity-tracker.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/session-activity-tracker.js) — 工具活动记录 + 自动脱敏

**应做的事**:
1. 在 Ledger (session-state.md) 中记录每个 Skill/Subagent 的启动时间和完成时间
2. (可选) Stop hook 中追踪 token 用量，按 Skill 聚合
3. 为 P0/P1 工作流生成成本摘要报告

---

## 类别 D：持续学习与知识沉淀

**目标**: 让 ECW 从历史会话中学习，越用越准

### D-1. Phase 3 校准结果持久化 — 风险分类自我改进 (P1)

**问题**: risk-classifier Phase 3 做事后校准（预测 vs 实际），但校准结果仅停留在当前会话上下文中，不影响未来分类。

**当前状态**: Phase 3 存在但无持久化

**ECC 参考**:
- [`skills/continuous-learning-v2/SKILL.md`](https://github.com/affaan-m/everything-claude-code/blob/main/skills/continuous-learning-v2/SKILL.md) — Instinct 模型：原子行为模式 + confidence score(0.3-0.9) + 证据支撑
- 项目级隔离：通过 git remote URL hash 确保跨项目不污染

**应做的事**:
1. Phase 3 校准结果写入 `templates/calibration-log.md` 格式的持久文件
2. SessionStart hook 注入最近 N 条校准偏差摘要作为"active concerns"
3. risk-classifier Phase 1 参考历史校准偏差调整初始预评估
4. 项目级隔离：每个项目维护独立的校准历史

---

### D-2. Instinct 注入框架 — 领域级行为模式 (P2)

**问题**: ECC 的 instinct 系统能将历史经验转化为可注入的行为模式（带 confidence score），ECW 完全缺乏此机制。

**当前状态**: 无

**ECC 参考**:
- [`skills/continuous-learning-v2/SKILL.md`](https://github.com/affaan-m/everything-claude-code/blob/main/skills/continuous-learning-v2/SKILL.md) — YAML frontmatter 格式的 instinct 文件，Top 6 按 confidence 注入
- `the-longform-guide.md` — "When Claude Code discovers something non-trivial, it saves that knowledge as a new skill"

**应做的事**:
1. 定义 ECW instinct 格式（trigger + action + confidence + domain + evidence）
2. impl-verify 反复出现的 finding → 自动生成 instinct
3. domain-collab 发现的跨域冲突模式 → 生成 instinct
4. SessionStart 注入当前项目的 Top instincts

---

### D-3. 文件产出隔离 — 解决多需求覆盖风险 (P1)

**问题**: MEMORY.md 已记录此问题 — ECW 过程文件（session-state.md、requirements-summary.md 等）无任务级隔离，多需求并行时存在覆盖风险。

**当前状态**: 已知问题，暂缓处理

**ECC 参考**:
- continuous-learning-v2 的项目级隔离：通过 git remote URL hash 生成唯一目录
- session-start.js 的 session ID 隔离：每个 session 有独立的状态文件

**应做的事**:
1. 为每个 ECW 工作流实例生成唯一 ID（基于需求描述 hash 或时间戳）
2. session-data 目录结构：`.claude/ecw/session-data/{workflow-id}/`
3. session-state.md 支持多活跃工作流并存
4. SessionStart hook 检测未完成工作流并提示恢复

---

## 类别 E：Context 管理优化

**目标**: 降低 token 浪费，改善长会话稳定性

### E-1. 主动压缩建议 — 基于 Tool-Call 计数器 (P1)

**问题**: ECW 依赖系统自动压缩，没有在"逻辑断点"主动建议压缩的机制。P0 工作流可能 500+ turn，系统压缩时机不可控。

**当前状态**: 仅有 PreCompact hook（被动响应）

**ECC 参考**:
- [`scripts/hooks/suggest-compact.js`](https://github.com/affaan-m/everything-claude-code/blob/main/hooks/strategic-compact/compact-suggest.js) — tool-call 计数器，阈值(50)时建议，之后每 25 次提醒
- `the-longform-guide.md` — "Disable auto-compaction and manually compact at logical intervals"

**应做的事**:
1. 在 PreToolUse dispatcher 中新增计数器子模块
2. ECW 特定的逻辑断点：Phase 切换时、Skill 完成时、subagent 全部返回后
3. 建议消息包含："已完成 XX，建议 compact 后继续 YY"
4. 可通过 `ECW_COMPACT_THRESHOLD` 环境变量配置阈值

---

### E-2. 工作模式声明 — 按阶段区分上下文需求 (P2)

**问题**: 需求分析、编码实现、验证审查使用相同上下文密度，浪费 token。ECC 通过 context 文件区分不同工作模式。

**当前状态**: 无模式区分

**ECC 参考**:
- [`contexts/dev.md`](https://github.com/affaan-m/everything-claude-code/blob/main/contexts/dev.md) — 开发模式：写代码优先，保持原子提交
- [`contexts/review.md`](https://github.com/affaan-m/everything-claude-code/blob/main/contexts/review.md) — 审查模式：severity 分级，安全检查清单
- [`contexts/research.md`](https://github.com/affaan-m/everything-claude-code/blob/main/contexts/research.md) — 探索模式：广泛阅读后再结论

**应做的事**:
1. 在 session-state.md 中增加 `current_mode` 字段
2. 定义 ECW 模式：`analysis`（需求分析）、`planning`（计划制定）、`implementation`（编码）、`verification`（验证）
3. 各模式附带简短行为指引（类似 ECC context 文件）
4. Skill 切换时自动更新模式

---

### E-3. Marker-Based 幂等更新 — 替代全文覆盖 (P1)

**问题**: 当前 session-state.md 更新采用全文覆盖（Write tool），如果两个操作并发写入，后者覆盖前者。

**当前状态**: Write tool 全文覆盖

**ECC 参考**:
- `session-end.js` — 使用 `<!-- ECC:SUMMARY:START -->` / `<!-- ECC:SUMMARY:END -->` marker 做区域替换
- Header 字段保持不变，只更新 marker 内的内容

**应做的事**:
1. 定义 session-state.md 的 marker 区域：`<!-- ECW:LEDGER:START/END -->`、`<!-- ECW:STATUS:START/END -->`
2. 更新时仅替换对应 marker 区域，保留其他部分
3. Stop hook 和 Skill 内部写入都使用 marker 机制

---

## 类别 F：Rules 规则系统

**目标**: 建立独立于 Skill 的始终生效工程规范

### F-1. 通用规则层 — 安全/测试/代码风格始终生效 (P1)

**问题**: ECW 的工程规范嵌入在各 SKILL.md 中（特别是 impl-verify），Skill 未触发时无规范约束。ECC 有独立的 rules 层，始终加载到上下文。

**当前状态**: 无独立规则系统

**ECC 参考**:
- [`rules/common/security.md`](https://github.com/affaan-m/everything-claude-code/blob/main/rules/common/security.md) — 8 项预提交安全检查清单
- [`rules/common/testing.md`](https://github.com/affaan-m/everything-claude-code/blob/main/rules/common/testing.md) — 80% 覆盖率、TDD 强制、AAA 模式
- [`rules/common/coding-style.md`](https://github.com/affaan-m/everything-claude-code/blob/main/rules/common/coding-style.md) — 50行函数/800行文件/4层嵌套上限
- [`rules/common/performance.md`](https://github.com/affaan-m/everything-claude-code/blob/main/rules/common/performance.md) — model 分层策略、context window 预算
- [`rules/common/design-patterns.md`](https://github.com/affaan-m/everything-claude-code/blob/main/rules/common/patterns.md) — Repository 模式、API 响应格式
- [`rules/README.md`](https://github.com/affaan-m/everything-claude-code/blob/main/rules/README.md) — 层级覆盖规则（语言专项 > 通用）

**应做的事**:
1. 在 `ecw.yml` 中新增 `rules` 配置节，定义项目适用的规则集
2. 创建 `templates/rules/common/` 目录，提供通用规则模板
3. 规则通过 `ecw-init` 安装到项目 `.claude/ecw/rules/` 目录
4. SessionStart hook 自动加载规则摘要到上下文

---

### F-2. 语言专项规则 — 层级覆盖模型 (P2)

**问题**: ECW 支持 Java/Go/TS/Python 项目（ecw.yml 配置），但无语言级工程规范。

**当前状态**: 无

**ECC 参考**:
- [`rules/java/coding-style.md`](https://github.com/affaan-m/everything-claude-code/blob/main/rules/java/coding-style.md) — Java 特定：records、sealed classes、Optional 使用规范、Stream 操作上限
- [`rules/golang/coding-style.md`](https://github.com/affaan-m/everything-claude-code/blob/main/rules/golang/coding-style.md) — Go 特定：gofmt 强制、interface 设计、error wrapping

**应做的事**:
1. 创建 `templates/rules/java/`、`templates/rules/go/` 等语言目录
2. 语言规则 extends 通用规则，仅覆盖差异部分
3. 规则文件使用 YAML frontmatter 的 `paths` 字段指定适用文件类型
4. impl-verify 读取适用规则文件作为验证标准

---

## 类别 G：Agent 架构升级

**目标**: 提升 subagent 效率、可靠性和成本效益

### G-1. Model 分层策略 — 按任务复杂度选择模型 (P1)

**问题**: ECW 的 subagent 未指定 model（或仅部分指定 sonnet），缺乏成本优化策略。ECC 明确 "90% Sonnet, 复杂用 Opus, 简单用 Haiku"。

**当前状态**: writing-plans subagent 指定 sonnet，impl-verify 指定 sonnet，其余未指定

**ECC 参考**:
- [`rules/common/performance.md`](https://github.com/affaan-m/everything-claude-code/blob/main/rules/common/performance.md) — Haiku: 工作 agent, 3x 节省; Sonnet: 主开发; Opus: 复杂推理
- [`skills/cost-aware-llm-pipeline/SKILL.md`](https://github.com/affaan-m/everything-claude-code/blob/main/skills/cost-aware-llm-pipeline/SKILL.md) — 文本长度/项目数阈值决定 model 升级
- [`.agents/planner.md`](https://github.com/affaan-m/everything-claude-code/blob/main/.agents/planner.md) — model: opus（规划用高端模型）
- [`.agents/code-reviewer.md`](https://github.com/affaan-m/everything-claude-code/blob/main/.agents/code-reviewer.md) — model: sonnet（审查用中端模型）

**应做的事**:
1. 为每个 subagent dispatch 点明确指定 model：
   - risk-classifier Phase 2 subagent → sonnet（已有）
   - domain-collab 域分析 agent → sonnet
   - requirements-elicitation synthesis agent → sonnet
   - writing-plans subagent → sonnet（已有）
   - spec-challenge agent → sonnet
   - impl-orchestration mechanical tasks → haiku
   - impl-orchestration integration/design tasks → sonnet/opus
   - impl-verify verification rounds → sonnet（已有）
   - biz-impact-analysis agent → sonnet
2. 在 SKILL.md 中添加 model 选择说明和升级条件

---

### G-2. Agent 独立化 — 抽取内嵌 Subagent Prompt (P2)

**问题**: 大量 subagent 逻辑内嵌在 SKILL.md 的 prompt template 中，无法独立测试、复用或选择 model。

**当前状态**: 仅 `agents/biz-impact-analysis.md` 和 `agents/spec-challenge.md` 是独立 agent 文件

**ECC 参考**:
- [`.agents/` 目录](https://github.com/affaan-m/everything-claude-code/tree/main/.agents) — 48 个独立 agent 文件，每个有 YAML frontmatter（name, tools, model）
- `.agents/planner.md` — 独立可测试的规划 agent
- `.agents/security-reviewer.md` — 独立的安全审查 agent

**应做的事**:
1. 将 impl-orchestration 的 implementer prompt 和 spec-reviewer prompt 抽取为独立 agent 文件
2. 将 domain-collab 的域分析 agent prompt 抽取为模板
3. 将 impl-verify 的 round subagent prompt 抽取为独立文件
4. 每个 agent 文件包含 YAML frontmatter（name, model, tools 限制）

---

### G-3. 循环安全控制 — impl-orchestration 防护 (P1)

**问题**: impl-orchestration 的 subagent 可能陷入无限循环（spec review 反复不通过、BLOCKED 反复重试），当前无检测和熔断机制。

**当前状态**: 无循环检测

**ECC 参考**:
- [`.agents/loop-operator.md`](https://github.com/affaan-m/everything-claude-code/blob/main/.agents/loop-operator.md) — 检查点追踪、停滞检测、重复失败暂停、成本漂移监控、4 个升级条件

**应做的事**:
1. impl-orchestration 增加每 Task 最大迭代次数（spec review ≤ 3 轮）
2. BLOCKED 状态升级限制：相同 Task 最多 re-dispatch 2 次，之后升级给用户
3. 全局预算：所有 Task 总迭代次数上限（如 15 轮）
4. 检测相同错误重复出现 → 自动暂停并报告

---

### G-4. Subagent 返回值验证 — Schema 校验 (P1)

**问题**: 多个 Skill 期望 subagent 返回特定格式的 YAML/JSON，但无任何校验。格式错误导致静默降级。

**当前状态**: 无校验，直接使用

**ECC 参考**:
- `.agents/code-reviewer.md` 的 confidence-based filtering (>80%) — 只信任高置信度结果
- 通用模式：每个 agent 定义明确的输出格式 + 合并策略

**应做的事**:
1. 定义各 subagent 返回的 YAML schema（risk-classifier Phase 2、domain-collab round、impl-verify round）
2. Coordinator 接收 subagent 返回后，验证必填字段存在
3. 格式错误时：记录到 Ledger + 重试一次 + 仍失败则降级处理
4. 降级处理规则：跳过该 round 并标注"[incomplete]"

---

## 类别 H：Skill 内部质量提升

**目标**: 修复跨所有 Skill 的系统性弱点

### H-1. 统一错误处理模式 (P1)

**问题**: 多数 Skill 详细描述了 happy path，error path 极简或缺失。Subagent 失败、文件写入失败、知识文件缺失等场景无处理。

**受影响 Skill**: 所有 11 个

**应做的事**:
1. 定义 ECW 标准错误处理模板：
   - Subagent dispatch 失败 → 记录 Ledger + 通知用户 + 提供降级路径
   - 文件写入失败 → 重试一次 + 仍失败则输出内容到会话中
   - 知识文件缺失 → 标注 `[degraded: {file} not found]` 并继续
2. 在各 SKILL.md 的关键步骤增加错误处理指引

---

### H-2. Timeout 规范 — 所有 Subagent 调用设超时 (P1)

**问题**: 多数 subagent dispatch 无 timeout 规范，可能无限挂起。

**受影响 Skill**: risk-classifier(Phase 2)、domain-collab(Round 1/2)、requirements-elicitation(synthesis)、spec-challenge、impl-orchestration(implementer/reviewer)、impl-verify(rounds)、biz-impact-analysis

**应做的事**:
1. 在各 SKILL.md 的 Agent dispatch 步骤增加 timeout 建议值
2. 轻量 subagent (haiku) → 60s, 标准 subagent (sonnet) → 180s, 重型 subagent (opus) → 300s
3. 超时处理：记录 Ledger + 提供降级路径

---

### H-3. 循环终止条件补全 (P1)

**问题**: 多个交互式循环缺乏终止条件：requirements-elicitation 的 Q&A 轮次、spec-challenge 的 "Needs discussion" 循环、impl-verify 的 fix-re-verify 循环。

**受影响 Skill**: requirements-elicitation、spec-challenge、impl-verify、cross-review

**应做的事**:
1. requirements-elicitation：最大问题轮次上限（如 P0: 15轮, P1: 10轮, P2: 5轮）
2. spec-challenge："Needs discussion" 最大 3 轮后强制进入决策
3. impl-verify：已有 5 轮上限，补充"连续两轮 must-fix 数量不减少 → 升级给用户"
4. cross-review：增加"同一不一致连续 2 轮出现 → 标记为已知问题并跳过"

---

### H-4. 状态检查点 — 防 Context 压缩丢失 (P1)

**问题**: 长流程中如果 context 压缩发生在关键数据产出之后但持久化之前，数据丢失。

**受影响 Skill**: systematic-debugging(Phase 1-5 证据)、requirements-elicitation(Q&A 历史)、domain-collab(Round 1/2 返回)、tdd(cycle 日志)

**应做的事**:
1. 定义"检查点写入时机"：每个 Round/Phase 完成后立即写入 session-data
2. systematic-debugging：Phase 1 完成后写入 `session-data/debug-evidence.md`
3. tdd P0：每个 cycle 完成后追加到 `session-data/tdd-cycles.md`
4. requirements-elicitation：每轮 Q&A 后追加到 requirements-summary.md

---

### H-5. 知识文件健壮性 — 缺失/格式错误处理 (P2)

**问题**: 所有 Skill 假设知识文件（domain-registry.md、shared-resources.md、cross-domain-rules.md 等）存在且格式正确。文件缺失或格式错误导致静默降级。

**受影响 Skill**: risk-classifier、domain-collab、writing-plans、impl-verify、biz-impact-analysis

**应做的事**:
1. 在 ecw-validate-config 中增加知识文件格式校验
2. 各 Skill 的"读取知识文件"步骤增加存在性检查
3. 缺失时：输出 `[Warning: {file} not found, analysis degraded]` 并继续
4. 格式错误时：尝试 best-effort 解析 + 标注降级

---

### H-6. impl-verify 内部矛盾修复 (P2)

**问题**: impl-verify 存在文档内矛盾："do not re-execute git diff"（Diff Read Strategy）vs "re-execute for Round N+"（conditional trigger section）。

**受影响 Skill**: impl-verify

**应做的事**:
1. 澄清 Diff Read Strategy：首次缓存 + 修复后增量 diff
2. Round N+ 应使用增量 diff（仅 fix 涉及的文件），而非完整 re-diff
3. 统一术语和行为描述

---

### H-7. 语言硬编码清理 (P3)

**问题**: spec-challenge agent prompt 中硬编码了"请用中文输出"。应由 ecw.yml 配置控制。

**受影响 Skill**: spec-challenge、部分其他 Skill

**应做的事**:
1. 在 ecw.yml 中增加 `output_language` 配置项
2. 各 subagent prompt 从配置读取输出语言
3. 默认值：跟随项目 CLAUDE.md 中的语言设置

---

## 类别 I：开发者体验与质量保障

**目标**: 降低使用门槛，扩大测试覆盖

### I-1. 代码质量工具链 — Linter/Formatter (P2)

**问题**: ECW 仓库无代码质量工具链，SKILL.md 和 Python hook 的格式全靠人工保证。

**当前状态**: 无

**ECC 参考**:
- [`commitlint.config.js`](https://github.com/affaan-m/everything-claude-code/blob/main/commitlint.config.js) — conventional commits 规范
- [`.markdownlint.json`](https://github.com/affaan-m/everything-claude-code/blob/main/.markdownlint.json) — markdown 格式检查
- [`eslint.config.js`](https://github.com/affaan-m/everything-claude-code/blob/main/eslint.config.js) — JS lint 规则

**应做的事**:
1. 添加 markdownlint 配置（SKILL.md 格式检查）
2. 添加 ruff/flake8 配置（Python hook 代码质量）
3. 在 tests/Makefile 的 `lint` target 中集成
4. (可选) commitlint 规范提交消息

---

### I-2. 测试覆盖扩展 — Layer 2 覆盖更多 Skill (P2)

**问题**: Layer 2 (promptfoo eval) 仅覆盖 risk-classifier 的路由决策，其余 10 个 Skill 无行为验证。

**当前状态**: 17 个 eval 场景，全部针对 risk-classifier

**应做的事**:
1. 为 domain-collab 新增 eval：给定跨域需求 → 验证正确路由到多域分析
2. 为 tdd 新增 eval：给定 P0 需求 → 验证强制执行 RED-GREEN-REFACTOR
3. 为 impl-verify 新增 eval：给定代码变更 → 验证检出已知 bug 模式
4. 每个新 eval 类别 3-5 个场景

---

### I-3. 贡献指南与故障排查文档 (P3)

**问题**: ECW 缺少贡献指南和故障排查文档，新用户遇到问题无处参考。

**当前状态**: README.md + CHANGELOG.md

**ECC 参考**:
- [`CONTRIBUTING.md`](https://github.com/affaan-m/everything-claude-code/blob/main/CONTRIBUTING.md) — 贡献类型、格式规范、审核流程
- [`TROUBLESHOOTING.md`](https://github.com/affaan-m/everything-claude-code/blob/main/TROUBLESHOOTING.md) — 常见问题和修复

**应做的事**:
1. 添加 CONTRIBUTING.md（Skill 开发规范、hook 开发规范、测试要求）
2. 添加 TROUBLESHOOTING.md（常见配置错误、hook 不触发、session-state 损坏等场景）
3. README 中添加快速排错指引

---

### I-4. 桌面通知 — 长任务完成通知 (P3)

**问题**: impl-orchestration 可能运行很长时间，用户无感知。

**当前状态**: 无

**ECC 参考**:
- [`scripts/hooks/notification.js`](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/notification.js) — macOS osascript / WSL BurntToast，Stop 时发送桌面通知

**应做的事**:
1. 在 Stop hook 中集成桌面通知（macOS: osascript, Linux: notify-send）
2. 仅在 impl-orchestration 等长任务完成时触发
3. 可通过 `ECW_NOTIFY` 环境变量开关

---

## 优先级总览

| 优先级 | 问题数 | 类别 |
|--------|--------|------|
| P0 | 3 | A-1, A-2, C-1 |
| P1 | 16 | A-3, B-1, B-2, B-3, C-2, C-3, D-1, D-3, E-1, E-3, F-1, G-1, G-3, G-4, H-1~H-4 |
| P2 | 10 | A-4, C-4, C-5, D-2, E-2, F-2, G-2, H-5, H-6, I-1~I-2 |
| P3 | 3 | H-7, I-3, I-4 |

## 建议 Session 分配

| Session | 类别 | 问题 | 预估工作量 |
|---------|------|------|-----------|
| Session 1 | A (Session 生命周期) | A-1, A-2, A-3, A-4 | 中 |
| Session 2 | B (Hooks 基础设施) | B-1, B-2, B-3 | 中 |
| Session 3 | C (安全与治理) | C-1, C-2, C-3, C-4, C-5 | 中-高 |
| Session 4 | D (持续学习) | D-1, D-2, D-3 | 高 |
| Session 5 | E (Context 管理) | E-1, E-2, E-3 | 中 |
| Session 6 | F (Rules 系统) | F-1, F-2 | 中 |
| Session 7 | G (Agent 架构) | G-1, G-2, G-3, G-4 | 高 |
| Session 8 | H (Skill 内部质量) | H-1~H-7 | 高 |
| Session 9 | I (开发者体验) | I-1~I-4 | 低-中 |
