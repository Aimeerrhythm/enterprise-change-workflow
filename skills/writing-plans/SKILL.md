---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code. Risk-aware planning with ECW domain context.
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for the codebase. Document everything: which files to touch, code, testing, how to verify. Give bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume the engineer is skilled but knows almost nothing about the project's toolset or problem domain.

**Announce at start:** "Using ecw:writing-plans to create the implementation plan."

**Mode switch**: Update session-state.md MODE marker to `planning`.

## Plan Mode — Do Not Use

**Do NOT call `EnterPlanMode` or `ExitPlanMode`.** This skill writes plans directly to `.claude/plans/` via the Write tool. Claude Code's built-in plan mode is a separate mechanism not used by ECW. After writing the plan file, use **AskUserQuestion** to confirm with the user (see Downstream Handoff).

## Risk-Aware Detail Level

Read `.claude/ecw/session-data/{workflow-id}/session-state.md` for risk level and affected domains. If unavailable, use AskUserQuestion.

| Risk Level | Plan Detail | Task Granularity |
|-----------|-------------|-----------------|
| **P0** | Full steps with test code + verification commands + rollback notes | 2-5 min per step, no merging |
| **P1** | Full steps with test code + verification commands | 2-5 min per step, no merging |
| **P2** | Simplified steps, can merge single-file + no-branch-logic tasks | 5-10 min per step |
| **P3** | Minimal outline (typically no formal plan needed) | — |

**Task merging rule (P2 only):** Single-file change with no conditional branch logic = can merge. State machine / cross-domain / multi-file coordination = must stay independent. Reference: risk-classifier "实现策略选择" section.

## Domain Context Injection

> **Note**: When Subagent Dispatch is active (≥ 2 domains or ≥ 3 knowledge files), these steps are executed inside the subagent, not by the coordinator. The coordinator only passes file paths.

Before writing the plan:

1. Read `.claude/ecw/ecw-path-mappings.md` to understand code path → domain mappings
2. For each affected domain, read its `business-rules.md` to understand constraints (state machines, validation rules, concurrency controls)
3. If `knowledge-summary.md` exists (from domain-collab), read it for cross-domain dependency context

> **Knowledge file robustness**: Verify each file exists before reading. If `ecw-path-mappings.md` is missing, skip domain context injection and note `[Warning: path mappings not found, plan lacks domain-aware file grouping]` in plan header. If a domain's `business-rules.md` is missing, note `[Warning: {domain} business-rules.md not found, domain constraints may be incomplete]` in the affected Tasks. Continue plan generation with available data.

Ensure design decisions respect domain rules. A plan that violates a state machine constraint or concurrency rule will fail at impl-verify.

## Subagent Dispatch Architecture

When the Plan generation workload is significant, delegate to a subagent to keep the coordinator context lean.

### Trigger Condition

Subagent dispatch activates when **either** condition is met:
- Affected domains ≥ 2 (cross-domain requirement)
- Knowledge files to read ≥ 3 (ecw-path-mappings + business-rules per domain + knowledge-summary, etc.)

When **both** conditions are false (single domain AND knowledge files < 3), use **Direct mode** — current behavior unchanged, no subagent overhead.

### Coordinator Responsibilities (lightweight)

Coordinator constructs the subagent prompt with the following inputs — **does not read knowledge file contents itself**:

1. **Requirement summary path**: `session-state.md` or `domain-collab-report.md` (subagent reads the file)
2. **Phase 2 assessment path**: `.claude/ecw/session-data/{workflow-id}/phase2-assessment.md`
3. **Knowledge file path list**:
   - `.claude/ecw/ecw-path-mappings.md`
   - `.claude/knowledge/{domain}/business-rules.md` (one per affected domain)
   - `.claude/ecw/session-data/{workflow-id}/knowledge-summary.md` (if exists)
4. **Plan output target path**: `.claude/plans/{feature}.md`
5. **Risk level + Plan detail requirements**: From `session-state.md` (P0/P1/P2 detail table in "Risk-Aware Detail Level" section)

