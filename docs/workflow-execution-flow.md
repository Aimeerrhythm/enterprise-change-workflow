# ECW 执行流程详解

## 总览

ECW 根据 risk-classifier 输出的风险等级（P0~P3）驱动不同深度的变更管理流程。本文档以 **P0 流程**为主线，详细描述每个阶段的输入、输出、决策点和串联机制。

---

## 1. 风险等级路由总览

```mermaid
flowchart TD
    REQ[用户输入需求] --> RC[risk-classifier Phase 1]
    RC --> |P0/P1 单域| RE[requirements-elicitation]
    RC --> |P0/P1 跨域| DC[domain-collab]
    RC --> |P2| WP2[writing-plans]
    RC --> |P3| IMPL3[直接实现]
    RC --> |Bug| SD[systematic-debugging]

    RE --> PH2A[Phase 2 精确评估]
    DC --> PH2B[Phase 2 精确评估]
    PH2A --> WP[writing-plans]
    PH2B --> WP

    WP --> |P0 必须 / P1 跨域| SC[spec-challenge]
    WP --> |P1 单域 / P2| TDD
    SC --> TDD[TDD: RED]
    TDD --> GREEN[Implementation: GREEN]
    GREEN --> IV[impl-verify]
    IV --> |P0/P1| BIA[biz-impact-analysis]
    BIA --> KT[knowledge-track]
    KT --> CAL[Phase 3 Calibration]
    IV --> |P2| DONE2[✅ 完成]
    CAL --> DONE[✅ 完成]

    WP2 --> TDD2[TDD: RED] --> GREEN2[Implementation] --> IV2[impl-verify] --> DONE2

    style RC fill:#e74c3c,color:#fff
    style SC fill:#e67e22,color:#fff
    style IV fill:#2ecc71,color:#fff
    style DONE fill:#27ae60,color:#fff
    style DONE2 fill:#27ae60,color:#fff
```

### 各等级路由对比

| 阶段 | P0 | P1 | P2 | P3 |
|------|----|----|----|----|
| 需求分析 | requirements-elicitation / domain-collab | 同 P0 | 跳过 | 跳过 |
| Phase 2 精确评估 | ✅ | ✅ | 跳过 | 跳过 |
| writing-plans | 完整 + 验证 + 回滚 | 完整 + 验证 | 简化 | 跳过 |
| spec-challenge | **必须** | 仅跨域 | 跳过 | 跳过 |
| TDD | 强制 + 验证日志 | 强制 | 简化模式 | 跳过 |
| impl-orchestration | Task≥4 强制 | Task≥4 强制 | 跳过 | 跳过 |
| impl-verify | 4 轮全量 | 4 轮全量 | 简化 | 跳过 |
| biz-impact-analysis | ✅ | ✅ | 跳过 | 跳过 |
| Phase 3 校准 | ✅ | ✅ | 跳过 | 跳过 |

---

## 2. P0 单域完整流程

