---
name: workspace
description: |
  Multi-repo workspace for cross-service development. Create isolated workspaces with git worktree,
  coordinate multi-session parallel implementation across independent services.
  Manual invocation only via /ecw:workspace.
argument-hint: create <services...> | run "<requirement>" | status | push | destroy
---

# Workspace — Multi-Repo Cross-Service Development

Manage cross-service workspaces and coordinate multi-session parallel development. Each service runs its own independent ECW flow; this Skill handles workspace lifecycle and master coordination.

**Output language**: Read `output_language` for the workspace session:
1. Try any ECW-ready service's `.claude/ecw/ecw.yml` → `project.output_language`
2. Fallback: `workspace.yml` → `output_language`
3. Fallback: detect from user's input language

All coordinator-written files must use this language for headings, labels, and descriptive text. Pass `output_language` explicitly in every dispatched child session prompt.

**File encoding**: All files must use native UTF-8 characters. Never use Unicode escape sequences.

**Core principle:** Workspace = infrastructure (git worktree), Coordinator = orchestration (Phase-Gate flow), per-service ECW = execution (unchanged). Three layers, orthogonal.

**Announce at start:** "Using ecw:workspace to [create workspace / coordinate cross-service development / ...]."

## When to Use

Use when:
- User needs to develop across 2+ independent git repositories simultaneously
- Cross-service changes with interface dependencies (Dubbo, MQ)
- Need coordinated implementation with contract alignment

Don't use when:
- Single-repo multi-module change (use standard ECW flow)
- Services are in a monorepo (use ecw:domain-collab instead)
- Pure read-only analysis (no implementation needed)

## Sub-commands

| Sub-command | Usage | Description |
|-------------|-------|-------------|
| `create` | `/ecw:workspace create <services...> [--name] [--branch]` | Create workspace + auto-enter + start run |
| `run` | `/ecw:workspace run "<requirement>"` | 6-Phase coordinator flow |
| `status` | `/ecw:workspace status` | All services' git + session status |
| `push` | `/ecw:workspace push` | Batch push with confirmation |
| `destroy` | `/ecw:workspace destroy` | Clean up worktrees + directory |

**One-command flow**: `create` captures the requirement, creates workspace, opens new session, starts `run` automatically. Manual only — not auto-triggered by risk-classifier.

For `create`, `status`, `push`, `destroy` details, see `./lifecycle-commands.md`.

---

## Sub-command: run — Phase-Gate Coordinator Flow

### Prerequisites

- Must be in workspace root (`.claude/ecw/workspace.yml` exists)
- Read workspace.yml → service list + original requirement

### Phase-Gate Architecture

```
Pre-flight → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
```

| Phase | Gate Artifact | Written by | Location |
|-------|--------------|------------|----------|
| Pre-flight | User confirms readiness | — | interactive |
| 1. Initial decomposition | `cross-service-plan.md` | Coordinator | `session-data/{wf-id}/` |
| 2. Per-service analysis | `analysis-report.md` per service | Child sessions | `{service}/.claude/ecw/session-data/{wf-id}/` |
| 3. Contract alignment | `confirmed-contract.md` per service | Coordinator | `{service}/.claude/ecw/session-data/{wf-id}/` |
| 4. Per-service impl | `status.json` per service | Child sessions | `{service}/.claude/ecw/session-data/{wf-id}/` |
| 5. Cross-service verify | Checks pass | Coordinator | interactive |
| 6. Summary & push | `session-state.json` (MODE: complete) | Coordinator | `session-data/{wf-id}/` |

**Enforcement**: At each Phase start (gate-in), verify previous artifact exists. Missing → STOP, report — do not backfill silently.

**Session-state convention**: After each Phase completes, update `session-state.json` to reflect completion. Use SKILL.md Phase numbers (1-6), do not invent custom names.

---

### Pre-flight: ECW Readiness Check

For each service, check `{service}/.claude/ecw/ecw.yml` and `{service}/.claude/knowledge/`. Classify: ECW-ready / ECW-partial / ECW-absent.

AskUserQuestion: show readiness table. If any ECW-absent → offer "Continue with source scan" / "Pause to init ECW".

Gate-out: User confirms. Write initial `session-state.json` to `.claude/ecw/session-data/{wf-id}/`.

---

### Phase 1: Initial Decomposition (code-free)

**Information constraint**: Use ONLY `workspace.yml.requirement` text and user's stated context. **No code reading** — no Read, Bash, Glob, Grep, or Explore tools. Code-level detail → mark as Open Question for Phase 2.

**Output standard**: cross-service-plan.md must contain ONLY business-level content (service roles, interaction types, open questions). Any class/method/field name or SQL is a violation.