### Subagent Responsibilities

**Source code reading limits** (prevent timeout): Read at most **10 source files** total. For each file, prefer Grep with limited context (`-A 5`) over full Read. Only Read full files for core interfaces or classes that directly participate in the change. Do NOT read complete implementations of large service classes — read class signatures and method signatures only.

The subagent executes the full Plan generation pipeline in its own context:

1. Read all knowledge files from the paths provided by coordinator
2. Execute **Domain Context Injection** (code path mappings, business rules, cross-domain dependencies)
3. Execute **Scope Check** (suggest splitting if multiple independent subsystems)
4. Execute **Design Completeness Check** (resolve open design questions via AskUserQuestion)
5. Execute **Self-Review** (spec coverage, placeholder scan, type consistency, TDD readiness)
6. Generate the complete Plan and **Write** it to `.claude/plans/{feature}.md`
7. Return to coordinator: **Plan summary (≤ 500 tokens)** containing:
   - Total Task count
   - One-sentence description per Task
   - Full list of files to create/modify
   - Implementation Strategy (direct if Tasks ≤ 3 + files ≤ 5; subagent-driven if Tasks > 8 or P0/P1 with 4+ Tasks)

### Coordinator Post-Processing

After receiving the subagent's summary:

1. Update `session-state.md` with Plan summary and implementation strategy
2. Display summary to user for confirmation
3. Execute **Downstream Handoff** (spec-challenge routing, TDD reminder, implementation strategy routing — see below)

### Model

`model: opus` — Plan quality drives all downstream implementation; a flawed plan causes cascading rework across TDD, implementation, and verification phases.

**Timeout (dynamic)**: Scale timeout by estimated Task count — **≤5 Tasks: 180s**, **6–10 Tasks: 300s**, **>10 Tasks: 420s**. Estimate Task count before dispatch from requirement scope: single-domain focused change → ≤5; multi-domain (2–3 domains) or medium complexity → 6–10; large cross-domain (4+ domains) or high complexity → >10. If estimate is unavailable, default to 300s. On timeout, **fall back to Direct mode immediately** — do NOT retry (empirically, a timed-out Plan subagent retried under the same conditions times out again, wasting another full timeout window).

## Scope Check

If the spec covers multiple independent subsystems, suggest breaking into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for.

- Design units with clear boundaries and well-defined interfaces
- Prefer smaller, focused files over large ones that do too much
- Files that change together should live together. Split by responsibility, not by layer
- In existing codebases, follow established patterns

This structure informs the task decomposition.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

Read `./plan-header-template.md` for the exact header format. Every plan MUST start with this header. Save plans to `.claude/plans/<feature-name>.md`.

## Task Structure

Read `./task-structure-template.md` for the full task format with TDD step-by-step cycle, file paths, and test context. Each task follows this structure.

## No Placeholders

Every step must contain the actual content. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may read tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Remember
- Exact file paths always
- Complete code in every step — if a step changes code, show the code
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits

## Design Completeness Check

Before saving the plan, verify ALL open design questions are resolved. The plan must be **self-contained for TDD execution** — if the TDD phase would need to ask "how should this work?", the plan is incomplete.

