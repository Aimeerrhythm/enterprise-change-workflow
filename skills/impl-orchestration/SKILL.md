---
name: impl-orchestration
description: Use when executing implementation plans with independent tasks. Risk-aware subagent dispatch with per-task review.
---

# Implementation Orchestration

Execute plan by dispatching subagents per task in dependency-aware parallel layers, with risk-aware review gates.

**Why subagents:** Delegate tasks to specialized agents with isolated context. Precisely craft their instructions — they never inherit your session context. This preserves your context for coordination work.

**Core principle:** Dependency graph → parallel layers → worktree-isolated dispatch → merge → review = high quality, fast execution.

**Announce at start:** "Using ecw:impl-orchestration to execute the plan with parallel layer dispatch."

## When to Use

Use when:
- You have an implementation plan (from `ecw:writing-plans`)
- Tasks are mostly independent
- `session-state.md` `实现策略` = `subagent-driven`, OR Task count x risk level matches subagent-driven criteria per risk-classifier

Don't use when:
- No plan exists (write one first)
- Tasks are tightly coupled (implement directly)
- P2 / P3 / simple changes (implement directly)

## Risk-Aware Review Depth

Read `.claude/ecw/session-data/{workflow-id}/session-state.md` for risk level. If unavailable (standalone invocation), default to P0 (full review depth).

