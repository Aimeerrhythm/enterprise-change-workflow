---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code. Risk-aware planning with ECW domain context.
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for the codebase. Document everything: which files to touch, code, testing, how to verify. Give bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume the engineer is skilled but knows almost nothing about the project's toolset or problem domain.

**Announce at start:** "Using ecw:writing-plans to create the implementation plan."

## Plan Mode — Do Not Use

**Do NOT call `EnterPlanMode` or `ExitPlanMode`.** This skill writes plans directly to `.claude/plans/` via the Write tool. Claude Code's built-in plan mode is a separate mechanism not used by ECW. After writing the plan file, use **AskUserQuestion** to confirm with the user (see Downstream Handoff).

## Risk-Aware Detail Level

Read `.claude/ecw/session-state.md` for risk level and affected domains. If unavailable, use AskUserQuestion.

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
2. **Phase 2 assessment path**: `.claude/ecw/session-data/phase2-assessment.md` (if exists)
3. **Knowledge file path list**:
   - `.claude/ecw/ecw-path-mappings.md`
   - `.claude/knowledge/{domain}/business-rules.md` (one per affected domain)
   - `.claude/ecw/knowledge-summary.md` (if exists)
4. **Plan output target path**: `.claude/plans/{feature}.md`
5. **Risk level + Plan detail requirements**: From `session-state.md` (P0/P1/P2 detail table in "Risk-Aware Detail Level" section)

### Subagent Responsibilities

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
   - Implementation Strategy (direct / subagent-driven, per "Implementation Strategy Selection" rules)

### Coordinator Post-Processing

After receiving the subagent's summary:

1. Update `session-state.md` with Plan summary and implementation strategy
2. Display summary to user for confirmation
3. Execute **Downstream Handoff** (spec-challenge routing, TDD reminder, implementation strategy routing — see below)

### Model

`model: sonnet` — Plan generation is creative writing with dense rule constraints; sonnet provides the best cost-performance balance.

**Timeout**: 300s (plan generation reads multiple knowledge files and produces substantial output). If subagent has not returned, terminate and fall back to Direct mode (see Error Handling).

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

**Save plans to:** `.claude/plans/<feature-name>.md`

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **Risk Level:** P{N} | **Domains:** {domain list} | **Implementation Strategy:** {direct | subagent-driven}

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

**Implementation Strategy** is read from `session-state.md` `实现策略` field. If TBD or unavailable, determine by risk-classifier's "实现策略选择" rules (Task count x risk level).

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Test Context:**
- Test framework: {from pom.xml/package.json, e.g., JUnit 5 + MockitoExtension}
- Base test class: {from ecw.yml tdd.base_test_class, or "none"}
- Key dependencies for test: {list interfaces/classes the test needs to mock or import, with file paths}

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

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

**Context management**: After the Plan is written to `.claude/plans/{feature}.md`, suggest to the user: "Implementation plan is complete and saved to file. Consider running `/compact` before proceeding to implementation — the Plan file contains all necessary context." Only suggest if the plan generation involved reading 3+ knowledge files.

## Error Handling

| Scenario | Handling |
|----------|---------|
| Subagent dispatch fails or returns incomplete plan | Record `FAILED` in Subagent Ledger → retry once → still fails: fall back to Direct mode (coordinator generates plan itself) |
| Knowledge file missing (`ecw-path-mappings.md`, `business-rules.md`, `knowledge-summary.md`) | Log `[Warning: {file} not found, plan may lack domain constraints]` → continue plan generation with available data. Missing path-mappings: skip domain context injection. Missing business-rules: note in plan header as risk |
| Plan file write failure | Retry once → still fails: output full plan content in conversation. User can manually save to `.claude/plans/` |
| `session-state.md` unavailable (risk level unknown) | Use AskUserQuestion to ask user for risk level before proceeding |

## Downstream Handoff

After saving the plan, determine and persist implementation strategy, then route to next step:

**Update session-state.md:** Count tasks in the plan. Per risk-classifier "实现策略选择" rules, determine strategy (direct / subagent-driven) and update `.claude/ecw/session-state.md` `实现策略` field. If spec-challenge will follow (P0; P1 cross-domain), spec-challenge may refine this — write the initial value now.

**1. Spec Challenge needed?** (P0; P1 cross-domain only)
→ "Plan saved. Next: `ecw:spec-challenge` for adversarial review before implementation."

**2. TDD phase?** (P0-P2 when `tdd.enabled: true`)
→ Remind that implementation should follow `ecw:tdd`.

**3. Implementation strategy routing:**

| Strategy | Handoff |
|----------|---------|
| `subagent-driven` | "Plan saved. Recommend using `ecw:impl-orchestration` to execute task-by-task with per-task review." |
| `direct` | "Plan saved. Implement tasks sequentially, following ecw:tdd for each." |

**4. Offer execution choice via AskUserQuestion:**
- "Subagent-Driven (Recommended)" — dispatch fresh subagent per task via ecw:impl-orchestration
- "Direct Implementation" — implement tasks sequentially in current session
