# ECW 改进 — Wave Progress

> 每个 session 完成后更新此文件。用 `[x]` 标记完成，附 commit hash。

## Wave 1 — 基座层

### Session 1-a: B (Hooks 基础设施) — branch: `wave1/hooks-infra`
- [x] B-1 Hook 调度器模式 — dispatcher.py + hooks.json 重构 (`b04e97a`)
- [x] B-2 风险等级 Profile — P0→strict, P1/P2→standard, P3→minimal (`608e41c`)
- [x] B-3 PostToolUse 质量门禁 — post-edit-check 子模块 (`76ff3eb`)

### Session 1-b: F (Rules) + I 部分 — branch: `wave1/rules-devex`
- [x] F-1 通用规则层 — templates/rules/common/ (`9e4fa72`)
- [x] F-2 语言专项规则 — templates/rules/java/, go/ (`a1c2182`)
- [x] I-1 代码质量工具链 — markdownlint, ruff (`cba99ea`)
- [x] I-3 贡献指南 — CONTRIBUTING.md, TROUBLESHOOTING.md (`0073cdc`)

**Wave 1 merge checklist:**
- [x] `git merge wave1/hooks-infra` — merged
- [x] `git merge wave1/rules-devex` — merged, Makefile 冲突已解决
- [x] `make lint` 通过
- [x] `make test-hook` 通过

---

## Wave 2 — 核心层

### Session 2-a: A (Session 生命周期) — branch: `wave2/session-hooks`
- [x] A-1 SessionStart hook (`ef38541`)
- [x] A-2 Stop hook (`01deb56`)
- [x] A-3 Pre-compact 增强 (`7831c30`)
- [x] A-4 SessionEnd hook (`46e216e`)

### Session 2-b: G (Agent 架构) — branch: `wave2/agent-arch`
- [x] G-1 Model 分层策略 — 所有 SKILL.md 的 subagent dispatch 指定 model (`216fb73`)
- [x] G-2 Agent 独立化 — 抽取 impl-orchestration/impl-verify 的 subagent prompt (`7f73d93`)
- [x] G-3 循环安全控制 — impl-orchestration 最大迭代 + 熔断 (`f077d2e`)
- [x] G-4 Subagent 返回值验证 — schema 检查 + 重试 + 降级 (`52ad78c`)

### Session 2-c: C-1 (Config 保护) — branch: `wave2/config-protect`
- [x] C-1 配置文件保护 — config-protect 子模块

**Wave 2 merge checklist:**
- [x] `git merge wave2/session-hooks` — merged, 无冲突
- [x] `git merge wave2/agent-arch` — merged, wave-progress 自动合并
- [x] `git merge wave2/config-protect` — merged, Makefile test-hook 行冲突已解决 (`dd50b0e`)
- [x] `make lint` 通过 — 3 warnings, all checks passed
- [x] `make test-hook` 通过 — 204 passed in 0.44s

---

## Wave 3 — 深化层

### Session 3-a: H (Skill 内部质量) — branch: `wave3/skill-quality`
- [x] H-1 统一错误处理 — 所有 SKILL.md 关键步骤增加错误处理 (`5899e0f`)
- [x] H-2 Timeout 规范 — 所有 subagent dispatch 增加 timeout (`f83be43`)
- [x] H-3 循环终止条件 — requirements-elicitation/spec-challenge/impl-verify/cross-review (`113884f`)
- [x] H-4 状态检查点 — systematic-debugging/tdd/requirements-elicitation/domain-collab (`a1dea11`)
- [x] H-5 知识文件健壮性 — 存在性检查 + 降级标注 (`5563399`)
- [x] H-6 impl-verify 矛盾修复 (`d0c3900`)

### Session 3-b: E (Context 管理) — branch: `wave3/context-mgmt`
- [x] E-3 Marker-Based 幂等更新 — marker_utils.py 共享模块 + session-state 模板 (`f097ece`)
- [x] E-1 主动压缩建议 — compact-suggest.py 计数器子模块 (`c26b46d`)
- [x] E-2 工作模式声明 — session-state MODE 字段 + 5 个 SKILL.md 模式切换 (`ce463f5`)

### Session 3-c: C-2~5 (安全剩余) — branch: `wave3/security`
- [x] C-2 敏感数据扫描 — secret-scan.py 子模块 (`e6b7288`)
- [x] C-3 Bash 命令预检 — bash-preflight.py 子模块 (`e6b7288`)
- [x] C-4 Fact-Forcing Gate — implementer prompt 增加事实溯源门控 (`0da5a4a`)
- [x] C-5 治理审计与成本追踪 — Ledger 增加 Started/Duration 列 (`febde0a`)

**Wave 3 merge checklist:**
- [x] `git merge wave3/skill-quality` — 3 SKILL.md 冲突已解决 (`767d6ba`)
- [x] `git merge wave3/context-mgmt` — dispatcher.py + Makefile 冲突已解决 (`6342cb0`)
- [x] `git merge wave3/security` — 6 冲突已解决 (dispatcher/Makefile/4 SKILL.md + implementer modify/delete) (`7649ec3`)
- [x] `make lint` 通过 — 3 warnings, all checks passed
- [x] `make test-hook` 通过 — 301 passed in 0.54s

---

## Wave 4 — 增值层

### Session 4-a: D (持续学习) — branch: `wave4/learning`
- [x] D-1 Phase 3 校准持久化 (`459b808`)
- [x] D-2 Instinct 注入框架 (`9e76369`)
- [x] D-3 文件产出隔离 (`c8dda93`)

### Session 4-b: I 剩余 — branch: `wave4/test-notify`
- [x] I-2 测试覆盖扩展 — domain-collab/tdd/impl-verify eval (`cf404c3`)
- [ ] I-4 桌面通知 (skipped)
- [x] H-7 语言硬编码清理 (`ea3229c`)

**Wave 4 merge checklist:**
- [ ] 两个分支 merge 无冲突
- [ ] `make all` 通过（完整测试）
- [ ] 版本号更新
