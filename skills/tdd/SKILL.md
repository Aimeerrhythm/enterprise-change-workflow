---
name: tdd
description: Use when implementing any feature or bugfix, before writing implementation code. Risk-aware TDD with ecw.yml integration.
---

# Test-Driven Development (TDD)

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Announce at start:** "Using ecw:tdd to guide test-first implementation."

## Scope Boundary

**ecw:tdd executes the Red-Green(-Refactor) cycle per Task from the Plan. It does NOT own design decisions.**

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

## Risk-Aware Enforcement

Read `.claude/ecw/session-state.md` for current risk level. If unavailable, use AskUserQuestion to ask the user.

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

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

**No exceptions:**
- Don't keep it as "reference"
- Don't "adapt" it while writing tests
- Don't look at it
- Delete means delete

Implement fresh from tests. Period.

## Red-Green-Refactor

```dot
digraph tdd_cycle {
    rankdir=LR;
    red [label="RED\nWrite failing test", shape=box, style=filled, fillcolor="#ffcccc"];
    verify_red [label="Verify fails\ncorrectly", shape=diamond];
    green [label="GREEN\nMinimal code", shape=box, style=filled, fillcolor="#ccffcc"];
    verify_green [label="All tests\npass?", shape=diamond];
    refactor [label="REFACTOR\nClean up", shape=box, style=filled, fillcolor="#ccccff"];
    verify_refactor [label="Still all\ngreen?", shape=diamond];
    next [label="Next", shape=ellipse];

    red -> verify_red;
    verify_red -> green [label="yes"];
    verify_red -> red [label="wrong\nfailure"];
    green -> verify_green;
    verify_green -> refactor [label="yes"];
    verify_green -> green [label="no"];
    refactor -> verify_refactor;
    verify_refactor -> next [label="yes"];
    verify_refactor -> green [label="no"];
    next -> red;
}
```

### RED - Write Failing Test

Write one minimal test showing what should happen.

**Requirements:**
- One behavior per test
- Clear name describing the behavior
- Real code (no mocks unless unavoidable)

### Verify RED - Watch It Fail

**MANDATORY. Never skip.**

Run the test. Confirm:
- Test fails (not errors)
- Failure message is expected
- Fails because feature missing (not typos)

**Test passes?** You're testing existing behavior. Fix test.
**Test errors?** Fix error, re-run until it fails correctly.

### GREEN - Minimal Code

Write simplest code to pass the test. Don't add features, refactor other code, or "improve" beyond the test.

### Verify GREEN - Watch It Pass

**MANDATORY.**

Confirm:
- Test passes
- Other tests still pass
- Output pristine (no errors, warnings)

**Test fails?** Fix code, not test.
**Other tests fail?** Fix now.

### REFACTOR - Clean Up

After green only:
- Remove duplication
- Improve names
- Extract helpers

Keep tests green. Don't add behavior.

**P0 verification log:** After each cycle, record:
```
[TDD Cycle N] RED: <test name> → FAIL (<expected failure>)
              GREEN: <minimal change> → PASS
              REFACTOR: <what changed or "none">
```

### Repeat

Next failing test for next behavior.

## Test Framework Awareness

Infer default test command from `ecw.yml project.language`:

| Language | Default Test Command |
|----------|---------------------|
| java | `mvn test -pl <module> -Dtest=<TestClass>` |
| go | `go test ./path/to/package -run TestName` |
| typescript | `npm test -- --testPathPattern=<file>` |
| python | `pytest path/to/test.py::test_name -v` |

If `tdd.base_test_class` is set in ecw.yml, extend from it in new test files.

## Good Tests

| Quality | Good | Bad |
|---------|------|-----|
| **Minimal** | One thing. "and" in name? Split it. | `test('validates email and domain and whitespace')` |
| **Clear** | Name describes behavior | `test('test1')` |
| **Shows intent** | Demonstrates desired API | Obscures what code should do |
| **Real code** | Tests actual behavior | Tests mock behavior |

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Already manually tested" | Ad-hoc is not systematic. No record, can't re-run. |
| "Deleting X hours is wasteful" | Sunk cost fallacy. Keeping unverified code is debt. |
| "Need to explore first" | Fine. Throw away exploration, start with TDD. |
| "Test hard = design unclear" | Listen to test. Hard to test = hard to use. |
| "TDD will slow me down" | TDD faster than debugging. |
| "Keep as reference" | You'll adapt it. That's testing after. Delete means delete. |

## Red Flags - STOP and Start Over

- Code before test
- Test after implementation
- Test passes immediately
- Can't explain why test failed
- Rationalizing "just this once"
- "Keep as reference" or "adapt existing code"
- "Already spent X hours, deleting is wasteful"

**All of these mean: Delete code. Start over with TDD.**

## Bug Fix Integration

Bug found? Write failing test reproducing it. Follow TDD cycle. Test proves fix and prevents regression.

Never fix bugs without a test. This integrates with `ecw:systematic-debugging` Phase 4.

## Verification Checklist

Before marking work complete:

- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason (feature missing, not typo)
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass
- [ ] Output pristine (no errors, warnings)
- [ ] Tests use real code (mocks only if unavoidable)
- [ ] Edge cases and errors covered
- [ ] `tdd.check_test_files` satisfied (if enabled in ecw.yml)

Can't check all boxes? You skipped TDD. Start over.

## When Stuck

| Problem | Solution |
|---------|----------|
| Don't know how to test | Write wished-for API. Write assertion first. Use AskUserQuestion to ask user. |
| Test too complicated | Design too complicated. Simplify interface. |
| Must mock everything | Code too coupled. Use dependency injection. |
| Test setup huge | Extract helpers. Still complex? Simplify design. |
