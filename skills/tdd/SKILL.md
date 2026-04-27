---
name: tdd
description: Use when implementing any feature or bugfix, before writing implementation code. Risk-aware TDD with ecw.yml integration.
---

# Test-Driven Development (TDD)

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Announce at start:** "Using ecw:tdd to guide test-first implementation."

**Mode switch**: Update session-state.md MODE marker to `implementation`.

## Scope Boundary

**ecw:tdd executes the Red-Green(-Refactor) cycle. It does NOT own design decisions.**

### Requirement changes (Plan exists)

Before writing any test, **read the Plan file** (`.claude/plans/<name>.md`). All file paths, method signatures, test scenarios, error codes, and data formats are specified there.

**What this skill MUST do:**
- Read the Plan to get file paths, test scenarios, and expected behavior
- Write failing tests (RED) per Plan specification
- Write minimal implementation to pass tests (GREEN)
- Run compilation and tests to verify

**What this skill MUST NOT do:**
- Ask design questions via AskUserQuestion (data format, field naming, storage approach — these belong to writing-plans). If a design gap is found, note it in output and proceed with the Plan's specification.
- Rewrite or update the Plan file (if the Plan is wrong, finish current Task's TDD first, then report the discrepancy)
- Explore the codebase to rediscover what the Plan already specifies (file paths, class names, method signatures are in the Plan)
- Create new Tasks beyond what the Plan defines

**Handling factual errors in the Plan** (class not found, method signature mismatch, wrong file path):
- One verification Read is allowed to confirm the error is real (not a typo in your code)
- If confirmed, note the discrepancy in output, adapt minimally to make the test compile, and continue
- Do NOT use this as a loophole for general exploration — one targeted Read per error, not open-ended searching

### Bug fixes (no Plan — input from systematic-debugging)

Bug fixes skip writing-plans. The input is the root cause analysis from `ecw:systematic-debugging`, not a Plan file.

**What this skill MUST do:**
- Write a failing test that **reproduces the bug** (RED)
- Fix the code minimally to make the test pass (GREEN)
- Run full test suite to verify no regressions

**What this skill MUST NOT do:**
- Redesign or refactor surrounding code beyond the fix scope
- Skip the reproduction test ("I already know the fix" is not an excuse)

## Risk-Aware Enforcement

Read `.claude/ecw/session-data/{workflow-id}/session-state.md` for current risk level. If unavailable (standalone invocation), default to P0 (mandatory + verification log).

| Risk Level | TDD Mode | Details |
|-----------|----------|---------|
| **P0** | Mandatory + verification log | Full Red-Green-Refactor with logged test output per cycle |
| **P1** | Mandatory | Full Red-Green-Refactor cycle |
| **P2** | Simplified | Red-Green only; max 5 cycles, max 50 turns; skip Refactor; 3x same compile error → stop |
| **P3** | Recommended | Encourage but don't enforce; user decides |
| **Bug** | Mandatory (reproduction test) | Write failing test reproducing bug, then fix (RED→GREEN) |
| **Emergency** | Skip | Speed-first; verify with full test suite post-fix; ecw:impl-verify still required |

**ecw.yml override:** If `tdd.enabled: false`, all levels degrade to Recommended.

### Skip Confirmation Protocol

If skipping TDD for any reason (P3 preference, prototype, generated code):

Use AskUserQuestion: "This task qualifies for TDD. Skip TDD for this implementation?"
- Options: "Apply TDD (Recommended)" / "Skip TDD"
- If Skip chosen, log reason and proceed without TDD.

### P2 Simplified Mode Rules

When risk level is P2, apply these concrete constraints:

1. **Plan-first**: Read the Plan before writing any test. All file paths, method signatures, test scenarios, dependencies, and test framework info are in the Plan. Do NOT use Read/Grep/Glob to rediscover this information.
2. **Max 5 Red-Green cycles**: If the Plan specifies more test scenarios, batch related ones into fewer cycles (e.g., 3 validation-error tests → 1 RED with 3 assertions → 1 GREEN).
3. **Max 50 total turns**: If this limit is reached, stop and report status to the user. Do not continue silently.
4. **Skip Refactor phase entirely**: P2 does not require refactor. Move directly from GREEN to next cycle.
5. **Compile failure limit**: If the same compilation error recurs 3 times after attempted fixes, stop and report to the user instead of retrying.
6. **No design questions**: Do not use AskUserQuestion for design decisions (data format, field naming, storage approach). These were resolved during writing-plans. If you discover a genuine gap, note it in your output and proceed with the Plan's specification.

## Subagent-Driven Fast Route

When **Implementation Strategy** in `session-state.md` is `subagent-driven` (i.e., `ecw:impl-orchestration` will be used), **this skill is a pass-through**. TDD cycles execute inside each implementer subagent, not in the coordinator.

**Action — do these two things only, then stop:**

1. Update `session-state.md` MODE marker to `implementation`
2. Invoke `ecw:impl-orchestration` via Skill tool

TDD protocol (Iron Law, risk-aware enforcement, cycle rules) is embedded into each implementer's prompt by `ecw:impl-orchestration`. Do NOT execute any TDD cycle in the coordinator when strategy is subagent-driven.

When **Implementation Strategy** is `direct` but the Plan involves **≥ 6 unique files**:

1. Each RED-GREEN cycle is dispatched as an independent subagent via the Agent tool (`model: sonnet`, default from `models.defaults.implementation`; configurable via ecw.yml — TDD cycles require understanding test frameworks and business logic)
2. The subagent receives: current cycle's test scenario from the Plan, relevant file paths, and TDD protocol rules
3. The subagent executes: write test → compile → implement → compile → verify
4. The subagent returns: cycle result summary (pass/fail, files created/modified, test output snippet ≤ 10 lines)
5. The coordinator tracks cycle progress but does NOT read implementation file contents

**Timeout per cycle subagent**: 180s. If a cycle subagent times out, terminate and fall back to direct execution for that cycle.

**Rationale**: In the WMS P0 cross-domain task, TDD executed 107 file reads in the coordinator, causing 3 context compressions. Delegating cycles to subagents keeps coordinator context lean.

## TDD Execution Protocol

Read `./prompts/red-green-refactor.md` for:
- The Iron Law (no production code without a failing test first)
- Full Red-Green-Refactor cycle diagram and per-phase instructions
- P0 verification log format and checkpoint rules

Read `./prompts/test-quality-guide.md` for:
- Test framework awareness and default test commands
- Good test criteria and common rationalizations
- Red flags requiring a full restart
- Bug fix integration rules
- Verification checklist
- Guidance when stuck

## Downstream Handoff

After all TDD cycles for the current Plan Task complete (all tests GREEN):

1. **If Implementation Strategy is `subagent-driven`**: TDD cycles are executed inside implementer subagents dispatched by `ecw:impl-orchestration`. No coordinator-level handoff needed — `ecw:impl-orchestration` manages the flow.

2. **If Implementation Strategy is `direct`** (executing Tasks sequentially in main session):
   - Mark the current Task as complete via TaskUpdate
   - Check TaskList for the next pending Plan Task
   - If next Plan Task exists: Begin TDD RED phase for the next Task immediately
   - If all Plan Tasks complete: Proceed to impl-verify

> **Downstream Handoff**: After the final Plan Task's GREEN phase completes, update session-state.md `Next` field to `ecw:impl-verify`, then invoke `ecw:impl-verify`. If a pending `ecw:impl-verify` Task exists in TaskList, mark it `in_progress` first. If `Auto-Continue` field is missing or `no` in session-state.md, wait for user confirmation (backward compatibility).

## Error Handling

| Scenario | Handling |
|----------|---------|
| Plan file missing or unreadable | For requirement changes: halt and notify user — TDD cannot proceed without a Plan. For bug fixes: proceed using systematic-debugging output as input |
| `session-state.md` unavailable (risk level unknown) | Default to P0 (mandatory + verification log) and proceed |
| Subagent delegation failure (≥ 6 files mode) | Record failure → retry once → still fails: fall back to direct TDD execution in coordinator context |
| Test command fails with environment error (not test failure) | Report environment issue to user — do not count as TDD cycle failure. Fix environment first, then resume |

## Supplementary Files

| File | Purpose |
|------|---------|
| `./prompts/red-green-refactor.md` | Iron Law + full Red-Green-Refactor cycle protocol |
| `./prompts/test-quality-guide.md` | Test quality criteria, rationalizations, checklist, and stuck guidance |
