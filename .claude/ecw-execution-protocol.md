# ECW 改进执行协议

> 核心原则：**每个类别 = 一个独立 session**，靠文件传递上下文，不靠 context window 记忆

---

## 为什么不能在同一个 session 里做

| 问题 | 后果 |
|------|------|
| Context window ~200K token，每个类别消耗 50-100K | 第 2 个类别开始就会触发压缩 |
| 压缩后丢失 ECC 参考模式的具体细节 | 后面的实现不符合前面建立的模式 |
| 压缩后丢失设计决策的 WHY | 反复做出矛盾的决策 |
| 多类别混在一个 context 中互相干扰 | Skill A 的错误处理模式被 Skill B 的写法覆盖 |

## 执行架构

```
┌─────────────────────────────────────────────────┐
│              文件系统（持久层）                    │
│                                                 │
│  .claude/ecw-improvement-issues.md  ← 问题清单   │
│  .claude/ecw-wave-progress.md       ← 波次进度   │
│  .claude/ecw-patterns/              ← 参考模式   │
│    ├── hook-patterns.md                         │
│    ├── skill-patterns.md                        │
│    └── conventions.md                           │
│                                                 │
└──────────┬──────────┬──────────┬────────────────┘
           │ 读       │ 读       │ 读
     ┌─────▼───┐ ┌───▼─────┐ ┌▼─────────┐
     │Session 1│ │Session 2│ │Session 3  │
     │ Wave1-B │ │ Wave1-F │ │ Wave2-A   │
     │(独立会话)│ │(独立会话)│ │(独立会话)  │
     └─────┬───┘ └───┬─────┘ └┬─────────┘
           │ 写       │ 写      │ 写
           ▼          ▼         ▼
     wave-progress.md 更新完成状态
```

## 每个 Session 的启动 Prompt

直接在新 Claude Code 会话中粘贴：

```
读取以下文件，然后执行类别 X 的改进：

1. .claude/ecw-improvement-issues.md — 找到类别 X 的所有 issue
2. .claude/ecw-patterns/conventions.md — 遵循已建立的编码约定
3. .claude/ecw-wave-progress.md — 了解前序波次的完成状态

按 issue 清单的"应做的事"逐项实现。每完成一个 issue，
更新 wave-progress.md 标记完成。

完成所有 issue 后，运行验证：
- make lint （如果改了 Python）
- make test-hook （如果改了 hook）
- make eval-quick （如果改了 SKILL.md）
```

## 波次执行流程

### Wave 1（基座层）

**并行 2 个独立 session：**

| Session | 类别 | Worktree 分支 | 改动范围 |
|---------|------|--------------|---------|
| 1-a | B (Hooks 基础设施) | `wave1/hooks-infra` | hooks/ 目录重构 |
| 1-b | F (Rules) + I-1,I-3 (Linter/Docs) | `wave1/rules-devex` | templates/rules/, 根目录 docs |

**完成条件：**
- [ ] hooks.json 改为 dispatcher 模式
- [ ] verify-completion.py 拆分为子模块
- [ ] Profile 机制 (P0→strict, P3→minimal) 可用
- [ ] templates/rules/common/ 目录存在
- [ ] ecw.yml 有 rules 配置节

**波次结束操作（在主分支上手动执行）：**
```bash
git merge wave1/hooks-infra
git merge wave1/rules-devex    # 无冲突：不同文件
# 更新 wave-progress.md
```

### Wave 2（核心层）

**并行 2-3 个独立 session：**

| Session | 类别 | Worktree 分支 | 改动范围 |
|---------|------|--------------|---------|
| 2-a | A (Session 生命周期) | `wave2/session-hooks` | hooks/ 新文件 |
| 2-b | G (Agent 架构) | `wave2/agent-arch` | skills/*/SKILL.md, agents/ |
| 2-c | C-1 (Config 保护) | `wave2/config-protect` | hooks/ 小子模块 |

**依赖：** 必须 Wave 1 merge 完成后才开始

**完成条件：**
- [ ] SessionStart/Stop/SessionEnd hook 可用
- [ ] 所有 subagent dispatch 有 model 指定
- [ ] agents/ 下新增独立 agent 文件
- [ ] ecw.yml/domain-registry.md 等受保护

### Wave 3（深化层）

**并行 2-3 个独立 session：**

| Session | 类别 | Worktree 分支 | 改动范围 |
|---------|------|--------------|---------|
| 3-a | H (Skill 内部质量) | `wave3/skill-quality` | skills/*/SKILL.md |
| 3-b | E (Context 管理) | `wave3/context-mgmt` | hooks/pre-compact.py, session-state 格式 |
| 3-c | C-2~5 (安全剩余) | `wave3/security` | hooks/ 子模块 |

**依赖：** 必须 Wave 2 merge 完成后才开始

### Wave 4（增值层）

**并行 2 个独立 session：**

| Session | 类别 | Worktree 分支 | 改动范围 |
|---------|------|--------------|---------|
| 4-a | D (持续学习) | `wave4/learning` | templates/, session-data 格式 |
| 4-b | I-2,I-4 (测试+通知) | `wave4/test-notify` | tests/, hooks/notify |

---

## 质量一致性保障：Pattern 文件

> **这是对抗 context 压缩的关键武器** — 把设计决策固化为文件，而非依赖 Claude 的记忆