| Risk Level | Per-task Spec Review | Per-task Code Quality Review | Post-impl |
|-----------|---------------------|----------------------------|-----------|
| **P0** | Mandatory | Mandatory (simplified inline) | ecw:impl-verify (full 4 Rounds) |
| **P1** | Mandatory | **Skip** (impl-verify Round 4 covers this) | ecw:impl-verify (full 4 Rounds) |
| **P2** | Not applicable (P2 doesn't use orchestration) | — | ecw:impl-verify |

**Why P0 keeps code quality review:** Error cost at P0 is extreme. Catching issues per-task is cheaper than finding them across the full implementation.

**Why P1 skips code quality review:** impl-verify Round 4 (engineering standards) provides the same checks with full implementation context, avoiding duplicate work.

## The Process

For a visual overview of the full process (Setup → Per-Layer Cycle → impl-verify), see `./process-diagram.md`.

## Setup

1. **Read plan file once** — extract all tasks with full text
2. **Build dependency graph** — see Dependency Graph Construction below
3. **Create TaskCreate list** — one Task per plan task, with dependency chain
4. **Display execution layers** — show user the parallel execution plan before starting
5. **Pre-check** — read ecw.yml, run compile + test commands once to establish baseline. Timeout 120s. If pre-check fails: attempt auto-fix → retry → still fails: notify user and continue (don't block)
6. **Note context** — architectural decisions, domain constraints, file structure

## Pre-flight Check

Before dispatching the first Task, run a build/test pre-flight to catch pre-existing failures early. This prevents wasting multiple Task dispatches before discovering a broken baseline.

**Controlled by** `impl_orchestration.pre_check` in ecw.yml (default: `true`). Set to `false` to skip.

**Steps:**

1. Read ecw.yml to determine project type and verification settings:
   - Java (`pom.xml` exists): run `mvn compile -q -T 1C`
   - If `verification.run_tests` is true: also run `mvn test -q -T 1C`
   - Other project types: skip (no universal pre-flight command)
2. **Timeout**: 120s for compile, `verification.test_timeout` (default 300s) for tests
3. **On failure**:
   - Attempt one auto-fix pass (read error output, fix obvious issues like missing imports or syntax errors)
   - Re-run the failed check
   - If still failing: notify user with the error summary via AskUserQuestion — "Pre-flight check failed: {summary}. Continue anyway or fix first?" — then proceed based on user choice
4. **Record result** in session-state.md: `Pre-flight: PASS` or `Pre-flight: FAIL (continued)`
5. On success or user-approved continue: proceed to Dependency Graph Construction

## Dependency Graph Construction

Before dispatching any task, build a dependency graph to determine which tasks can run in parallel.

### Step 1: Extract Task Metadata from Plan (LLM)

For each `## Task N:` heading in the plan, extract:
- `id` (int): task number
- `files` (list of strings): files to create or modify — from "Files:" line or inferred from task description
- `depends_on` (list of ints): explicit dependency IDs — from "depends on Task N" / "after Task N" / "requires output from Task N" phrases

Plan task ordering often implies sequence — but only include in `depends_on` when explicitly stated or logically required (e.g., Task creates a class that another Task extends).

Heuristics for `files`:
- Plan usually lists "Files to create/modify" per task
- Same module + same class/file → include both tasks
- Same configuration file → include both tasks
- Uncertain → include the file (safe default — the script will serialize conflicting tasks)

### Step 2: Call dep_graph.py (Deterministic)

Format the extracted task list as JSON and run:

```bash
echo '[{"id": 1, "files": ["A.java"], "depends_on": []}, {"id": 2, "files": ["B.java", "Shared.java"], "depends_on": [1]}, {"id": 3, "files": ["C.java", "Shared.java"], "depends_on": []}]' | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/dep_graph.py"
```

The script handles:
- **File conflict detection**: tasks touching the same file are automatically serialized (lower ID first)
- **Topological sort**: Kahn's algorithm groups tasks into parallel execution layers
- **Cycle detection**: reports involved tasks if a cycle exists

Output:
```json
{"layers": [[1, 3], [2]], "conflicts": [{"tasks": [2, 3], "file": "Shared.java"}]}
```

If the output contains an `"error"` field (cycle detected), report the error to the user and ask how to resolve (remove a dependency, merge tasks, or restructure).

### Step 3: Display Execution Layers

Use the returned `layers` to display the execution plan to the user:

```
Execution Layers (max parallelism: 3):
  Layer 0: Task 1                       [1 task, serial]
  Layer 1: Task 2 | Task 4 | Task 6    [3 parallel]
  Layer 2: Task 3 | Task 5 | Task 7    [3 parallel]
  Layer 3: Task 8 | Task 9 | Task 10   [3 parallel]
  Layer 4: Task 12 | Task 13           [2 parallel]

  Estimated: 5 layers (vs 13 serial tasks)
```

If `conflicts` is non-empty, also display detected file conflicts so the user can verify the file-level serialization is correct.

### Max Parallelism

Default: **3** concurrent implementer subagents. Configurable via ecw.yml `impl_orchestration.max_parallelism`.

If a layer has more tasks than max parallelism, split into sub-layers (e.g., 5 tasks with max 3 → sub-layer A: 3 tasks, sub-layer B: 2 tasks).

### Serial Fallback

Fall back to fully serial execution (no worktree isolation) when:
- Dependency graph is a single chain (all tasks mutually dependent)
- Plan has ≤ 3 tasks (parallelism overhead exceeds benefit)
- User explicitly requests serial execution
- ecw.yml sets `impl_orchestration.parallel: false`

**Serial ≠ coordinator-direct.** Serial mode still dispatches implementer subagents — just one at a time without worktree isolation. The coordinator NEVER writes implementation code itself. This ensures ecw.yml `models` config is respected and hook enforcement (gateguard, verify-completion) applies consistently.

Announce: "Tasks are interdependent / few enough — using serial execution (subagent dispatch, no worktree)."

## Layer Execution

Execute one layer at a time. Each layer follows a 5-phase cycle.

### Phase 1: Parallel Implementation (worktree-isolated)

Dispatch ALL tasks in the current layer simultaneously. Each implementer runs in an isolated git worktree via the Agent tool's `isolation: "worktree"` parameter.

**Critical**: ALL Agent calls for the same layer MUST be in a **single message** to achieve true parallel execution. Sequential calls defeat the purpose.

```
# Example: Layer 1 with 3 tasks — single message, 3 Agent calls
Agent(
  description: "impl Task 2: Add inventory lock DTO",
  subagent_type: "ecw:implementer",
  isolation: "worktree",
  model: "sonnet",
  prompt: "<full task prompt with context>"
)
Agent(
  description: "impl Task 4: Add MQ consumer config",
  subagent_type: "ecw:implementer",
  isolation: "worktree",
  model: "haiku",
  prompt: "<full task prompt with context>"
)
Agent(
  description: "impl Task 6: Add lock service interface",
  subagent_type: "ecw:implementer",
  isolation: "worktree",
  model: "sonnet",
  prompt: "<full task prompt with context>"
)
```

Each implementer:
- Works in its own worktree (isolated filesystem)
- Commits changes to its worktree branch
- Returns: status, changed files list, commit summary

**Single-task layer optimization**: When a layer has only 1 task, skip worktree isolation — dispatch directly on the current branch. Avoids unnecessary merge overhead.

### Phase 2: Sequential Merge

After ALL implementers in the layer complete, for each worktree branch **in sequence**:

**Step 1 — Read result file (BEFORE merge):**

```bash
cat {worktree_path}/.claude/ecw/task-result.json
```

Read `./task-result-schema.md` for the full schema. This is the authoritative source for the Subagent Ledger; the Agent tool result text is secondary. If the file is missing:
- Fall back to `git log {worktree_branch}` to infer what was done
- Write `.claude/ecw/session-data/{wf-id}/task-{N}-aggregation-warning.md` to record the gap explicitly
- Continue merge (do not block the layer)

**Step 2 — Merge the branch:**

```bash
git merge <worktree-branch> --no-edit
```

**Merge order**: Merge largest changeset first (more context for subsequent merges).

**Conflict handling:**

| Scenario | Action |
|----------|--------|
| Clean merge | Continue to next branch |
| Conflict in test files only | Auto-resolve: keep both versions, fix imports/duplicates |
| Conflict in source files | This should be rare (file-conflict detection prevents it). Attempt auto-resolve → if fails: mark task for re-execution in a later serial pass |
| Merge fails completely | `git merge --abort`, move the failed task to an overflow serial layer at the end |

After all merges succeed, run a quick compile check (if configured in ecw.yml) to verify no integration issues.

### Phase 3: Parallel Spec Review

Dispatch spec reviewers for ALL layer tasks simultaneously. Reviews are read-only — no worktree needed:

```
# All spec reviews in a single message
Agent(description: "spec-review Task 2", subagent_type: "ecw:spec-reviewer", model: "sonnet", prompt: "...")
Agent(description: "spec-review Task 4", subagent_type: "ecw:spec-reviewer", model: "sonnet", prompt: "...")
Agent(description: "spec-review Task 6", subagent_type: "ecw:spec-reviewer", model: "sonnet", prompt: "...")
```

The reviewer reads actual code and verifies:
- Missing requirements
- Extra/unneeded work
- Misunderstandings

If issues found for any task:
1. Dispatch a **repair implementer subagent** (same `subagent_type: "ecw:implementer"`, same model as original implementer) with: the spec review findings + task context + "fix these issues only, do not re-implement". The coordinator MUST NOT edit source code directly — this bypasses ecw.yml models config and gateguard hook.
2. Re-review only the repaired tasks (dispatch spec reviewer again)
3. Max 3 rounds per task (see Loop Safety Controls)

**Spec reviewer timeout**: 120s. If reviewer times out, coordinator performs simplified spec check inline.

### Phase 4: Code Quality Review (P0 Only)

Read `./prompts/code-quality-review-template.md` for the P0 code quality review dispatch template and criteria.

### Phase 5: Complete Layer

- Mark all layer tasks complete via TaskUpdate
- **[MANDATORY] Update Subagent Ledger** in `session-state.md` — batch all layer tasks in a single Edit:
  - Data source: `task-result.json` (read in Phase 2 Step 1). If file was missing, use git log–inferred data and mark with `[inferred]` in the notes column
  - P0: record implementer + spec-reviewer + code-quality per task
  - P1: record implementer + spec-reviewer per task
  - Include worktree branch name in notes column for traceability
- Record layer timing: `Layer {N}: {task_count} tasks, {elapsed}s (parallel), merge {merge_time}s`
- Proceed to next layer

```yaml
- phase: "Task 2: Add DTO"
  agent: implementer
  type: general
  model: sonnet
  scale: medium
  started: "14:30"
  duration: "~45s"
- phase: "Task 2: Add DTO"
  agent: spec-reviewer
  type: general
  model: sonnet
  scale: small
  started: "14:31"
  duration: "~20s"
- phase: "Task 4: MQ config"
  agent: implementer
  type: general
  model: haiku
  scale: small
  started: "14:30"
  duration: "~30s"
- phase: "Task 4: MQ config"
  agent: spec-reviewer
  type: general
  model: sonnet
  scale: small
  started: "14:31"
  duration: "~18s"
```

## Implementer Prompt Construction

Read `./prompts/implementer-prompt-guide.md` for prompt construction guidelines, model selection, timeout rules, and implementer status handling.

## Loop Safety Controls

Guard against infinite loops and runaway costs. Read `./loop-safety-reference.md` for full rules.

Key limits: spec review max 3 rounds, code quality max 2 rounds, BLOCKED re-dispatch max 2, global budget 50 dispatches, stall detection at 6 dispatches per task. Exceed any limit → AskUserQuestion escalation.

## After All Tasks

**Do NOT dispatch a final code reviewer.** ECW uses `ecw:impl-verify` (4-Round multi-dimensional verification) which is more comprehensive.

After all tasks complete, invoke `ecw:impl-verify`. If a pending `ecw:impl-verify` task exists in TaskList, mark it `in_progress` first.

## Task Merging

If plan has many small tasks, consider merging per risk-classifier rules:
- Single-file + no conditional branch logic = can merge
- State machine / cross-domain / multi-file = must stay independent

Reference `workflow-routes.yml` `impl_strategy` section for authoritative rules. Do not redefine here.

## Error Handling

| Scenario | Handling |
|----------|---------|
| `task-result.json` missing after worktree merge | Fall back to `git log {worktree-branch}` to infer task result. Write `.claude/ecw/session-data/{wf-id}/task-{N}-aggregation-warning.md`. Mark Ledger entry with `[inferred]`. Continue processing — do not block the layer |
| Implementer subagent fails or returns empty | Record `FAILED` in Subagent Ledger → retry once with same model → still fails: escalate model (sonnet→opus) → still fails: notify user and mark task BLOCKED |
| Spec reviewer returns empty or malformed | Retry once → still fails: coordinator performs simplified spec check inline (verify file changes match task requirements) |
| Code quality reviewer fails (P0 only) | Retry once → still fails: skip code quality review for this task with `[Warning: code quality review unavailable for Task N]`, continue to next task. impl-verify Round 4 will catch quality issues |
| Implementer returns BLOCKED status | 1. Context problem → provide more context, re-dispatch 2. Task too complex → escalate model 3. Plan issue → AskUserQuestion to discuss with user. Max 2 re-dispatches per task, then escalate to user |
| Worktree merge conflict (unexpected) | Log as dependency graph miss. `git merge --abort`, move conflicting task to overflow serial layer at end |
| Multiple implementers fail in same layer | Merge successful ones, move failed ones to retry layer |
| Post-merge compile failure | Identify which merge introduced the issue (bisect last N merges). Fix inline or re-dispatch implementer for the offending task |
| Layer fully times out | Terminate remaining agents. Retry timed-out tasks with simplified scope. If still failing, escalate to user |

## Anti-Patterns

Read `./prompts/anti-patterns.md` for never-rules and common rationalizations to avoid.

## ecw.yml Configuration

```yaml
impl_orchestration:
  parallel: true                 # Enable parallel execution (default: true)
  max_parallelism: 3             # Max concurrent implementer subagents (default: 3)
  pre_check: true                # Run compile+test before first task (default: true)
  merge_compile_check: true      # Run compile check after each layer merge (default: true)
```

When `parallel: false`, the orchestrator uses the serial fallback mode throughout.

## Supplementary Files

- `process-diagram.md` — DOT visual overview of Setup → Per-Layer Cycle → impl-verify flow
- `loop-safety-reference.md` — Iteration limits, global budget, stall/error/timeout detection rules
- `prompts/implementer-prompt-guide.md` — Prompt construction, model selection, status handling
- `prompts/code-quality-review-template.md` — P0 code quality review dispatch template
- `prompts/anti-patterns.md` — Never rules + common rationalizations
- `task-result-schema.md` — Worktree result file schema, coordinator read protocol, missing-file fallback