**Checklist — resolve each applicable item before saving (skip items that don't apply to this change):**
- [ ] Data storage approach decided (new table vs. extend existing, field types)
- [ ] Field naming and data format specified (JSON structure, enum values, etc.)
- [ ] Configuration strategy defined (Nacos key names, default values, fallback behavior)
- [ ] Error codes and messages specified (exact code values, message text)
- [ ] External API contracts confirmed (method signatures of called services)

If any item has open questions, use **AskUserQuestion** to resolve them NOW. Do not save a plan with unresolved design decisions — TDD will inherit the ambiguity and waste turns re-asking.

## Self-Review

After writing the complete plan, review with fresh eyes:

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it? List any gaps.

**2. Placeholder scan:** Search for red flags — any patterns from the "No Placeholders" section. Fix them.

**3. Type consistency:** Do types, method signatures, and property names in later tasks match earlier definitions? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

**4. TDD readiness:** Could the TDD phase write tests from this Plan without reading any additional source files beyond the ones listed in each Task's **Files** and **Test Context** sections? If not, add the missing file paths, interface signatures, and import context.

If you find issues, fix them inline.

**Context management**: The Plan file contains all necessary context for downstream skills. After the Plan is written and self-review is complete:

1. **If spec-challenge follows** (P0 any; P1 cross-domain): **Skip context-health check entirely.** The session split decision belongs to spec-challenge's Post-Review phase — triggering compact here would preempt that split point and cause the implementation phase to run in an already-bloated session.
2. **Otherwise** (no spec-challenge downstream): Check `.claude/ecw/state/context-health.txt` — if the file exists and starts with `HIGH`, use AskUserQuestion: "压缩后继续 (Recommended)" (description: "上下文较大，在阶段边界压缩无损。输入 /compact 后自动继续") vs "直接继续". If user picks compact, output "请输入 /compact，压缩完成后将自动继续。" then STOP. Otherwise (file missing, LOW, MEDIUM, or user picks continue), proceed immediately.

## Error Handling

| Scenario | Handling |
|----------|---------|
| Subagent dispatch fails or returns incomplete plan | Record `FAILED` in Subagent Ledger → retry once → still fails: fall back to Direct mode (coordinator generates plan itself) |
| Subagent timeout (dynamic limit exceeded) | Record `TIMEOUT` in Subagent Ledger → **fall back to Direct mode immediately** (no retry — empirically, retry under same conditions times out again, wasting another full timeout window). Coordinator generates plan itself in Direct mode |
| Knowledge file missing (`ecw-path-mappings.md`, `business-rules.md`, `knowledge-summary.md`) | Log `[Warning: {file} not found, plan may lack domain constraints]` → continue plan generation with available data. Missing path-mappings: skip domain context injection. Missing business-rules: note in plan header as risk |
| Plan file write failure | Retry once → still fails: output full plan content in conversation. User can manually save to `.claude/plans/` |
| `session-state.md` unavailable (risk level unknown) | Use AskUserQuestion to ask user for risk level before proceeding |

## Downstream Handoff

After saving the plan, determine and persist implementation strategy, then route to next step:

**Update session-state.md:** Count tasks in the plan. Per risk-classifier "Implementation Strategy Selection" rules (Tasks ≤ 3 + files ≤ 5 = direct; Tasks 4-8 P0/P1 or Tasks > 8 = subagent-driven), determine strategy and update `.claude/ecw/session-data/{workflow-id}/session-state.md` `实现策略` field. If spec-challenge will follow (P0; P1 cross-domain), spec-challenge may refine this — write the initial value now.

**1. Spec Challenge needed?** (P0; P1 cross-domain only)
→ "Plan saved. Next: `ecw:spec-challenge` for adversarial review before implementation."
→ **Auto-proceed**: Immediately invoke `ecw:spec-challenge` — do NOT use AskUserQuestion or wait for user confirmation. Skip steps 2-4 below; execution choice is handled by spec-challenge's Post-Review section after review completes.

**2. TDD phase?** (P0-P2 when `tdd.enabled: true`, and spec-challenge NOT needed)
→ Remind that implementation should follow `ecw:tdd`.

**3. Implementation strategy routing:** (when spec-challenge NOT needed)

| Strategy | Handoff |
|----------|---------|
| `subagent-driven` | "Plan saved. Recommend using `ecw:impl-orchestration` to execute task-by-task with per-task review." |
| `direct` | "Plan saved. Implement tasks sequentially, following ecw:tdd for each." |

**4. Offer execution choice via AskUserQuestion:** (when spec-challenge NOT needed)
- "Subagent-Driven (Recommended)" — dispatch fresh subagent per task via ecw:impl-orchestration
- "Direct Implementation" — implement tasks sequentially in current session

## Supplementary Files

- `plan-header-template.md` — Plan document header format
- `task-structure-template.md` — Task format with TDD step-by-step cycle
