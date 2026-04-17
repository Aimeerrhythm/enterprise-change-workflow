---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes. Domain-knowledge-driven root cause analysis.
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Announce at start:** "Using ecw:systematic-debugging for root cause investigation."

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

**Step 1: Read Error Messages Carefully**
- Don't skip past errors or warnings
- Read stack traces completely
- Note line numbers, file paths, error codes

**Step 2: Reproduce Consistently**
- Can you trigger it reliably?
- What are the exact steps?
- If not reproducible, gather more data — don't guess

**Step 3: Check Recent Changes**
- What changed that could cause this?
- Git diff, recent commits
- New dependencies, config changes

**Step 4: Gather Evidence in Multi-Component Systems**

When system has multiple components (API → service → database, CI → build → deploy):

Before proposing fixes, add diagnostic instrumentation:
```
For EACH component boundary:
  - Log what data enters component
  - Log what data exits component
  - Verify environment/config propagation
  - Check state at each layer

Run once to gather evidence showing WHERE it breaks
THEN analyze evidence to identify failing component
THEN investigate that specific component
```

**Step 5: Domain Knowledge Cross-Reference**

Read `.claude/ecw/session-data/{workflow-id}/session-state.md` for risk level. Scale cross-reference depth by risk:

**P0/P1 — Full cross-domain tracing:**

1. From `.claude/ecw/ecw-path-mappings.md`, locate the bug's domain
2. Read domain's `business-rules.md` — check state machines, validation rules, concurrency controls
3. Query `cross-domain-calls.md` (§1) — trace upstream callers and downstream callees
4. Query `mq-topology.md` (§2) — check if affected code publishes/consumes messages; trace message flow
5. Query `shared-resources.md` (§3) — check if bug involves a shared service/component; list all consumers

> **Knowledge file robustness**: Verify each file exists before reading. For any missing file, log `[Warning: {file} not found, skipping this cross-reference dimension]` and continue with available files. If `ecw-path-mappings.md` is missing, use directory-based heuristic to infer domain (e.g., `src/main/java/{domain}/` path pattern).

**P2/P3 — Simplified check:**
1. Locate domain from `ecw-path-mappings.md`
2. Read domain's `business-rules.md`
3. Query `shared-resources.md` (§3) only — check shared resource contention

**If session-state.md doesn't exist** (e.g., debugging outside ECW flow), skip step 5 or use simplified check.

**Step 6: Trace Data Flow**

When error is deep in call stack:
- Where does bad value originate?
- What called this with bad value?
- Keep tracing up until you find the source
- Fix at source, not at symptom

**Phase 1 Checkpoint**: After completing all 6 steps, write evidence summary to `.claude/ecw/session-data/{workflow-id}/debug-evidence.md`:
```markdown
# Debug Evidence (Phase 1)
## Error: {error message summary}
## Reproduction: {steps or "not reproducible"}
## Recent Changes: {relevant git diff summary}
## Domain Cross-Reference: {findings from Step 5, or "skipped"}
## Data Flow Trace: {source of bad value, or "N/A"}
## Working Hypothesis: {initial hypothesis for Phase 2}
```
This ensures Phase 1 evidence survives context compaction during long debugging sessions.

### Phase 2: Pattern Analysis

**Find the pattern before fixing:**

1. **Find Working Examples** — Locate similar working code in same codebase
2. **Compare Against References** — If implementing pattern, read reference implementation COMPLETELY. Don't skim.
3. **Identify Differences** — What's different between working and broken? List every difference.
4. **Understand Dependencies** — What other components, config, environment does this need?

### Phase 3: Hypothesis and Testing

**Scientific method:**

1. **Form Single Hypothesis** — State clearly: "I think X is the root cause because Y." Be specific.
2. **Test Minimally** — Make the SMALLEST possible change. One variable at a time.
3. **Verify** — Did it work? Yes → Phase 4. No → form NEW hypothesis. Don't stack fixes.
4. **When You Don't Know** — Say so. Research more. Use AskUserQuestion to ask the user.

### Phase 4: Implementation

**Fix the root cause, not the symptom:**

1. **Create Failing Test Case**
   - Simplest possible reproduction
   - Automated test if possible
   - MUST have before fixing
   - Follow `ecw:tdd` for proper test-first discipline: write the failing reproduction test (RED), then implement the fix to make it pass (GREEN), then refactor if needed
   - For risk level, refer to `ecw:tdd` enforcement table (Bug row = Mandatory)

2. **Implement Single Fix**
   - Address the root cause identified
   - ONE change at a time
   - No "while I'm here" improvements

3. **Verify Fix**
   - Test passes now?
   - No other tests broken?
   - Issue actually resolved?

4. **If Fix Doesn't Work**
   - STOP
   - Count: How many fixes have you tried?
   - If < 3: Return to Phase 1, re-analyze with new information
   - **If >= 3: STOP and question the architecture (step 5 below)**

5. **If 3+ Fixes Failed: Question Architecture**

   Pattern indicating architectural problem:
   - Each fix reveals new shared state/coupling in different place
   - Fixes require massive refactoring
   - Each fix creates new symptoms elsewhere

   **STOP and question fundamentals:**
   - Is this pattern fundamentally sound?
   - Should we refactor architecture vs. continue fixing symptoms?
   - Suggest `ecw:risk-classifier --recheck` to re-evaluate risk level

   **Use AskUserQuestion to discuss with user before more fixes.**

## Error Handling

| Scenario | Handling |
|----------|---------|
| Knowledge file missing (`ecw-path-mappings.md`, `business-rules.md`, `cross-domain-calls.md`, etc.) | Log `[Warning: {file} not found, cross-reference degraded]` → continue with available files. If all knowledge files missing: skip Step 5 (domain cross-reference) entirely, rely on code-level investigation only |
| `session-state.md` unavailable (risk level unknown) | Use simplified check (P2/P3 level) for Step 5 cross-reference depth |
| Bug not reproducible after Step 2 | Do not skip to Phase 3 — gather more data first. Log `[Not reproducible: need additional evidence]` and ask user for more context |

## Red Flags - STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals new problem in different place**

**ALL of these mean: STOP. Return to Phase 1.**

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "I see the problem, let me fix it" | Seeing symptoms does not equal understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question pattern. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, domain cross-reference, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create failing test (ecw:tdd), fix, verify | Bug resolved, tests pass |
