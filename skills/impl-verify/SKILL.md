---
name: impl-verify
description: >
  Use when implementation is complete and ready for verification, before marking
  task done. Absorbs code-reviewer role — no separate code review needed in ECW
  workflow. Also invocable manually via /ecw:impl-verify.
---

# Impl-Verify — Implementation Correctness Verification

After implementation completes and before marking the task done, perform multi-dimensional cross-validation of code changes: code logic ↔ requirements / domain knowledge / Plan / engineering standards. Converge over multiple rounds; exit only with zero must-fix findings.

## Why This Is Needed

The most dangerous thing during implementation is not "code won't compile" but "code compiles but logic is wrong." Typical issues:

- State machine missing a transition — business flow deadlocks in certain scenarios
- Validation rule omitted — invalid data written to database
- Plan says "rollback on failure" — code swallows the exception
- Requirement says "read from config" — code hardcodes the value

These issues cannot be caught by compilation checks (compilation passes), nor by structural consistency checks (no inter-file contradictions). Only line-by-line comparison of code logic against requirements/rules/design decisions can reveal them.

## Trigger

- **Automatic**: After implementation completes, before marking task as complete
- **Manual**: `/ecw:impl-verify`

## Relationship with Other Verification Components

| Component | What It Verifies | Execution Model | Mandatory? |
|-----------|-----------------|-----------------|------------|
| **ecw:impl-verify (this skill)** | Code correctness + quality | Multi-round convergence, exit on zero must-fix | Yes (P0-P2) |
| verify-completion hook | Compilation, tests, reference integrity, knowledge sync | Auto-intercept | Yes (automatic) |
| ecw:biz-impact-analysis | Business impact scope | Single analysis | Yes (P0/P1 mandatory) |
| ecw:cross-review | Inter-file structural consistency | Multi-round convergence | No (manual, optional) |
| ecw:spec-challenge | Plan blind spots, boundary conditions | Challenge-response | Plan phase, not implementation phase |

**Relationship with code-reviewer**: impl-verify Round 4 (engineering standards) absorbs the code quality review responsibility of code-reviewer. In the ECW workflow, impl-verify replaces code-reviewer as the post-implementation code review step.

## Input Material Collection

Before execution, locate input materials in the following order:

| Material | Source | Round |
|----------|--------|-------|
| **Requirement document** | Current session's requirements-elicitation output / domain-collab report / user's original requirement description | Round 1 |
| **Domain knowledge** | `.claude/knowledge/{domain}/business-rules.md`, `data-model.md` (locate affected domains via ecw-path-mappings.md) | Round 2 |
| **Plan file** | Plan file produced by writing-plans in current session | Round 3 |
| **Changed code** | `git diff --name-only` + `git diff` (get file list and detailed changes) | All Rounds |
| **Project patterns** | Existing code's naming/layering/error-handling conventions | Round 4 |

**Knowledge file read priority** (Round 2):
1. First check if `.claude/ecw/knowledge-summary.md` exists and covers domains affected by this change
2. If summary file is sufficient (contains state machine, validation rules, data model sections), execute Round 2 based on summary
3. If summary does not exist or is insufficient, read full domain knowledge files

**Degradation handling**:
- No requirement document (P3 or degraded scenario) → Skip Round 1, warn user
- No domain knowledge files → Skip Round 2, warn user
- No Plan file → Skip Round 3, warn user
- None of the above available → Execute Round 4 only (engineering standards), output warning

### Diff Read Strategy (Reduce Redundancy)

1. **Before Round 1**: Execute `git diff --name-only` and `git diff` once, record as "baseline diff"
2. **Rounds 2-4**: Do not re-execute `git diff`. Cross-reference against diff content already read in Round 1. If specific file change details are needed, use `git diff -- {specific file}` instead of full diff
3. **Round N+ (fix re-verification)**: Only execute `git diff HEAD~1 -- {file}` for files involved in fixes to get incremental changes; do not re-read full diff
4. **Changed file table cache**: The changed file list (filename + change type + changed line count) produced in Round 1 serves as index for subsequent Rounds; no need to regenerate

### Subagent Dispatch Architecture