Process:
1. Read workspace.yml → requirement + service list (ONLY information source)
2. Decompose from pure business perspective: per-service responsibilities, Provider/Consumer roles, interaction type (Dubbo / MQ / unclear)
3. AskUserQuestion: present per-service business responsibilities for confirmation
4. Write `session-data/{wf-id}/cross-service-plan.md`
5. Write `{service}/.claude/ecw/session-data/{wf-id}/workspace-analysis-task.md` per service — see `./workspace-analysis-task-template.md` for template

Gate-out: cross-service-plan.md + all workspace-analysis-task.md exist.

---

### Phase 2: Per-Service Code Analysis (parallel, interactive)

Generate per-service start scripts and open terminal tabs via `./terminal-adapters.md` § Service Scripts.

Child sessions follow workspace-analysis-task-template.md: analysis → poll contract → impl. Coordinator only monitors artifacts.

Poll: check `{service}/.claude/ecw/session-data/{wf-id}/analysis-report.md` every 5 seconds.

Gate-out: analysis-report.md exists for all services.

---

### Phase 3: Contract Alignment + Conflict Resolution

Cross-validate analysis reports for conflicts:
- MQ: Producer topic/DTO ↔ Consumer expected topic/DTO
- Dubbo: Provider interface signature ↔ Consumer expected signature
- Interaction pattern conflicts (sync vs async)
- Responsibility boundary conflicts

Conflicts found → AskUserQuestion per conflict, user decides.

Once aligned:
- Update cross-service-plan.md with final contracts
- Write `{service}/.claude/ecw/session-data/{wf-id}/confirmed-contract.md` per service

Read `./coordination-protocol.md` for confirmed-contract.md content scope and exclusion rules.

**Content scope** — ONLY cross-service contract layer: field names/types, topic names/interface signatures, interaction_pattern, execution order, impl-verify requirement. Do NOT include class names, method names, multiple implementation options, implementation steps, or "A or B" choices.

Gate-out: confirmed-contract.md exists for all services.

---

### Phase 4: Per-Service Implementation (parallel or layered)

Child sessions detect confirmed-contract.md via polling and continue into Phase 4 automatically. Coordinator does NOT generate new scripts — no user action needed.

Poll: check `{service}/.claude/ecw/session-data/{wf-id}/status.json` every 5 seconds, timeout 120 minutes. See `./coordination-protocol.md` for status.json schema and timeout handling.

Failed/timeout → AskUserQuestion: continue waiting / skip / abort.

Gate-out: status.json exists for all services with required fields (service, status, summary, files_changed, commits, error).

---

### Phase 5: Cross-Service Verification

Each service's ecw:impl-verify already ran inside child sessions. Coordinator performs cross-service checks:

**MQ**: field names match, field types match, nullable annotations consistent, topic names match.

**Dubbo**: method signatures match (name, params, return type, exceptions). Run the deterministic version-consistency check (do NOT grep manually):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cross-service-verify.py" "{workspace_path}" "{wf-id}"
```

The script reads every Provider's `api-ready.json` `modules[]` and verifies each Consumer pom's dependency on a published artifactId pins the SNAPSHOT version. Exit code 0 = all PASS, 1 = at least one FAIL, 2 = invocation error. Output is a JSON report with per-check status (PASS/FAIL/SKIP) — SKIP means the version was an unresolved `${property}` and needs manual review.

FAIL = HARD FAIL: typically a version-pollution bug where Consumer pom still references the original release version while Provider only published a SNAPSHOT.

All pass → proceed. Issues → present findings, suggest which service to fix.

Gate-out: All checks pass (or user accepts known issues).

---

### Phase 6: Summary & Push Confirmation

1. Aggregate status.json + git log per service
2. Present summary: commits, files changed, deploy order, ECW coverage per service
3. AskUserQuestion: Push now or later?

Gate-out: Workflow complete, session-state MODE → complete.

---

## Error Handling

| Scenario | Handling |
|----------|---------|
| Child session fails | Report, ask: retry / skip / abort |
| Child session blocked | Report, user resolves in split pane |
| Contract mismatch (Phase 3) | Present diff, user adjusts |
| Cross-service verification fails | Present findings, suggest fix |
| Terminal adapter fails | Fall back to manual adapter |
| Polling timeout (120 min) | Notify, offer: continue / skip / abort |

## Anti-Patterns

Read `./prompts/anti-patterns.md` for never-rules and common rationalizations.

## Supplementary Files

- `./lifecycle-commands.md` — create / status / push / destroy detailed process
- `./terminal-adapters.md` — Terminal detection + adapter implementations
- `./coordination-protocol.md` — status.json / api-ready.json schema, polling mechanism, artifact locations
- `./workspace-analysis-task-template.md` — Child session task template
- `./prompts/anti-patterns.md` — Never rules + common rationalizations
