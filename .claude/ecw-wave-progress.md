# ECW 改进 — Wave Progress

> 每个 session 完成后更新此文件。用 `[x]` 标记完成，附 commit hash。

## Wave 1 — 基座层

### Session 1-a: B (Hooks 基础设施) — branch: `wave1/hooks-infra`
- [x] B-1 Hook 调度器模式 — dispatcher.py + hooks.json 重构 (`b04e97a`)
- [x] B-2 风险等级 Profile — P0→strict, P1/P2→standard, P3→minimal (`608e41c`)
- [x] B-3 PostToolUse 质量门禁 — post-edit-check 子模块 (`76ff3eb`)

### Session 1-b: F (Rules) + I 部分 — branch: `wave1/rules-devex`
- [ ] F-1 通用规则层 — templates/rules/common/
- [ ] F-2 语言专项规则 — templates/rules/java/, go/
- [ ] I-1 代码质量工具链 — markdownlint, ruff
- [ ] I-3 贡献指南 — CONTRIBUTING.md, TROUBLESHOOTING.md

**Wave 1 merge checklist:**
- [ ] `git merge wave1/hooks-infra` 无冲突
- [ ] `git merge wave1/rules-devex` 无冲突
- [ ] `make lint` 通过
- [ ] `make test-hook` 通过

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
- [ ] C-1 配置文件保护 — config-protect 子模块

**Wave 2 merge checklist:**
- [ ] `git merge wave2/session-hooks` 无冲突
- [ ] `git merge wave2/agent-arch` 无冲突
- [ ] `git merge wave2/config-protect` 无冲突
- [ ] `make lint` 通过
- [ ] `make test-hook` 通过

---

## Wave 3 — 深化层

### Session 3-a: H (Skill 内部质量) — branch: `wave3/skill-quality`
- [ ] H-1 统一错误处理 — 所有 SKILL.md 关键步骤增加错误处理
- [ ] H-2 Timeout 规范 — 所有 subagent dispatch 增加 timeout
- [ ] H-3 循环终止条件 — requirements-elicitation/spec-challenge/cross-review
- [ ] H-4 状态检查点 — systematic-debugging/tdd/domain-collab
- [ ] H-5 知识文件健壮性 — 存在性检查 + 降级标注
- [ ] H-6 impl-verify 矛盾修复

### Session 3-b: E (Context 管理) — branch: `wave3/context-mgmt`
- [ ] E-1 主动压缩建议 — tool-call 计数器
- [ ] E-2 工作模式声明 — session-state current_mode 字段
- [ ] E-3 Marker-Based 幂等更新 — session-state.md marker 机制

### Session 3-c: C-2~5 (安全剩余) — branch: `wave3/security`
- [ ] C-2 敏感数据扫描
- [ ] C-3 Bash 命令预检
- [ ] C-4 Fact-Forcing Gate
- [ ] C-5 治理审计与成本追踪

**Wave 3 merge checklist:**
- [ ] 三个分支依次 merge 无冲突
- [ ] `make lint` 通过
- [ ] `make test-hook` 通过
- [ ] `make eval-quick` 通过（SKILL.md 改动后必须）

---

## Wave 4 — 增值层

### Session 4-a: D (持续学习) — branch: `wave4/learning`
- [ ] D-1 Phase 3 校准持久化
- [ ] D-2 Instinct 注入框架
- [ ] D-3 文件产出隔离

### Session 4-b: I 剩余 — branch: `wave4/test-notify`
- [ ] I-2 测试覆盖扩展 — domain-collab/tdd/impl-verify eval
- [ ] I-4 桌面通知
- [ ] H-7 语言硬编码清理

**Wave 4 merge checklist:**
- [ ] 两个分支 merge 无冲突
- [ ] `make all` 通过（完整测试）
- [ ] 版本号更新
