---
name: impl-orchestration
description: Use when executing implementation plans with independent tasks. Risk-aware subagent dispatch with per-task review.
---

# Implementation Orchestration

Execute plan by dispatching fresh subagent per task, with risk-aware review gates after each.

**Why subagents:** Delegate tasks to specialized agents with isolated context. Precisely craft their instructions — they never inherit your session context. This preserves your context for coordination work.

**Core principle:** Fresh subagent per task + risk-aware review = high quality, fast iteration.

**Announce at start:** "Using ecw:impl-orchestration to execute the plan task-by-task."

## When to Use

Use when:
- You have an implementation plan (from `ecw:writing-plans`)
- Tasks are mostly independent
- `session-state.md` `实现策略` = `subagent-driven`, OR Task count x risk level matches subagent-driven criteria per risk-classifier

Don't use when:
- No plan exists (write one first)
- Tasks are tightly coupled (implement directly)
- P2 / P3 / simple changes (implement directly)

## Risk-Aware Review Depth

Read `.claude/ecw/session-state.md` for risk level. If unavailable, use AskUserQuestion to ask the user for risk level (P0 or P1).

| Risk Level | Per-task Spec Review | Per-task Code Quality Review | Post-impl |
|-----------|---------------------|----------------------------|-----------|
| **P0** | Mandatory | Mandatory (simplified inline) | ecw:impl-verify (full 4 Rounds) |
| **P1** | Mandatory | **Skip** (impl-verify Round 4 covers this) | ecw:impl-verify (full 4 Rounds) |
| **P2** | Not applicable (P2 doesn't use orchestration) | — | ecw:impl-verify |

**Why P0 keeps code quality review:** Error cost at P0 is extreme. Catching issues per-task is cheaper than finding them across the full implementation.

**Why P1 skips code quality review:** impl-verify Round 4 (engineering standards) provides the same checks with full implementation context, avoiding duplicate work.

## The Process

```dot
digraph process {
    rankdir=TB;

    subgraph cluster_per_task {
        label="Per Task Cycle";
        dispatch [label="Dispatch implementer\n(./implementer-prompt.md)"];
        questions [label="Implementer asks\nquestions?" shape=diamond];
        answer [label="Answer, provide context"];
        implement [label="Implementer: implement,\ntest, commit, self-review"];
        spec_review [label="Dispatch spec reviewer\n(./spec-reviewer-prompt.md)"];
        spec_ok [label="Spec compliant?" shape=diamond];
        spec_fix [label="Implementer fixes\nspec gaps"];
        code_review [label="P0: Code quality\nreview (inline prompt)"];
        code_ok [label="Quality approved?" shape=diamond];
        code_fix [label="Implementer fixes\nquality issues"];
        mark_done [label="Mark task complete\n+ update Subagent Ledger"];
    }

    init [label="Read plan, extract tasks,\ncreate TaskCreate list"];
    more [label="More tasks?" shape=diamond];
    impl_verify [label="Invoke ecw:impl-verify"];

    init -> dispatch;
    dispatch -> questions;
    questions -> answer [label="yes"];
    answer -> dispatch;
    questions -> implement [label="no"];
    implement -> spec_review;
    spec_review -> spec_ok;
    spec_ok -> spec_fix [label="no"];
    spec_fix -> spec_review [label="re-review"];
    spec_ok -> code_review [label="yes\n(P0 only)"];
    spec_ok -> mark_done [label="yes\n(P1: skip)"];
    code_review -> code_ok;
    code_ok -> code_fix [label="no"];
    code_fix -> code_review [label="re-review"];
    code_ok -> mark_done [label="yes"];
    mark_done -> more;
    more -> dispatch [label="yes"];
    more -> impl_verify [label="no"];
}
```

## Setup

1. **Read plan file once** — extract all tasks with full text
2. **Create TaskCreate list** — one Task per plan task, with dependency chain
3. **Note context** — architectural decisions, domain constraints, file structure

## Per-Task Cycle

### 1. Dispatch Implementer

Use `agents/implementer.md` prompt template. Inject:
- Full task text (don't make subagent read plan file)
- Scene-setting context (where this fits, dependencies)
- ECW domain context (domain name, knowledge file paths, risk level)
- TDD requirement (if `tdd.enabled` in ecw.yml)
- Working directory

Use Agent tool with `subagent_type: "general-purpose"`.

**Model selection:**

| Task Type | Model | Criteria |
|-----------|-------|----------|
| Mechanical tasks | `model: "haiku"` | 1-2 files, clear spec, no conditional branching (enum/constant definitions, DTO fields, config changes) |
| Integration/design tasks | `model: "sonnet"` | Multi-file coordination, judgment needed, business logic |
| Architecture tasks | `model: "opus"` | Cross-module structural decisions, complex state machines, deep reasoning required |

Default to `model: "sonnet"` when classification is ambiguous.

### 2. Handle Implementer Status

**DONE:** Proceed to spec review.

**DONE_WITH_CONCERNS:** Read concerns. If about correctness/scope, address before review. If observations, note and proceed.

**NEEDS_CONTEXT:** Provide missing context and re-dispatch.

**BLOCKED:** Assess:
1. Context problem → provide more context, re-dispatch
2. Task too hard → re-dispatch with more capable model
3. Task too large → break into smaller pieces
4. Plan wrong → use AskUserQuestion to discuss with user

**Re-dispatch limit**: Same task can be re-dispatched at most **2 times** after BLOCKED. If still BLOCKED after 2 re-dispatches, escalate to user via AskUserQuestion with full context of what was tried.

**Never** ignore escalation or force same model to retry without changes.

### 3. Spec Compliance Review

Use `agents/spec-reviewer.md` prompt template. Inject:
- Full task requirements
- Implementer's report

**Model selection**: `model: "sonnet"` (spec compliance review requires understanding requirements and comparing against code — pattern-matching, not creative reasoning).

The reviewer reads actual code and verifies:
- Missing requirements
- Extra/unneeded work
- Misunderstandings

If issues found → implementer fixes → re-review. Repeat until approved (max 3 rounds — see Loop Safety Controls).

### 4. Code Quality Review (P0 Only)

For P0 risk level, after spec compliance passes, dispatch a code quality review (`model: "sonnet"` — quality review is pattern-matching against engineering standards):

```
Agent(description: "Code quality review for Task N"):
  Review the implementation for Task N.

  Files changed: [list from implementer report]

  Check:
  - Each file has one clear responsibility
  - Units decomposed for independent testing
  - Following file structure from plan
  - Clean, maintainable code
  - Names clear and accurate
  - No overbuilding (YAGNI)
  - Tests verify behavior (not mock behavior)

  Report: Strengths, Issues (Critical/Important/Minor), Assessment (Approved/Needs Fix)
```

If issues found → implementer fixes → re-review (max 2 rounds — see Loop Safety Controls).

### 5. Complete Task

- Mark task complete in TaskUpdate
- Update Subagent Ledger in `session-state.md` (P0 记录全部三行；P1 仅记录 implementer + spec-reviewer，跳过 code-quality)：

```markdown
| {task_name} | implementer | {model} | — |
| {task_name} | spec-reviewer | {model} | — |
| {task_name} | code-quality | {model} | — |  ← P0 only
```

## Loop Safety Controls

Guard against infinite loops and runaway subagent costs.

### Per-Task Iteration Limits

| Review Type | Max Rounds | On Limit Reached |
|-------------|-----------|-----------------|
| Spec compliance review | **3** | Escalate to user: list unresolved spec gaps, ask whether to accept, adjust plan, or abort task |
| Code quality review (P0) | **2** | Escalate to user: list remaining quality issues, ask whether to accept or defer to impl-verify |
| BLOCKED re-dispatch | **2** | Escalate to user: provide full blocked context, ask for guidance |
| NEEDS_CONTEXT re-dispatch | **3** | Escalate to user: the task may be under-specified in the plan |

### Global Budget

**Total subagent dispatches across all tasks: maximum 30.** Count every Agent tool call (implementer, spec-reviewer, code-quality, re-dispatch). When approaching the limit (≥ 25), warn user: "Approaching global dispatch budget ({N}/30). {M} tasks remaining."

If budget exhausted before all tasks complete, escalate to user with options:
1. "Extend budget" — continue with +10 dispatches
2. "Switch to direct implementation" — complete remaining tasks without subagents
3. "Stop here" — mark remaining tasks as pending for next session

### Repeated Error Detection

Track spec review failure reasons per task. If the **same spec gap** (matching description) appears in 2 consecutive review rounds after implementer claims to have fixed it:

1. **Pause** the review loop
2. **Report** to user: "Task {N} spec review found the same issue ({description}) in 2 consecutive rounds after fix attempts."
3. **Ask** via AskUserQuestion:
   - "Re-dispatch with more capable model" — upgrade model tier
   - "Provide additional context" — user adds clarification
   - "Skip this check" — accept the current implementation with a note

### Stall Detection

If a single task consumes **≥ 6 subagent dispatches** (implementation + reviews + re-dispatches combined), pause and escalate:

"Task {N} has consumed {count} dispatches without completing. This suggests the task may be too complex or the plan may need revision."

## After All Tasks

**Do NOT dispatch a final code reviewer.** ECW uses `ecw:impl-verify` (4-Round multi-dimensional verification) which is more comprehensive.

1. Invoke `ecw:impl-verify` — this is the post-implementation quality gate
2. impl-verify handles: requirements alignment, domain rule compliance, plan consistency, engineering standards

## Never Rules

- Start implementation on main/master without explicit user consent
- Skip spec compliance review
- Proceed with unfixed spec issues
- Dispatch multiple implementation subagents in parallel (conflicts)
- Make subagent read plan file (provide full text)
- Skip scene-setting context
- Ignore subagent questions
- Accept "close enough" on spec compliance
- Skip review loops (issues found = fix = re-review)
- Let self-review replace actual review (both needed)
- **Start code quality review before spec compliance passes** (wrong order)
- Move to next task while review has open issues

## Task Merging

If plan has many small tasks, consider merging per risk-classifier rules:
- Single-file + no conditional branch logic = can merge
- State machine / cross-domain / multi-file = must stay independent

Reference risk-classifier "实现策略选择" section for authoritative rules. Do not redefine here.