```mermaid
flowchart TD
    START([用户输入需求]) --> PHASE1

    subgraph PHASE1 [① risk-classifier Phase 1]
        P1A[关键词匹配 → 初判 P0] --> P1B[创建 session-state.md]
        P1B --> P1C[写入 Auto-Continue 路由链]
        P1C --> P1D[创建 post-impl Tasks:<br/>Task#3 impl-verify<br/>Task#4 biz-impact-analysis<br/>Task#5 Phase 3 Calibration]
        P1D --> P1E{👤 用户确认<br/>P0 等级是否准确?}
    end

    P1E --> |确认| REQE

    subgraph REQE [② requirements-elicitation]
        R1[9 维系统提问] --> R2{👤 多轮交互<br/>需求是否充分?}
        R2 --> |补充| R1
        R2 --> |充分| R3[dispatch Sonnet 综合分析]
        R3 --> R4[输出 requirements-summary.md]
    end

    R4 --> PHASE2

    subgraph PHASE2 [③ risk-classifier Phase 2]
        P2A[dispatch Sonnet 查询依赖图] --> P2B[结合代码分析]
        P2B --> P2C[精确等级判定]
        P2C --> P2D{升降级?}
        P2D --> |降级| P2E[调整路由链]
        P2D --> |维持 P0| P2F[输出 phase2-assessment.md]
        P2E --> P2F
        P2F --> P2G{👤 用户确认<br/>等级 + 结论}
    end

    P2G --> |确认| WP

    subgraph WP [④ writing-plans]
        W1[P0 细度: 完整任务分解<br/>+ 验证步骤 + 回滚说明]
        W1 --> W2{≥2域 或<br/>知识文件≥3?}
        W2 --> |Yes| W3[dispatch Opus 子代理]
        W2 --> |No| W4[直接模式编写]
        W3 --> W5[输出 Plan 文件]
        W4 --> W5
        W5 --> W6{评估实现策略}
        W6 --> |Task≤3 文件≤5| STRATEGY_DIRECT[标记: direct]
        W6 --> |Task 4-8 P0| STRATEGY_ORCH[标记: impl-orchestration]
        W6 --> |Task>8| STRATEGY_ORCH
    end

    STRATEGY_DIRECT --> SPEC
    STRATEGY_ORCH --> SPEC

    subgraph SPEC [⑤ spec-challenge ★ P0 必须]
        S1[dispatch Opus 独立审查 Plan] --> S2[返回 Fatal + Improvement]
        S2 --> S3{👤 对每个 Fatal 项}
        S3 --> |同意修改| S4[执行修改]
        S3 --> |反对| S5[记录理由, 跳过]
        S3 --> |讨论| S6[限 3 轮讨论]
        S6 --> S3
        S4 --> S7[Improvement 项批量多选]
        S5 --> S7
        S7 --> S8[更新 Plan + 输出报告]
        S8 --> S9{👤 确认修改后 Plan}
    end

    S9 --> |确认| TDDP

    subgraph TDDP [⑥ TDD: RED]
        T1[根据 Plan 每个 Task 编写测试] --> T2[执行测试 → 全部 RED]
        T2 --> T3[记录测试输出日志]
    end

    T3 --> IMPLP

    subgraph IMPLP [⑦ Implementation: GREEN]
        I0{实现策略?}
        I0 --> |direct| I1[逐 Task 实现 → 测试变绿]
        I0 --> |orchestration| I2[构建 Task 依赖图]
        I2 --> I3[分层并行 dispatch<br/>最多 3 并发]
        I3 --> I4[P0 每 Task 强制:<br/>spec 评审 + 代码质量评审]
        I4 --> I5[合并 + 冲突解决]
        I1 --> I6[RED→GREEN→Refactor 循环]
        I5 --> I6
    end

    I6 --> VERIFY

    subgraph VERIFY [⑧ impl-verify — 4 轮并行]
        V1[并行 dispatch 4 个 Sonnet 子代理]
        V1 --> V2[Round 1: 需求↔代码追踪]
        V1 --> V3[Round 2: 域知识约束对齐]
        V1 --> V4[Round 3: Plan 决策验证]
        V1 --> V5[Round 4: 工程标准评审]
        V2 --> V6[Coordinator 汇总]
        V3 --> V6
        V4 --> V6
        V5 --> V6
        V6 --> V7{must-fix > 0?}
        V7 --> |Yes| V8[修复 + 重新验证<br/>最多 5 轮]
        V8 --> V6
        V7 --> |No| V9[✅ 验证通过]
    end

    V9 --> BIA

    subgraph BIA [⑨ biz-impact-analysis]
        B1[dispatch Opus 子代理] --> B2[输入: git diff]
        B2 --> B3[分析业务流程 / 外部系统 / e2e 路径]
        B3 --> B4{发现未注册<br/>跨域调用?}
        B4 --> |Yes| B5[自动回填 cross-domain-calls.md]
        B4 --> |No| B6[输出业务影响报告]
        B5 --> B6
    end

    B6 --> KT

    subgraph KT [⑩ knowledge-track]
        K1[追踪知识利用: hit/miss/redundant/misleading]
        K1 --> K2[输出 doc-tracker.md]
    end

    K2 --> CAL

    subgraph CAL [⑪ Phase 3 Calibration]
        C1[对比 Phase 1/2 预测 vs 实际] --> C2[输出 calibration-log.md]
        C2 --> C3[输出 calibration-history.md]
        C3 --> C4[输出 instincts.md<br/>置信度 > 0.7]
    end

    CAL --> FINISH([✅ P0 流程完成])

    style PHASE1 fill:#ffeaa7
    style REQE fill:#dfe6e9
    style PHASE2 fill:#ffeaa7
    style WP fill:#74b9ff
    style SPEC fill:#e17055,color:#fff
    style TDDP fill:#a29bfe
    style IMPLP fill:#6c5ce7,color:#fff
    style VERIFY fill:#00b894,color:#fff
    style BIA fill:#fdcb6e
    style KT fill:#dfe6e9
    style CAL fill:#b2bec3
```

---

## 3. P0 跨域流程差异

跨域 P0 在需求分析阶段使用 **domain-collab** 替代 requirements-elicitation，其余阶段相同。

