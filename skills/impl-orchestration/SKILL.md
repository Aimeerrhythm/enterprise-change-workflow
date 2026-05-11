---
name: impl-orchestration
description: Use when executing implementation plans with independent tasks. Risk-aware subagent dispatch with per-task review.
---

# Implementation Orchestration

Execute plan by dispatching subagents per task in dependency-aware parallel layers, with risk-aware review gates.

**Core principle:** Dependency graph → parallel layers → worktree-isolated dispatch → merge → review = high quality, fast execution.

**Announce at start:** "Using ecw:impl-orchestration to execute the plan with parallel layer dispatch."

## When to Use

Use when:
- You have an implementation plan (from `ecw:writing-plans`)
- Tasks are mostly independent
- Auto-continue hook routes here based on `impl_strategy` conditions in `workflow-routes.yml`, OR Task count x risk level matches subagent-driven criteria

Don't use when:
- No plan exists (write one first)
- Tasks are tightly coupled (implement directly)
- P2 / P3 / simple changes (implement directly)

## Risk-Aware Review Depth

Read `.claude/ecw/session-data/{workflow-id}/session-state.json` for risk level. If unavailable (standalone invocation), default to P0 (full review depth).

| Risk Level | Per-task Spec Review | Per-task Code Quality Review | Post-impl |
|-----------|---------------------|----------------------------|-----------|
| **P0** | Mandatory | Mandatory (simplified inline) | ecw:impl-verify (full 4 Rounds) |
| **P1** | Mandatory | **Skip** (impl-verify Round 4 covers this) | ecw:impl-verify (full 4 Rounds) |

**Why P0 keeps code quality review:** Error cost at P0 is extreme. Catching issues per-task is cheaper than finding them across the full implementation.

## Process Overview

For a visual overview, see `./process-diagram.md`.

### Setup

1. **Read plan file once** — extract all tasks with full text
2. **Pre-flight check** — Read `./dep-graph-usage.md` § Pre-flight Check. Controlled by ecw.yml `impl_orchestration.pre_check` (default: true). Timeout 120s compile / 600s test. On failure: auto-fix → retry → ask user
3. **Build dependency graph** — Read `./dep-graph-usage.md` § Steps 1-3. Extract task metadata → call `dep_graph.py` → get parallel layers
4. **Create Tasks** — one TaskCreate per plan task, with dependency chain
5. **Display execution layers** — show user the parallel execution plan before starting

### Execution Mode

**Default: parallel** — max 3 concurrent implementer subagents (configurable: ecw.yml `impl_orchestration.max_parallelism`). Layers with more tasks than max are split into sub-layers.

**Serial fallback** when: dependency graph is a single chain, plan has ≤ 3 tasks, user requests serial, or ecw.yml `impl_orchestration.parallel: false`. Serial still dispatches implementer subagents (one at a time, no worktree) — coordinator NEVER writes implementation code itself.

## Layer Execution (5 Phases)

Execute one layer at a time.

### Phase 1: Parallel Implementation (worktree-isolated)

Read `./prompts/implementer-prompt-guide.md` for prompt construction, model selection, and timeout rules.

Dispatch ALL tasks in the current layer simultaneously via Agent tool with `isolation: "worktree"`. **All Agent calls for the same layer MUST be in a single message.**

```
Agent(
  description: "impl Task 2: Add inventory lock DTO",
  subagent_type: "ecw:implementer",
  isolation: "worktree",
  model: "sonnet",
  prompt: "<full task prompt with context>"
)
```

Each implementer works in its own worktree, commits changes, writes `task-result.json`.

**Single-task layer**: skip worktree isolation — dispatch directly on current branch.

### Phase 2: Sequential Merge

After ALL implementers complete, for each worktree branch in sequence:

1. Read `{worktree_path}/.claude/ecw/task-result.json` — see `./task-result-schema.md` for schema and fallback protocol
2. `git merge <worktree-branch> --no-edit` (merge largest changeset first)

| Conflict type | Action |
|---------------|--------|
| Clean merge | Continue |
| Test files only | Auto-resolve: keep both, fix imports |
| Source files | Attempt auto-resolve → fails: move task to overflow serial layer |
| Merge fails | `git merge --abort`, move to overflow layer |

After all merges: run compile check if ecw.yml `impl_orchestration.merge_compile_check: true`.

### Phase 3: Parallel Spec Review

Dispatch spec reviewers for ALL layer tasks simultaneously (single message, `subagent_type: "ecw:spec-reviewer"`, `model: "sonnet"`, timeout 120s). Same parallel dispatch pattern as Phase 1.

If issues found: dispatch repair implementer → re-review. Max 3 rounds per task (see `./loop-safety-reference.md`).

### Phase 4: Code Quality Review (P0 Only)

Read `./prompts/code-quality-review-template.md` for dispatch template. Max 2 rounds per task.

### Phase 5: Complete Layer

- Mark all layer tasks complete via TaskUpdate
- Record layer timing
- Proceed to next layer

## After All Tasks

**Do NOT dispatch a final code reviewer.** Invoke `ecw:impl-verify` (4-Round verification). If a pending impl-verify Task exists, mark it `in_progress` first.

## Task Merging

If plan has many small tasks, consider merging. See `workflow-routes.yml` `impl_strategy` section for authoritative rules.

## Loop Safety Controls

Read `./loop-safety-reference.md` for full rules. Key limits: spec review max 3 rounds, code quality max 2 rounds, BLOCKED re-dispatch max 2, global budget 50 dispatches, stall detection at 6 dispatches per task.

## Error Handling

| Scenario | Handling |
|----------|---------|
| `task-result.json` missing | Fall back to `git log` inference, write aggregation warning, continue |
| Implementer fails or empty | Retry once → escalate model → still fails: notify user, mark BLOCKED |
| Spec reviewer fails | Retry once → still fails: coordinator performs simplified spec check inline |
| Code quality reviewer fails (P0) | Retry once → still fails: skip with warning, impl-verify Round 4 catches issues |
| Implementer returns BLOCKED | Provide context → escalate model → still blocked after 2 re-dispatches: ask user |
| Unexpected merge conflict | `git merge --abort`, move task to overflow serial layer |
| Multiple implementers fail | Merge successful ones, move failed to retry layer |
| Post-merge compile failure | Bisect last N merges, fix or re-dispatch offending task |

## ecw.yml Configuration

```yaml
impl_orchestration:
  parallel: true                 # Enable parallel execution (default: true)
  max_parallelism: 3             # Max concurrent implementer subagents (default: 3)
  pre_check: true                # Run compile+test before first task (default: true)
  merge_compile_check: true      # Run compile check after each layer merge (default: true)
```

## Supplementary Files

- `process-diagram.md` — Visual overview of Setup → Per-Layer Cycle → impl-verify
- `dep-graph-usage.md` — Dependency graph construction details + pre-flight check procedure
- `loop-safety-reference.md` — Iteration limits, global budget, stall/error/timeout detection
- `prompts/implementer-prompt-guide.md` — Prompt construction, model selection, status handling
- `prompts/code-quality-review-template.md` — P0 code quality review dispatch template
- `prompts/anti-patterns.md` — Never rules + common rationalizations
- `task-result-schema.md` — Worktree result file schema, coordinator read protocol