To prevent context overflow in the coordinator, each verification Round is dispatched as an independent subagent. The coordinator only holds the lightweight change summary and aggregated findings.

**Coordinator responsibilities:**
1. Execute `git diff --name-only` to get the changed file list (lightweight)
2. Dispatch Round 1-4 as **parallel** subagents (4 Agent tool calls in a single message)
3. Collect structured findings YAML from each subagent
4. Merge findings, present to user, handle convergence loop

**Each Round subagent uses the prompt template defined in `agents/impl-verifier.md`.** Coordinator fills the template variables with round-specific reference material and verification checklist.

**Each Round subagent receives:**
- Changed file list (from coordinator)
- Round-specific reference material paths (not content — the subagent reads them)
- Verification checklist for that Round
- Output format specification

**Each Round subagent returns** structured findings:
```yaml
round: 1  # or 2, 3, 4
findings:
  - file: "path/to/file.java"
    line: 42
    severity: must-fix  # or suggestion
    dimension: "requirements-tracing"  # or domain-rules, plan-decisions, engineering-standards
    description: "Description of the finding"
    expected: "What was expected"
    actual: "What was found"
status: pass  # or has-findings
summary: "One-line summary of this round"
```

**Parallel dispatch**: Rounds 1-4 verify independent dimensions and do not depend on each other's results. They MUST be dispatched in parallel (multiple Agent tool calls in a single assistant message) for efficiency.

**Model selection**: Use `model: "sonnet"` for all verification subagents. Verification is pattern-matching against reference material — does not require Opus-level reasoning.

## Execution Protocol

### Round 1 — Requirements ↔ Code (Bidirectional Tracing) [Subagent]

**Goal**: Every requirement is correctly implemented; every code change has requirement backing.

**A→B Direction (Requirements→Code)**:

1. Extract all requirement items from requirement document (feature points, business rules, data changes, boundary conditions)
2. For each requirement, locate code implementation (file:line)
3. **Don't just confirm existence — verify logic**:
   - Do conditional branches match the requirement's conditions?
   - Are boundary values handled per requirements?
   - Do data changes match requirement-described fields/types/constraints?
   - Are error scenarios handled per requirements?
4. Tag results:
   - ✅ Correct — logic matches
   - ⚠️ Deviation — implementation differs from requirement (describe the deviation) → **must-fix**
   - ❌ Missing — not implemented → **must-fix**

**B→A Direction (Code→Requirements)**:

1. Scan all added/modified code in `git diff`
2. For each significant change (new method, modified logic, new class, new field), trace back to requirement or design decision
3. Tag results:
   - ✅ Has backing — maps to specific requirement item
   - ❓ No backing — no corresponding item in requirement document → **needs confirmation** (may be scope creep, or may be a reasonable implementation detail)

### Round 2 — Domain Knowledge ↔ Code (Rule Alignment) [Subagent]

> Uses diff content already read in Round 1; does not re-execute full `git diff`. Only reads specific file changes as needed.

**Goal**: Code implementation is consistent with domain-level business rules and data model.

**Operations**:

1. Locate the domain of changed code via `ecw-path-mappings.md`
2. Read that domain's `business-rules.md` and `data-model.md`. **Only read sections relevant to diff changes**: state machine section (if diff involves state changes), validation rules section (if diff involves validation logic), concurrency section (if diff involves lock operations), idempotency section (if diff involves MQ consumers). If unsure which sections are relevant, read the full file.
3. Compare item by item:

| Dimension | Reference Source | What to Check |
|-----------|-----------------|---------------|
| **State machine** | business-rules.md state machine section | Do code state transitions = document definitions? Any illegal jumps? Do side effects (notifications/MQ) match? |
| **Validation rules** | business-rules.md validation section | Does code validation logic = document constraints? Are required fields, value ranges, formats consistent? |
| **Concurrency control** | business-rules.md concurrency section | Does code lock pattern (optimistic/pessimistic/distributed) = document rules? |
| **Idempotency** | business-rules.md idempotency section | Do MQ consumers / API endpoints deduplicate per document? |
| **Data model** | data-model.md | Do new field types/constraints/defaults = document definitions? Do enum values = document enums? |
| **Cross-domain interaction** | business-rules.md cross-domain section | Do cross-domain calls go through document-defined Facade? Do parameters/return values match? |

