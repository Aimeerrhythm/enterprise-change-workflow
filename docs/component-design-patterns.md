# ECW 核心组件设计模式

本文档记录 ECW 各核心组件在演进过程中沉淀出的设计模式和工程约束。每个模式都源自真实的失败案例或架构决策。

---

## 1. Hook 生命周期模型

ECW 使用 Claude Code 的 PreToolUse / PostToolUse hook 机制实现确定性流程控制。

### 时序

```
用户请求 → LLM 决定调用 Skill
            ↓
     ┌─── PreToolUse ───┐
     │ 1. 写入 in-progress state     │
     │ 2. 计算 next skill             │
     │ 3. 注入只读上下文 (systemMessage) │
     │ 4. 注入 instincts (if any)     │
     └──────────────────────────────┘
            ↓
     Skill 执行（LLM 读取 SKILL.md 并执行业务逻辑）
            ↓
     ┌─── PostToolUse ──┐
     │ 1. 写入 completed state        │
     │ 2. 计算 remaining route        │
     │ 3. 注入 auto-continue 指令     │
     └──────────────────────────────┘
            ↓
     LLM 看到 systemMessage → 立即调用下一个 Skill
```

### 设计约束

| 约束 | 原因 |
|------|------|
| Hook 永远不返回 `{"result": "block"}` | 阻断 skill 调用会破坏用户体验且不可恢复 |
| Hook 异常必须静默吞掉 | `except: pass` — 宁可状态不更新也不能阻塞工作流 |
| PreToolUse 不注入 "do not ask" | 某些 Skill（spec-challenge）有 mandatory 用户确认流 |
| PostToolUse 是唯一路由决策点 | Skill 本身不做"下一步去哪"的决策 |

### 反模式

- ❌ Skill 中写 `current_phase` / `next` / `working_mode`（状态所有权反转原则）
- ❌ Hook 中硬编码 skill 映射表（应从 routes.yml 动态加载）
- ❌ PreToolUse 和 PostToolUse 都写同一个字段（竞争导致状态不一致）

---

## 2. Marker-Based Idempotent Section Updates

`marker_utils.py` 的核心设计：用 HTML 注释 marker 将文件划分为独立可寻址的 section。

### 格式

```markdown
<!-- ECW:STATUS:START -->
risk_level: P0
auto_continue: true
routing: [writing-plans, spec-challenge, impl-verify]
<!-- ECW:STATUS:END -->
```

### 为什么不用整文件覆盖

session-state.md 由多个 Hook 分别管理不同 section（STATUS、MODE、LEDGER、TIMELINE、STOP）。整文件覆盖 = 多写入者竞争 = 数据丢失。Marker 机制让每个写入者只修改自己的 section，其余保持不变。

### API 设计

```python
# 读：精确提取
parse_status(content) → dict        # STATUS section as YAML
read_marker_section(content, name) → str  # raw section content

# 写：原子替换
update_status_fields(content, {"current_phase": "plan-loaded"}) → content
update_yaml_section(content, "LEDGER", data) → content

# 创建/追加
append_ledger_entry(content, entry) → content  # 在 END marker 之前插入
append_timeline_entry(content, phase) → content  # 自动回填上条 duration
```

### 设计约束

| 约束 | 原因 |
|------|------|
| YAML 格式（非 Markdown） | LLM 容易生成有效 YAML；程序可精确解析 |
| 新增 section 自动 append 到文件尾 | 向前兼容——旧文件不含新 section 时自动创建 |
| `append_ledger_entry` 是唯一入口 | 禁止 LLM 直接 `Edit` 追加到文件尾（会写到 END marker 之外） |

### 失败案例

- Issue #36: LLM 把 Ledger 写到 `<!-- ECW:LEDGER:END -->` 之后 → 所有 hook parser 读不到
- Issue #33: LLM 写 `phase1-complete` vs Hook 写 `phase1-loaded` → 同字段双写冲突
- Issue #40: 从 Markdown 迁移到 YAML 格式，需要同步改 10+ SKILL.md 中的格式描述

**根治方案**: State Ownership Inversion — Skill 不写 state，只有一个写入者。

---

## 3. 声明式路由配置

`workflow-routes.yml` 是整个 ECW 路由系统的 Single Source of Truth。

### 设计哲学

路由规则是**治理产物**（由组织决定 P0 变更必须走什么流程），不是**技术实现细节**。它应该以非技术人员可读的声明式格式存在，而不是散落在 Python 代码的 if-else 分支中。

### 文件结构

```yaml
routes:         # 路由矩阵（level × mode × type → chain）
skill_metadata: # 每个 Skill 的元数据（mode, phase_name, aliases）
off_chain_skills: # 手动工具白名单
impl_strategy:  # 实现策略决策规则
post_impl_tasks: # 后续任务创建规则
```