```mermaid
flowchart TD
    START([用户输入跨域需求]) --> PHASE1[① risk-classifier Phase 1<br/>判定: P0 跨域]
    PHASE1 --> DC

    subgraph DC [② domain-collab — 替代 requirements-elicitation]
        DC1[Round 1: 并行 dispatch<br/>多个 domain-analyst] --> DC2[各域返回 YAML 分析]
        DC2 --> DC3[Round 2: dispatch<br/>domain-negotiator<br/>跨域协商]
        DC3 --> DC4[Round 3: Coordinator<br/>交叉验证]
        DC4 --> DC5[输出 domain-collab-report.md<br/>+ knowledge-summary.md]
    end

    DC5 --> PHASE2[③ Phase 2 精确评估]
    PHASE2 --> NEXT[④~⑪ 后续流程同单域 P0]

    style DC fill:#fd79a8,color:#fff
```

### domain-collab 三轮流程

```mermaid
sequenceDiagram
    participant C as Coordinator
    participant DA1 as Domain Analyst A
    participant DA2 as Domain Analyst B
    participant DA3 as Domain Analyst C
    participant DN as Domain Negotiator

    Note over C: Round 1 — 并行域分析
    C->>+DA1: 分析需求对域 A 的影响
    C->>+DA2: 分析需求对域 B 的影响
    C->>+DA3: 分析需求对域 C 的影响
    DA1-->>-C: YAML: 变更点 + 依赖 + 风险
    DA2-->>-C: YAML: 变更点 + 依赖 + 风险
    DA3-->>-C: YAML: 变更点 + 依赖 + 风险

    Note over C: Round 2 — 跨域协商
    C->>+DN: 各域分析结果 + 冲突点
    DN-->>-C: 协商方案 + 接口契约

    Note over C: Round 3 — 交叉验证
    C->>C: 验证一致性 + 缺口检测
    C->>C: 输出 domain-collab-report.md
```

---

## 4. auto-continue 串联机制

```mermaid
sequenceDiagram
    participant SK as Skill 执行
    participant HK as auto-continue Hook
    participant SS as session-state.md
    participant NX as 下一个 Skill

    SK->>HK: PostToolUse 触发
    HK->>SS: 原子更新 Current Phase → "已完成"
    HK->>SS: 更新 Working Mode
    HK->>SS: 记录 Subagent Ledger (时间戳+耗时)
    HK->>SS: 读取 Auto-Continue 路由链
    HK->>HK: 查找下一个未完成 step
    HK->>NX: 注入 systemMessage<br/>"接下来执行 ecw:xxx"
    NX->>HK: PreToolUse 触发
    HK->>SS: 更新 Current Phase → "进行中"
    NX->>NX: Skill 开始执行
```

### session-state.md 关键字段

```yaml
# Auto-Continue 路由链示例 (P0 单域)
Auto-Continue:
  - requirements-elicitation    # ✅ 已完成
  - Phase 2                     # ✅ 已完成
  - writing-plans               # 🔄 进行中
  - spec-challenge              # ⏳ 待执行
  - TDD:RED                     # ⏳ 待执行
  - Implementation:GREEN        # ⏳ 待执行
  - impl-verify                 # ⏳ 待执行
  - biz-impact-analysis         # ⏳ 待执行
  - Phase 3 Calibration         # ⏳ 待执行

Current Phase: writing-plans (进行中)
Working Mode: plan-generation
Next: spec-challenge
```

---

## 5. impl-verify 4 轮验证详解

```mermaid
flowchart LR
    subgraph DISPATCH [并行 Dispatch]
        R1[Round 1<br/>需求↔代码<br/>双向追踪]
        R2[Round 2<br/>域知识<br/>约束对齐]
        R3[Round 3<br/>Plan 决策<br/>验证]
        R4[Round 4<br/>工程标准<br/>质量评审]
    end

    R1 --> COORD[Coordinator<br/>汇总 YAML]
    R2 --> COORD
    R3 --> COORD
    R4 --> COORD

    COORD --> CHECK{must-fix<br/>数量?}
    CHECK --> |> 0| FIX[修复问题]
    FIX --> DISPATCH
    CHECK --> |= 0| PASS[✅ 验证通过]
    CHECK --> |停滞检测<br/>超 5 轮| ESCALATE[⚠️ 升级处理]

    style R1 fill:#74b9ff
    style R2 fill:#a29bfe
    style R3 fill:#fd79a8
    style R4 fill:#ffeaa7
    style PASS fill:#00b894,color:#fff
```