4. Tag inconsistencies: deviation description + severity (**must-fix** or **suggestion**)

### Round 3 — Plan ↔ Code (Decision Verification) [Subagent]

> Uses diff content already read in Round 1; does not re-execute full `git diff`. Only reads specific file changes as needed.

**Goal**: Every design decision in the Plan is followed in code.

**Operations**:

1. Read Plan file, extract all design decisions (architecture choices, reuse directives, execution order, error handling strategy, test requirements)
2. Verify each:

| Decision Type | Verification Method |
|--------------|-------------------|
| Architecture choice | Plan says "use strategy pattern" → Did code use strategy pattern (not if-else chain)? |
| Reuse directive | Plan says "reuse XxxManager.doSomething()" → Did code call that method (not re-implement)? |
| Execution order | Plan says "send MQ after state change" → Is MQ send after state update? |
| Error handling | Plan says "log + alert on failure, don't block" → Does catch block implement this? |
| Test coverage | Plan listed test scenarios → Do corresponding test cases exist for all? |
| Test quality | Do tests include precise assertions (assertThat / assertEquals) rather than just println or Assert.notNull? |
| Test-first | Were test files produced before or in the same batch as implementation code? (reference git log; non-blocking hint) |

3. Tag deviations → **must-fix** (test-first is **suggestion** level, does not block convergence)

### Round 4 — Engineering Standards ↔ Code (Quality Review) [Subagent]

> Uses diff content already read in Round 1; does not re-execute full `git diff`. Only reads specific file changes as needed.

**Goal**: Code quality meets project engineering standards. Absorbs code-reviewer responsibilities.

**Operations**:

1. Scan changed code against project existing patterns and engineering standards:

| Dimension | What to Check |
|-----------|---------------|
| **Naming consistency** | Do new class/method/variable names match project existing patterns? |
| **Duplicate code** | Are there opportunities to reuse existing methods? Any large duplications with other classes? |
| **Method complexity** | Does a single method have too many responsibilities and need splitting? Is nesting depth excessive? |
| **Layering violation** | Controller directly calling Mapper? Service directly operating HTTP request? |
| **Dependency direction** | Does it introduce reverse dependency (lower layer calling upper layer)? |
| **Error handling pattern** | Consistent with project existing error handling pattern (unified exception types, error code conventions)? |
| **Resource management** | Are database connections/file handles/streams properly closed? |

2. **Severity tagging**:
   - **must-fix**: Layering violations, resource leaks, severe duplication (50+ lines of identical logic), reverse dependencies
   - **suggestion**: Method too long, naming could be better, minor duplication, extractable but not urgent

### Round N+ (Conditional Trigger) — Fix Re-Verification

**Triggered only when any previous Round has must-fix findings that have been fixed.**

**Operations**:

1. Collect all files involved in fixes
2. Re-run related dimension checks on those files (not a full re-run — only the affected Rounds)
3. If this round still has must-fix findings, continue fixing and trigger next round
4. If user also addressed suggestion-level issues, re-verification covers those changes too (ensure no new issues introduced)

**Incremental re-verification**: When dispatching Round N+, only dispatch subagents for Rounds that had must-fix findings. Pass only the files involved in fixes (incremental diff), not the full change set. This reduces subagent context consumption during convergence.

### Convergence Condition

**Most recent round has zero must-fix findings → exit, output verification passed report.**

- Suggestion-level findings do not block convergence; recorded in final report for reference
- **Loop cap**: Maximum 5 rounds. If must-fix findings remain after 5 rounds, output all unresolved items and suggest user intervention
- **Context savings**: By dispatching Rounds as subagents, the coordinator holds only the changed file list (~500 tokens) plus aggregated findings YAML (~200 tokens per finding). In the WMS P0 session, this would have reduced coordinator context from ~49 file reads to ~4 YAML summaries.

## Severity Definitions