### .claude/ecw-patterns/conventions.md

在 Wave 1 开始前创建，所有 session 必须遵循：

```markdown
# ECW 编码约定

## Hook 开发约定
- 语言：Python 3.8+（与 verify-completion.py 一致）
- 入口：`def main():`，从 `sys.stdin` 读 JSON
- 错误处理：`try/except` 包裹 main()，异常时 `sys.exit(0)` 不阻塞
- 输出：JSON `{"result": "continue|block", ...}` 到 stdout
- 日志：写 stderr，不写 stdout
- 子模块注册：通过 dispatcher.py，不直接注册到 hooks.json

## SKILL.md 修改约定
- 新增 subagent dispatch 必须指定 model（haiku/sonnet/opus）
- 新增步骤必须包含错误处理（失败 → Ledger 记录 + 降级路径）
- 循环结构必须有终止条件（最大轮次 + 升级规则）
- 检查点写入时机：每个 Round/Phase 完成后立即写入 session-data/

## 文件写入约定
- session-state.md 使用 marker-based 更新（<!-- ECW:SECTION:START/END -->）
- 新配置节加到 ecw.yml 末尾，不打乱现有结构
- 新 agent 文件使用 YAML frontmatter（name, model, tools）

## 命名约定
- Hook 文件：`hooks/{功能名}.py`（如 session-start.py, config-protect.py）
- 子模块函数：`check_{功能名}(input_data, config)` 返回 (result, message)
- 测试文件：`tests/static/test_{功能名}.py`
```

### .claude/ecw-patterns/hook-patterns.md

从 ECC 提取的关键模式，本地化为 ECW 适用版本（避免每个 session 重新 fetch GitHub）：

```markdown
# Hook 实现参考模式

## 1. Dispatcher 模式（来源：ECC bash-hook-dispatcher.js）
单个 hooks.json 注册 → dispatcher.py → 按 profile 过滤 → 串联子模块

## 2. Profile 门控（来源：ECC hook-flags.js）
ECW 映射：P0→strict, P1→standard, P2→standard, P3→minimal
子模块声明 profiles=["standard","strict"]，dispatcher 按当前风险等级过滤

## 3. Marker-Based 幂等更新（来源：ECC session-end.js）
<!-- ECW:LEDGER:START --> ... <!-- ECW:LEDGER:END -->
更新时正则匹配 marker 区域，替换内容，保留文件其余部分

## 4. 配置保护（来源：ECC config-protection.js）
basename 匹配保护文件列表 → exit code 2 阻断 → "修改源代码而非配置"
```

### .claude/ecw-patterns/skill-patterns.md

```markdown
# SKILL.md 修改参考模式

## 1. Subagent Dispatch 标准格式
dispatch via Agent tool, model: {haiku|sonnet|opus}
timeout 建议：haiku 60s, sonnet 180s, opus 300s
返回值验证：检查必填字段存在，格式错误 → 重试一次 → 降级

## 2. 错误处理标准模板
- Subagent 失败 → 记录 Ledger "[FAILED: {agent_name}]" + 通知用户 + 降级路径
- 文件写入失败 → 重试一次 + 仍失败则输出到会话
- 知识文件缺失 → "[degraded: {file} not found]" 标注 + 继续

## 3. 循环终止标准
- 交互循环：最大轮次 (P0:15, P1:10, P2:5)
- 收敛循环：连续 2 轮无改善 → 升级给用户
- Fix-verify 循环：≤5 轮（已有） + 同错重现 → 升级
```

---

## Wave Progress 跟踪文件

每个 session 完成后更新此文件：

```markdown
# Wave Progress

## Wave 1 — 基座层
- [ ] B-1 Hook 调度器模式
- [ ] B-2 风险等级 Profile
- [ ] B-3 PostToolUse 质量门禁
- [ ] F-1 通用规则层
- [ ] F-2 语言专项规则
- [ ] I-1 代码质量工具链
- [ ] I-3 贡献指南与故障排查

## Wave 2 — 核心层
- [ ] A-1 SessionStart hook
- [ ] A-2 Stop hook
- [ ] A-3 Pre-compact 增强
- [ ] A-4 SessionEnd hook
- [ ] G-1 Model 分层策略
- [ ] G-2 Agent 独立化
- [ ] G-3 循环安全控制
- [ ] G-4 Subagent 返回值验证
- [ ] C-1 配置文件保护

## Wave 3 — 深化层
- [ ] H-1 统一错误处理
- [ ] H-2 Timeout 规范
- [ ] H-3 循环终止条件
- [ ] H-4 状态检查点
- [ ] H-5 知识文件健壮性
- [ ] H-6 impl-verify 矛盾修复
- [ ] E-1 主动压缩建议
- [ ] E-2 工作模式声明
- [ ] E-3 Marker-Based 幂等更新
- [ ] C-2 敏感数据扫描
- [ ] C-3 Bash 命令预检
- [ ] C-4 Fact-Forcing Gate
- [ ] C-5 治理审计与成本追踪

## Wave 4 — 增值层
- [ ] D-1 Phase 3 校准持久化
- [ ] D-2 Instinct 注入框架
- [ ] D-3 文件产出隔离
- [ ] I-2 测试覆盖扩展
- [ ] I-4 桌面通知
- [ ] H-7 语言硬编码清理
```
