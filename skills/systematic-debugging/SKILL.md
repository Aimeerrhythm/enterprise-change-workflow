---
name: systematic-debugging
description: Entry point for bug fixes. Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes. Domain-knowledge-driven root cause analysis.
---

# Systematic Debugging

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**This skill is the direct entry point for all bug fixes** — no need to run `ecw:risk-classifier` first.

**Announce at start:** "Using ecw:systematic-debugging for root cause investigation."

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

## Workflow Integration

**When invoked as the bug fix entry point**, create session-state immediately after announcing start:

**Before writing**, Read `skills/risk-classifier/session-state-format.md` for the JSON schema.

Write `.claude/ecw/session-data/{workflow-id}/session-state.json` with:
- `change_type: "bug"`
- `routing: ["ecw:systematic-debugging", "TDD:RED", "Fix(GREEN)", "ecw:impl-verify"]`
- `next: "ecw:tdd"`
- `current_phase: "systematic-debugging"`

Generate `{workflow-id}` as `{YYYYMMDD}-{xxxx}` (same convention as risk-classifier; use `currentDate` system-reminder for the date).

> `biz-impact-analysis` and `knowledge-track` are not in the default bug chain — invoke them manually if the fix has broader impact.

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed the initial investigation, you cannot propose fixes.

## The Four Phases

You MUST complete each phase before proceeding to the next. Read the supplementary files for full per-phase instructions:

- **Phase 1: Initial Investigation** — `./prompts/investigation-steps.md` (read error messages, reproduce, check changes, gather evidence, domain cross-reference, trace data flow, write checkpoint)
- **Phase 2: Pattern Analysis** — `./prompts/analysis-and-fix.md` Phase 2 section (find working examples, compare against references, identify differences, understand dependencies)
- **Phase 3: Hypothesis and Testing** — `./prompts/analysis-and-fix.md` Phase 3 section (form single hypothesis, test minimally, verify, escalate when stuck)
- **Phase 4: Implementation** — `./prompts/analysis-and-fix.md` Phase 4 section (create failing test, implement single fix, verify, escalate on repeated failure, question architecture after 3+ failures)

## Error Handling

| Scenario | Handling |
|----------|---------|
| Knowledge file missing (`path-mappings.md`, `business-rules.md`, `cross-domain-calls.md`, etc.) | Log `[Warning: {file} not found, cross-reference degraded]` → continue with available files. If all knowledge files missing: skip Step 5 (domain cross-reference) entirely, rely on code-level investigation only |
| `session-state.json` unavailable (risk level unknown) | Use simplified check (P2/P3 level) for Step 5 cross-reference depth |
| Bug not reproducible after Step 2 | Do not skip to Phase 3 — gather more data first. Log `[Not reproducible: need additional evidence]` and ask user for more context |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Initial Investigation** | Read errors, reproduce, check changes, domain cross-reference, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create failing test (ecw:tdd), fix, verify | Bug resolved, tests pass |

## Supplementary Files

| File | Content |
|------|---------|
| `./prompts/investigation-steps.md` | Initial investigation steps: 6-step root cause investigation + checkpoint format |
| `./prompts/analysis-and-fix.md` | Phase 2–4 detailed steps: pattern analysis, hypothesis testing, implementation |
| `./prompts/anti-patterns.md` | Red flags and common rationalizations to watch for |
