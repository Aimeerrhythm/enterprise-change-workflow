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

**Output language**: Read `ecw.yml` → `project.output_language`. All artifact headings, table headers, and labels in `impl-verify-findings.md` follow this language. Pass to dispatched verifier agent prompts.

**Mode switch**: Update the MODE marker in session-state.md: `<!-- ECW:MODE:START -->` / `- **Working Mode**: verification` / `<!-- ECW:MODE:END -->`.

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

   **Convergence status marker**: The **first line** of `impl-verify-findings.md` must be one of:
   - `<!-- ECW:VERIFY-STATUS: HAS-MUST-FIX -->` — when any unresolved must-fix items exist
   - `<!-- ECW:VERIFY-STATUS: PASS -->` — when convergence is achieved (zero must-fix in the latest round)

   Update this marker every time the findings file is written or updated. The `verify-completion` hook reads this marker to mechanically block task completion when must-fix items are unresolved.
6. Present findings to user, handle convergence loop

**Each Round subagent is dispatched with `subagent_type: "ecw:impl-verifier"`**, which auto-injects the agent's base instructions (verification approach, output format, reading limits). Coordinator passes round-specific reference material and verification checklist in the `prompt` parameter.

**Each Round subagent receives:**
- Changed file list (from coordinator)
- Round-specific reference material paths (not content — the subagent reads them)
- Verification checklist for that Round (Read `./prompts/round-checklists.md` and pass the relevant Round section)
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

### Round 1 — Requirements ↔ Code [Subagent]

Read `./prompts/round-checklists.md` — Round 1 section for the full bidirectional tracing checklist.

### Round 2 — Domain Knowledge ↔ Code [Subagent]

Read `./prompts/round-checklists.md` — Round 2 section for the domain rule alignment checklist.

### Round 3 — Plan ↔ Code [Subagent]

Read `./prompts/round-checklists.md` — Round 3 section for the plan decision verification checklist.

### Round 4 — Engineering Standards ↔ Code [Subagent]

Read `./prompts/round-checklists.md` — Round 4 section for the engineering standards quality review checklist.

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

## Downstream Handoff

After convergence (zero must-fix findings in the most recent round):

> **Downstream Handoff**: Read risk level and domain mode from session-state.md (if unavailable, default to P0), update `Next` field **within the `<!-- ECW:STATUS:START/END -->` marker block**, then:
> - **P0/P1**: Invoke `ecw:biz-impact-analysis`. Mark the `ecw:impl-verify` Task as complete and the `ecw:biz-impact-analysis` Task as `in_progress` if it exists in TaskList. (knowledge-track runs after biz-impact-analysis completes)
> - **P2 cross-domain**: If ecw.yml `paths.knowledge_root` exists, invoke `ecw:knowledge-track`. Then suggest biz-impact-analysis; wait for user decision.
> - **P2 single-domain**: If ecw.yml `paths.knowledge_root` exists, invoke `ecw:knowledge-track`. No biz-impact-analysis suggestion (excluded per workflow-routes.yml).
> - **P3**: If ecw.yml `paths.knowledge_root` exists, invoke `ecw:knowledge-track`. No further downstream handoff.
> - If `Auto-Continue` field is missing or `no` in session-state.md, wait for user confirmation (backward compatibility).

## Severity Definitions and Verification Discipline

Read `./prompts/common-rationalizations.md` for severity definitions, the must-fix/suggestion judgment principle, and the common rationalization guard (iron law).

## Risk Level Behavior Differences

Read risk level from `.claude/ecw/session-data/{workflow-id}/session-state.md`. If unavailable (standalone invocation), default to P0 (all rounds mandatory).

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
- `prompts/round-checklists.md` — Round 1-4 verification checklists (subagent reasoning instructions)
- `prompts/common-rationalizations.md` — Severity definitions and verification discipline guard (iron law)
