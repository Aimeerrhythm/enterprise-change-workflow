---
name: impl-verify
description: >
  Use when implementation is complete and ready for verification, before marking
  task done. Absorbs code-reviewer role — no separate code review needed in ECW
  workflow. Also invocable manually via /ecw:impl-verify.
---

# Impl-Verify — Implementation Correctness Verification

After implementation completes and before marking the task done, perform multi-dimensional cross-validation of code changes: code logic ↔ requirements / domain knowledge / Plan / engineering standards. Converge over multiple rounds; exit only with zero must-fix findings.

**Announce at start:** "Using ecw:impl-verify to verify implementation correctness."

**Mode switch**: Update session-state.md MODE marker to `verification`.

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
1. First check if `.claude/ecw/session-data/{workflow-id}/knowledge-summary.md` exists and covers domains affected by this change
2. If summary file is sufficient (contains state machine, validation rules, data model sections), execute Round 2 based on summary
3. If summary does not exist or is insufficient, read full domain knowledge files

> **Knowledge file robustness (Round 2)**: Before reading any domain knowledge file, verify it exists. If `business-rules.md` or `data-model.md` for a domain is missing, log `[Warning: {domain}/{file} not found, Round 2 checks for this domain degraded]` in the Round 2 findings. The subagent should still check available files and report what dimensions could not be verified.

**Degradation handling**:
- No requirement document (P3 or degraded scenario) → Skip Round 1, warn user
- No domain knowledge files → Skip Round 2, warn user
- No Plan file → Skip Round 3, warn user
- None of the above available → Execute Round 4 only (engineering standards), output warning

### Diff Read Strategy (Reduce Redundancy)

1. **Coordinator pre-processing**: Execute `git diff --name-only` once to get the changed file list. Pass this list (not full diff content) to all Round subagents
2. **Round 1-4 subagents (parallel)**: Each subagent independently reads code changes for its verification needs. Use targeted `git diff -- {specific file}` for files relevant to that Round's dimension, rather than reading full `git diff` for all files. This keeps each subagent's context lean
3. **Round N+ (fix re-verification)**: Only execute `git diff HEAD~1 -- {file}` for files involved in fixes to get incremental changes. Do not re-read the full baseline diff
4. **Changed file table cache**: The changed file list from coordinator pre-processing serves as the index for all Rounds; each subagent receives it as input

### Subagent Dispatch Architecture

To prevent context overflow in the coordinator, each verification Round is dispatched as an independent subagent. The coordinator only holds the lightweight change summary and aggregated findings.

**Coordinator responsibilities:**
1. Execute `git diff --name-only` to get the changed file list (lightweight)
2. Dispatch Round 1-4 as **parallel** subagents (4 Agent tool calls in a single message)
3. Collect structured findings YAML from each subagent
4. Merge findings, deduplicate across Rounds
5. **Persist findings**: Write merged findings to `.claude/ecw/session-data/{workflow-id}/impl-verify-findings.md` **before** creating any fix Tasks or presenting to user. Format per finding: severity, Round, file:line, description, expected vs actual, fix suggestion. Update this file after each re-verification round (append new findings, mark fixed ones as `[FIXED]`). This ensures findings survive context compaction.
6. Present findings to user, handle convergence loop

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

**Return value validation**: For each Round subagent, verify the YAML contains required fields (`round`, `findings`, `status`, `summary`). For each finding, verify `file`, `severity`, and `description` exist. If validation fails:
1. Log to Ledger: `[FAILED: impl-verify Round {N}, reason: invalid return format]`
2. Retry once with the same model
3. If retry also fails: mark that Round as `[incomplete: Round {N}]` in the output, continue with findings from other Rounds. Do not block convergence — but warn user that one verification dimension was skipped.

**Model selection**: Use `model: "sonnet"` (default from `models.defaults.verification`; configurable via ecw.yml) for all verification subagents. Reason: verification is pattern-matching against reference material — does not require Opus-level reasoning.

**Timeout per Round subagent**: 180s. If a Round subagent has not returned within this time, terminate it and fall back to coordinator inline execution for that Round (see Error Handling).

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

> Each subagent reads code changes independently using targeted `git diff -- {file}` for files relevant to its verification dimension.

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

> Each subagent reads code changes independently using targeted `git diff -- {file}` for files relevant to its verification dimension.

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

> Each subagent reads code changes independently using targeted `git diff -- {file}` for files relevant to its verification dimension.

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

If ecw.yml `rules.enabled: true`: pass engineering rules files from `rules.path` (default `.claude/ecw/rules/`) to the Round 4 subagent. Verification against `[must-follow]` rules → must-fix; `[recommended]` rules → suggestion.

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
- **Stall detection**: If must-fix count does not decrease for 2 consecutive rounds (Round N and N+1 have equal or higher must-fix count), stop iterating and escalate to user: `[Stall detected: must-fix count not decreasing after {N} rounds. Remaining {X} must-fix items require manual intervention.]`
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

**Before generating verification output**, Read `./output-templates.md` for per-round findings format, zero-findings format, final pass summary structure, and output constraints.

## Error Handling

| Scenario | Handling |
|----------|---------|
| Round subagent returns empty or malformed YAML | Record `FAILED` in findings → retry once with explicit output format instructions → still fails: coordinator executes that Round inline (fallback to non-subagent mode for that Round only) |
| All 4 Round subagents fail | Notify user: `[DEGRADED: automated verification unavailable]` → suggest manual code review or retry |
| Knowledge file missing (Round 2: `business-rules.md`, `data-model.md`, `knowledge-summary.md`) | Skip Round 2 with `[Warning: domain knowledge files not found, Round 2 skipped]` → continue with Rounds 1, 3, 4 |
| Requirement/Plan file missing | Skip corresponding Round (1 or 3) with warning → execute remaining Rounds |
| `impl-verify-findings.md` write failure | Retry once → still fails: output findings in conversation to preserve for convergence tracking |
| `git diff` command failure | Verify git state with `git status` → if not in a git repo or no changes: notify user and exit |

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

For focused attention in each Round, Read `./deviation-patterns.md` for the 14 most common deviation patterns with Round mapping and examples.

## Supplementary Files

- `output-templates.md` — Per-round findings format, zero-findings format, final pass summary, output constraints
- `deviation-patterns.md` — 14 common implementation deviation patterns by Round