| Severity | Definition | Blocks Convergence | Typical Scenarios |
|----------|-----------|-------------------|-------------------|
| **must-fix** | Not fixing will cause functional errors, data corruption, security vulnerabilities, or severe architectural issues | Yes | State machine missing transition, validation omission, exception swallowed, resource leak, layering violation, cross-domain contract violation |
| **suggestion** | Fixing improves code quality and maintainability but does not affect functional correctness | No | Method too long, inconsistent naming, minor duplication, extractable common method |

**Judgment principle**: If unsure whether it's must-fix or suggestion, ask yourself: **Will this issue cause a bug or incident in production?** Yes → must-fix. No → suggestion.

## Risk Level Behavior Differences

| Risk | Execution Scope | Details |
|------|----------------|---------|
| **P0** | Rounds 1-4 all (mandatory) | Full verification, cannot skip |
| **P1** | Rounds 1-3 (mandatory), Round 4 recommended | Correctness mandatory, quality recommended |
| **P2** | Round 1 (recommended), can be manually skipped | At least do requirement tracing |
| **P3** | Skip | No requirement/plan documents to cross-reference; go directly to hook |
| **Bug** | Round 1 variant | Verify fix logic correctly resolves the reported issue without introducing regression |

**Bug fix Round 1 variant**:
- A→B: Bug description issue → Does fix code actually resolve it?
- B→A: Does fix code only change what needs changing, without introducing unrelated changes?
- Additional: On the code path involved in the bug, check for other potential similar issues

## Output Format

Per-round output:

```markdown
### Impl-Verify Round {N} — {dimension name}

**Check scope**: {cross-referenced artifacts + code file list}

**Findings**:

| # | Type | Reference Source | Code Location | Deviation Description | Severity |
|---|------|-----------------|--------------|----------------------|----------|
| 1 | State machine deviation | requirements: "A→B→C" | FooService.java:142 | Code allows A→C jump, missing state B | must-fix |
| 2 | Method too long | Engineering standards | BarService.java:60 | issue() method 50+ lines, mixes validation and business logic | suggestion |

**This round: {X} must-fix + {Y} suggestions.**
```

Zero must-fix output:

```markdown
### Impl-Verify Round {N} — {dimension name}

**Check scope**: {cross-referenced artifacts + code file list}

**Findings**: No must-fix items. {Y} suggestions (non-blocking).

**This round zero must-fix, verification passed.**
```

Final pass summary:

```markdown
## Impl-Verify Verification Passed

After {N} rounds of verification (fixed {X} must-fix issues), implementation correctness check passed.

**Per-dimension results**:
- Round 1 (Requirements↔Code): {count} must-fix, resolved
- Round 2 (Domain Knowledge↔Code): {count} must-fix, resolved
- Round 3 (Plan↔Code): {count} must-fix, resolved
- Round 4 (Engineering Standards↔Code): {count} must-fix, resolved
- Round {M} (Fix re-verification): Zero must-fix ✓

**Unaddressed suggestions** ({count}, non-blocking):
| # | Location | Suggestion Content |
|---|----------|--------------------|
| 1 | ... | ... |

Verification passed. Task can be marked as complete.

**Next step** (read risk level from `.claude/ecw/session-state.md`; if file does not exist or lacks risk level field, use AskUserQuestion to ask user for current risk level):
- P0/P1 change → **Immediately** use Skill tool to invoke `ecw:biz-impact-analysis` to analyze business impact of code changes.
- P2 change → **Suggested** to run `ecw:biz-impact-analysis` (not mandatory; user may decide to skip).
- P3 / pure formatting change → No biz-impact-analysis needed.

If TaskList has a pending "ecw:biz-impact-analysis" Task, marking impl-verify Task as completed will automatically unblock that Task.
```

## Output Constraints

### In-Session Output Limits

Per-round findings table:
- **≤ 5 must-fix**: Output full findings table directly
- **> 5 must-fix**: Output summary in session (count + top 3 most severe items)
- **All findings**: After each verification pass completes, write all findings to `.claude/ecw/session-data/impl-verify-findings.md` regardless of count. This ensures findings survive context compaction during multi-round convergence.
- **Zero must-fix**: Use simplified output format (`### Impl-Verify Round {N} — {dimension}` + `**Findings**: No must-fix items. {Y} suggestions (non-blocking).` + `**This round zero must-fix, verification passed.**`), no more than 3 lines