### 动态加载模式

```python
# 启动时解析 routes.yml → 生成 5 张映射表
_mappings = _load_routes_from_file()
_SKILL_COMPLETED_PHASE = _mappings["completed_phase"]
_SKILL_MODE = _mappings["mode"]
_SKILL_ROUTING_ALIASES = _mappings["routing_aliases"]
_ROUTING_STEP_TO_SKILL = _mappings["step_to_skill"]
_OFF_CHAIN_ALLOWED = _mappings["off_chain"]
```

### 验证方式

- `test_data_contracts.py`: 验证所有 route chain 中的 skill 都存在对应目录
- `test_workflow_simulator.py`: 模拟完整 trace，验证 must_include / must_exclude
- `test_dynamic_routes.py`: 验证动态加载正确性和行为保持

### 新增 Skill 的流程

1. 创建 `skills/{name}/SKILL.md`
2. 在 `workflow-routes.yml` 的 `skill_metadata` 添加 mode + phase_name
3. 如有路由别名（如 TDD:RED → ecw:tdd），添加 `routing_aliases`
4. 在 `routes` 中将其加入对应 chain
5. **不需要改任何 Python 代码**

---

## 4. 只读上下文注入模式

Skill 需要感知当前工作流状态（做决策用），但不应修改状态（避免双写）。

### 解法

PreToolUse hook 在 Skill 加载时注入一条 `systemMessage`：

```
[ECW STATE — read-only] risk=P0, mode=planning, next=ecw:tdd, remaining=TDD:RED → impl-verify
```

Skill 读到这条消息后知道当前上下文，但没有任何"请你写入 X"的指令。

### 设计要点

| 要点 | 说明 |
|------|------|
| 前缀 `[ECW STATE — read-only]` | 明确告诉 LLM 这是只读信息，不是待执行指令 |
| 紧凑格式（一行） | 最小化 token 占用——每个 Skill 调用都会注入 |
| 与 instincts 合并 | 同一条 systemMessage 包含状态 + 历史校准，减少注入次数 |
| 无状态时不注入 | 新 session 首次调用 risk-classifier 时无 session-state → 不注入 |

---

## 5. Instincts（学习型规则）设计

Phase 3 Calibration 产出的 heuristic rules，存储在 `instincts.md`，通过 PreToolUse 注入对应 Skill。

### 架构位置

```
Phase 3 产出 → instincts.md → parse_instincts() → PreToolUse 注入 → 影响 Skill 决策
```

### 设计约束

| 约束 | 原因 |
|------|------|
| 按 skill section 分割 | 不同 Skill 的校准数据不应互相干扰 |
| session-start 只注入高置信度（≥ 0.7） | 低置信度 instinct 可能误导 |
| auto-continue 注入全部（无 confidence 过滤） | per-skill 注入已经做了精确路由 |
| 统一解析函数 `parse_instincts()` | 避免两处实现漂移（Issue #62 修复） |

### 格式

```markdown
## risk-classifier

<!-- INSTINCT -->
- **Pattern**: 涉及状态机的变更被低估
- **Action**: 有状态流转关键词时 +1 级
- **Confidence**: 0.85
- **Source**: 20260501-a3f1 calibration
```

---

## 6. Checkpoint Store 设计

`CheckpointStore` 类提供 session-data checkpoint 文件的统一 CRUD。

### 为什么需要抽象

ECW 有 15+ 种 checkpoint 文件（session-state, domain-collab-report, phase2-assessment, impl-verify-findings...）。每个 Hook/Skill 都需要：
- 找到当前 workflow 的目录
- 检查文件存在性
- 读写文件

没有抽象 = 每处都重复目录拼接 + 错误处理逻辑。

### API

```python
store = CheckpointStore.from_latest_workflow(cwd)  # 找最新 workflow
store.write("phase2-assessment", content)           # 创建目录 + 写入
content = store.read("knowledge-summary")           # None if missing
store.exists("impl-verify-findings")                # bool
store.list()                                        # ["session-state", ...]
```

### 设计要点

- **workflow-id 隔离**: 每个 workflow 有独立子目录（`{YYYYMMDD}-{xxxx}`），避免覆盖
- **from_latest_workflow()**: 自动找最新目录，Hook 不需要知道具体 workflow-id
- **创建目录 on write**: `write()` 内部 `os.makedirs(exist_ok=True)`，调用方无需关心

---

## 7. 错误处理哲学

ECW hook 系统的错误处理遵循一个核心原则：**Hook 故障永不阻塞工作流。**

### 分层策略

