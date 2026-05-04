---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes. Domain-knowledge-driven root cause analysis.
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Announce at start:** "Using ecw:systematic-debugging for root cause investigation."

**Mode switch**: Update the MODE marker in session-state.md: `<!-- ECW:MODE:START -->` / `working_mode: implementation` / `<!-- ECW:MODE:END -->`.

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

Detailed steps (read error messages, reproduce, check changes, gather evidence, domain cross-reference, trace data flow, write checkpoint):

**Read `./prompts/investigation-steps.md`**

### Phase 2: Pattern Analysis

Find working examples, compare against references, identify differences, understand dependencies:

**Read `./prompts/analysis-and-fix.md` — Phase 2 section**

### Phase 3: Hypothesis and Testing

Form single hypothesis, test minimally, verify, escalate when stuck:

**Read `./prompts/analysis-and-fix.md` — Phase 3 section**

### Phase 4: Implementation

Create failing test, implement single fix, verify, escalate on repeated failure, question architecture after 3+ failures:

**Read `./prompts/analysis-and-fix.md` — Phase 4 section**

## Error Handling

| Scenario | Handling |
|----------|---------|
| Knowledge file missing (`ecw-path-mappings.md`, `business-rules.md`, `cross-domain-calls.md`, etc.) | Log `[Warning: {file} not found, cross-reference degraded]` → continue with available files. If all knowledge files missing: skip Step 5 (domain cross-reference) entirely, rely on code-level investigation only |
| `session-state.md` unavailable (risk level unknown) | Use simplified check (P2/P3 level) for Step 5 cross-reference depth |
| Bug not reproducible after Step 2 | Do not skip to Phase 3 — gather more data first. Log `[Not reproducible: need additional evidence]` and ask user for more context |

## Red Flags and Anti-Patterns

**Read `./prompts/anti-patterns.md`**

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, domain cross-reference, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create failing test (ecw:tdd), fix, verify | Bug resolved, tests pass |

## Supplementary Files

| File | Content |
|------|---------|
| `./prompts/investigation-steps.md` | Phase 1 detailed steps: 6-step root cause investigation + checkpoint format |
| `./prompts/analysis-and-fix.md` | Phase 2–4 detailed steps: pattern analysis, hypothesis testing, implementation |
| `./prompts/anti-patterns.md` | Red flags and common rationalizations to watch for |

## Downstream Handoff

After Phase 4 implementation completes (bug fixed, tests passing):

> **Downstream Handoff**: Update `Next` field **within the `<!-- ECW:STATUS:START/END -->` marker block** in session-state.md to `ecw:impl-verify`, then invoke `ecw:impl-verify` for post-fix verification. If `auto_continue` field is missing or `false` in session-state.md, wait for user confirmation (backward compatibility).