Final pass summary:
- Summary no more than **15 lines** (one line per Round result + unaddressed suggestion list max 5 items)
- If there are skipped suggestions, list only the count, not details

### Fix Re-Verification Rounds

Fix re-verification rounds (Round N+) output only:
- Re-verified must-fix IDs + pass/fail result (table format, one item per line)
- New findings (if any)
- **Do not repeat already-passed Round results**

## Common Rationalizations — You Are Bypassing Verification

When these thoughts occur, **stop** — you are rationalizing skipping or weakening verification:

| Your Thought | Reality |
|-------------|---------|
| "This is a reasonable implementation detail, not a deviation" | If the requirement explicitly specifies behavior, implementation differences are deviations. Tag ⚠️ not ✅ |
| "The requirement was unclear, so it's not a miss" | Tag as ❓ needs confirmation, not ignore. Ambiguous requirements are risk, not exemption |
| "This must-fix doesn't really have much impact, let me tag it suggestion" | Return to severity definition: Will it cause a bug or incident in production? Yes → must-fix. Do not downgrade |
| "Round 4 is all suggestion-level, let me skip it" | Round 4 can also find resource leaks, layering violations — these are must-fix. Must execute |
| "Previous rounds were clean, later rounds are just formality" | Each round covers different dimensions. Round 1 passing does not mean Round 2 will pass |
| "Too many fixes, let me mark as passed and fix next time" | Convergence condition is zero must-fix, not "close enough." This is non-negotiable |
| "I didn't change this code, no need to verify" | Everything in git diff gets verified. Your changes may break assumptions of surrounding code |
| "Tests all pass, logic must be fine" | Tests passing ≠ logic correct. Tests may not cover that path. impl-verify checks logic, not test results |

**Iron law: Convergence condition (zero must-fix) cannot be achieved by the verifier self-downgrading severity. Only fixing code achieves convergence.**

## Constraints

- **Loop cap**: Maximum 5 rounds. If must-fix findings remain after 5 rounds, output all unresolved items and suggest user intervention.
- **Skippable scenarios**: P3 changes; pure formatting/comment changes; degraded scenarios with no requirement/plan/knowledge files to cross-reference (skip with warning).
- **Out of scope**:
  - Does not check inter-file structural consistency (ecw:cross-review's responsibility, manual optional)
  - Does not check compilation/references/knowledge sync (verify-completion hook's responsibility)
  - Does not analyze business impact scope (ecw:biz-impact-analysis's responsibility)
  - Does not review plan design (ecw:spec-challenge's responsibility, plan phase not implementation phase)

## Common Implementation Deviation Patterns

For focused attention in each Round:

| Pattern | Round | Example |
|---------|-------|---------|
| **State machine transition missing** | 1, 2 | Requirement defines A→B→C, code allows direct A→C jump |
| **Validation rule omitted** | 1, 2 | Requirement says "quantity must be positive", code has no check |
| **Error handling mismatch** | 1, 3 | Plan says "rollback on failure", code swallows exception |
| **Calculation formula error** | 1 | Requirement: price × qty - discount, code: (price - discount) × qty |
| **Scope creep** | 1 | Code adds functionality not required by requirements |
| **Idempotency missing** | 2 | New MQ consumer has no deduplication, violating business-rules.md idempotency section |
| **Cross-domain contract violation** | 2 | Code directly calls cross-domain internal method, not going through document-defined Facade |
| **Reuse decision not followed** | 3 | Plan specifies reusing existing method, code re-implements it |
| **Test scenario omitted** | 3 | Plan lists normal/exception/boundary 3 test scenarios, only normal scenario test written |
| **Assertion missing** | 3 | Plan requires verifying failure return, test only prints result with no assert |
| **Mock abuse** | 3 | Mocked the output of the dependency being tested — test is testing Mock behavior, not real code |
| **Layering violation** | 4 | Controller directly calls Mapper, bypassing Service layer |
| **Resource leak** | 4 | Database connection/file handle not closed in finally |
| **Severe duplication** | 4 | 50+ lines of identical logic with another class — should extract common method |