| 轮次 | 验证维度 | 检查内容 |
|------|---------|---------|
| Round 1 | 需求↔代码双向追踪 | 每条需求是否有对应实现；代码是否有无需求支撑的逻辑 |
| Round 2 | 域知识约束对齐 | 实现是否违反业务规则、状态机约束、数据一致性要求 |
| Round 3 | Plan 决策验证 | 代码是否偏离 Plan 中的设计决策和架构约定 |
| Round 4 | 工程标准质量评审 | 编码规范、错误处理、性能、安全、可测试性 |

---

## 6. impl-orchestration 并行编排

```mermaid
flowchart TD
    PLAN[Plan 文件] --> DEP[构建 Task 依赖图]

    DEP --> L1[Layer 1: 无依赖 Tasks]
    DEP --> L2[Layer 2: 依赖 L1 的 Tasks]
    DEP --> L3[Layer 3: 依赖 L2 的 Tasks]

    L1 --> |最多 3 并发| T1A[Task A]
    L1 --> T1B[Task B]
    L1 --> T1C[Task C]

    T1A --> REVIEW1{P0: spec 评审<br/>+ 代码质量评审}
    T1B --> REVIEW1
    T1C --> REVIEW1

    REVIEW1 --> |通过| MERGE1[合并 Layer 1]
    REVIEW1 --> |不通过| FIX1[修复]
    FIX1 --> REVIEW1

    MERGE1 --> L2
    L2 --> |并发| T2A[Task D]
    L2 --> T2B[Task E]

    T2A --> REVIEW2{评审}
    T2B --> REVIEW2
    REVIEW2 --> MERGE2[合并 Layer 2]
    MERGE2 --> L3
    L3 --> T3A[Task F]
    T3A --> REVIEW3{评审}
    REVIEW3 --> DONE([全部 Task 完成])

    style REVIEW1 fill:#e17055,color:#fff
    style REVIEW2 fill:#e17055,color:#fff
    style REVIEW3 fill:#e17055,color:#fff
```

---

## 7. 用户决策点

P0 流程中有 **5 个关键人工介入点**，流程不会全自动跑完：

```mermaid
flowchart LR
    D1[Phase 1 确认<br/>P0 等级] --> D2[需求澄清<br/>多轮交互]
    D2 --> D3[Phase 2 确认<br/>精确等级]
    D3 --> D4[spec-challenge<br/>逐项决策]
    D4 --> D5[impl-verify<br/>修复确认]

    style D1 fill:#fdcb6e
    style D2 fill:#fdcb6e
    style D3 fill:#fdcb6e
    style D4 fill:#e17055,color:#fff
    style D5 fill:#00b894,color:#fff
```

| # | 决策点 | 用户操作 | 影响 |
|---|--------|---------|------|
| 1 | Phase 1 等级确认 | 确认/调整 P0 等级 | 决定整条路由链深度 |
| 2 | 需求澄清交互 | 回答 9 维提问 | 需求完整度直接影响 Plan 质量 |
| 3 | Phase 2 等级确认 | 确认/接受升降级 | 可能改变后续路由 (如降为 P1 跳过部分步骤) |
| 4 | spec-challenge 决策 | 对每个 Fatal: 同意/反对/讨论 | Plan 修改范围 |
| 5 | impl-verify 修复 | 确认 must-fix 修复方案 | 验证收敛速度 |

---

## 8. 数据流与产出物

```mermaid
flowchart TD
    subgraph ARTIFACTS [session-data/workflow-id/]
        SS[session-state.md<br/>中枢状态]
        RS[requirements-summary.md]
        P2A[phase2-assessment.md]
        SCR[spec-challenge-report.md]
        KS[knowledge-summary.md]
        IVF[impl-verify-findings.md]
    end

    subgraph STATE [state/]
        CL[calibration-log.md]
        CH[calibration-history.md]
        INS[instincts.md]
    end

    subgraph KNOWLEDGE [knowledge-ops/]
        DT[doc-tracker.md]
        RM[repo-map.md]
    end

    PHASE1_OUT[Phase 1] --> SS
    REQ_OUT[requirements-elicitation] --> RS
    PHASE2_OUT[Phase 2] --> P2A
    SPEC_OUT[spec-challenge] --> SCR
    DC_OUT[domain-collab] --> KS
    IV_OUT[impl-verify] --> IVF
    CAL_OUT[Phase 3] --> CL
    CAL_OUT --> CH
    CAL_OUT --> INS
    KT_OUT[knowledge-track] --> DT

    style SS fill:#e74c3c,color:#fff
    style ARTIFACTS fill:#ffeaa7
    style STATE fill:#dfe6e9
    style KNOWLEDGE fill:#b2bec3
```
