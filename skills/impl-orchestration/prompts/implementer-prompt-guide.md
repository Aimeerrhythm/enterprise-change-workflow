# Implementer Prompt Construction

Dispatch with `subagent_type: "ecw:implementer"` (base instructions auto-injected). Pass in `prompt`:
- Full task text (don't make subagent read plan file)
- Scene-setting context (where this fits, dependencies, what prior layers already built)
- ECW domain context (domain name, knowledge file paths, risk level)
- TDD requirement (if `tdd.enabled` in ecw.yml)
- Working directory
- **For worktree dispatch**: "You are in an isolated worktree. Implement, test, and commit. Your changes will be merged after review."
- **Completed layer context**: Briefly list what prior layers implemented (file names + one-line summary), so the implementer understands what already exists
- **Engineering rules** (if ecw.yml `rules.enabled: true`): Include in prompt: "Engineering rules are at `{rules.path}`. Read applicable rules before implementing. Your code will be verified against these rules in impl-verify Round 4."

## Model Selection and Timeout

| Task Type | Model | Timeout | Criteria |
|-----------|-------|---------|----------|
| Mechanical tasks | `model:` from `models.defaults.mechanical` (default: `"haiku"`) | 60s | 1-2 files, clear spec, no conditional branching (enum/constant definitions, DTO fields, config changes) |
| Integration/design tasks | `model:` from `models.defaults.implementation` (default: `"sonnet"`) | 180s | Multi-file coordination, judgment needed, business logic |
| Architecture tasks | `model:` from `models.defaults.analysis` (default: `"opus"`) | 300s | Cross-module structural decisions, complex state machines, deep reasoning required |

Default to `models.defaults.implementation` when classification is ambiguous.

**Agent-side execution limits** (enforced inside implementer.md): Implementer hard-stops at 100 tool calls and 15 source file reads. If a task is too large for these limits, split it before dispatching — do not rely on coordinator-side timeout alone.

If implementer times out, terminate and re-dispatch with simplified task scope or escalate model (see Error Handling in SKILL.md).

## Handle Implementer Status

**DONE:** Proceed to merge (parallel) or spec review (serial fallback).

**DONE_WITH_CONCERNS:** Read concerns. If about correctness/scope, address before review. If observations, note and proceed.

**NEEDS_CONTEXT:** Provide missing context and re-dispatch (in worktree mode, re-dispatch to same worktree path if possible; otherwise create new worktree).

**BLOCKED:** Assess:
1. Context problem → provide more context, re-dispatch
2. Task too hard → re-dispatch with more capable model
3. Task too large → break into smaller pieces
4. Plan wrong → use AskUserQuestion to discuss with user

**Re-dispatch limit**: Same task can be re-dispatched at most **2 times** after BLOCKED. If still BLOCKED after 2 re-dispatches, escalate to user via AskUserQuestion with full context of what was tried.

**Never** ignore escalation or force same model to retry without changes.
