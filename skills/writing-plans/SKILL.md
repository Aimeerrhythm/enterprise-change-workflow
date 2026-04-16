---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code. Risk-aware planning with ECW domain context.
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for the codebase. Document everything: which files to touch, code, testing, how to verify. Give bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume the engineer is skilled but knows almost nothing about the project's toolset or problem domain.

**Announce at start:** "Using ecw:writing-plans to create the implementation plan."

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

Before writing the plan:

1. Read `.claude/ecw/ecw-path-mappings.md` to understand code path → domain mappings
2. For each affected domain, read its `business-rules.md` to understand constraints (state machines, validation rules, concurrency controls)
3. If `knowledge-summary.md` exists (from domain-collab), read it for cross-domain dependency context

Ensure design decisions respect domain rules. A plan that violates a state machine constraint or concurrency rule will fail at impl-verify.

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

## Self-Review

After writing the complete plan, review with fresh eyes:

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it? List any gaps.

**2. Placeholder scan:** Search for red flags — any patterns from the "No Placeholders" section. Fix them.

**3. Type consistency:** Do types, method signatures, and property names in later tasks match earlier definitions? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

If you find issues, fix them inline.

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