| 层级 | 错误处理 | 原因 |
|------|---------|------|
| Hook 顶层 | `except: pass` + `{"result": "continue"}` | 用户操作不应因 hook bug 而失败 |
| 状态写入 | `try/except` 包裹，失败 = 状态过期但流程继续 | 过期状态比阻塞工作流的代价低 |
| 配置读取 | fallback default（如 risk_level 缺失 → 默认 P0） | 安全侧兜底 |
| 文件解析 | YAML 解析失败 → 返回 None → 调用方判断 | 不传播异常到上游 |

### 反模式

- ❌ Hook 中 `raise` 导致 Claude Code 报错
- ❌ `sys.exit(1)` 终止进程
- ❌ 重试循环（Hook 执行有隐式时限，重试可能超时）

### 日志而非断言

用 `log_trace()` 记录异常状态用于事后诊断，不用 `assert` 在运行时中断。`trace.jsonl` 是回顾工具，不是实时监控。

---

## 8. 文档加载体系设计

Claude Code 的 context window 是稀缺资源。每个 session 自动加载的文档**直接占用推理预算**——多一行无用信息 = 少一行有效推理空间。

### 三原则

| 原则 | 含义 | 违反时的表现 |
|------|------|-------------|
| **精简** | 每个 token 都必须对 session 内的决策有贡献 | 文档越写越长，但模型行为没有因此变好 |
| **按需加载** | 只在需要时才进入上下文，不需要时零开销 | 低频参考信息占据每个 session 的固定 token |
| **有效** | 加载的内容必须能直接影响模型行为（约束/规则/上下文） | 文档存在但模型表现得像没读过一样 |

### 文档分层架构

```
Layer 0: 每 session 自动加载（CLAUDE.md + Memory index）
  → 只放"违反就出错"的硬性规则
  → 目标: < 2000 tokens

Layer 1: 动态注入（session-start hook）
  → 只在有活跃工作流时注入相关状态
  → 条件触发，无工作流时零开销

Layer 2: 按需读取（docs/、templates/、prompts/）
  → CLAUDE.md 提供指引（"实现前读 X"），但不内联全文
  → 模型在需要时通过 Read tool 自行获取

Layer 3: 被动存档（CHANGELOG、理论反思文档）
  → 不引用、不加载、不影响行为
  → 仅供人类审阅或历史考古
```

### CLAUDE.md 内容准入标准

一段内容要进入 CLAUDE.md（Layer 0），必须同时满足：

1. **高频** — 超过 50% 的 session 需要参考它
2. **行为约束** — 它是规则/约束/流程，不是知识/参考/背景
3. **不可推导** — 不能通过阅读代码或现有文件推导出来

| 适合 CLAUDE.md | 不适合 CLAUDE.md |
|---------------|-----------------|
| "Skills 不写状态" | 15 个 skill 的逐条描述（代码里有 frontmatter） |
| "impl-verify 在标记完成前执行" | 25 个 artifact 文件的完整路径表（低频查询） |
| "workflow-routes.yml 是路由唯一来源" | 每个 skill 的触发条件表（hook 自动处理） |

### Memory 文件准入标准

一条 memory 值得存在，必须满足：

1. **未来有行动价值** — 不是"已完成的记录"，而是"下次遇到时要遵循的规则"
2. **不可从代码/文档推导** — 如果 `docs/design-principles.md` 已经写了同样的内容，memory 就是冗余副本
3. **不会自然过期** — project 类 memory 有保质期，完成后应清理

### 反模式

| 反模式 | 后果 | 修正 |
|--------|------|------|
| 把完整表格放 CLAUDE.md | 每 session 多 1000+ tokens，99% 用不上 | 外置到 docs/，CLAUDE.md 只留一行链接 |
| Memory 记录"做了什么" | 变成历史日志，越积越多但无行动价值 | 只记"下次怎么做"，完成的及时清理 |
| CLAUDE.md 复述 SKILL.md 内容 | 两处维护，必然漂移 | CLAUDE.md 只说"存在某规则"，不重复规则内容 |
| 所有文档平铺在 CLAUDE.md | 无法区分"必须遵守"vs"按需参考" | 严格分层：Layer 0 只放硬性规则 |
| "以防万一"多加几行 | 积少成多，半年后 CLAUDE.md 膨胀到 5000+ tokens | 定期审查：每行问"删掉它模型会出错吗？"不会就删 |

### 定期审查机制

每 5 个版本（或每月）执行一次文档审查：

1. `wc -c CLAUDE.md` — 超过 8000 chars（~2000 tokens）就需要瘦身
2. 逐条 Memory 问："这条删了，下次 session 会犯错吗？"
3. CLAUDE.md 每个 section 问："过去 10 个 session 有几个用到了？"低于 30% 就外置
4. 检查 docs/ 下是否有"应该加载但没被 CLAUDE.md 引用"的孤岛文档

