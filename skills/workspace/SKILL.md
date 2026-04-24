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

**Output language**: Read `ecw.yml` → `project.output_language`. All user-facing text follows this language. If unavailable, detect from user's input language. Pass `output_language` to every dispatched agent prompt.

**Core principle:** Workspace = infrastructure (git worktree), Coordinator = orchestration (Phase-Gate flow), per-service ECW = execution (unchanged). Three layers, orthogonal.

**Announce at start:** "Using ecw:workspace to [create workspace / coordinate cross-service development / ...]."

**Mode switch**: Update session-state.md MODE marker to `analysis` (during Phase 1-3) or `implementation` (during Phase 4).

## Trigger

- **Manual only**: `/ecw:workspace create|run|status|push|destroy`
- This Skill is NOT auto-triggered by risk-classifier. User explicitly invokes it when cross-repo development is needed.

## When to Use

Use when:
- User needs to develop across 2+ independent git repositories simultaneously
- Cross-service changes with interface dependencies (Dubbo, MQ)
- Need coordinated implementation with contract alignment

Don't use when:
- Single-repo multi-module change (use standard ECW flow: risk-classifier → ...)
- Services are in a monorepo (use ecw:domain-collab instead)
- Pure read-only analysis (no implementation needed)

## Sub-commands

| Sub-command | Usage | Description |
|-------------|-------|-------------|
| `create` | `/ecw:workspace create <services...> [--name] [--branch]` | Create workspace + auto-enter + start run |
| `run` | `/ecw:workspace run "<requirement>"` | 6-Phase coordinator flow (usually auto-triggered by create) |
| `status` | `/ecw:workspace status` | All services' git + session status |
| `push` | `/ecw:workspace push` | Batch push with confirmation |
| `destroy` | `/ecw:workspace destroy` | Clean up worktrees + directory |

**One-command flow**: `create` captures the requirement from user's input, creates the workspace, then automatically opens a new session in the workspace and starts `run`. User only needs to describe the requirement once.

For `create`, `status`, `push`, `destroy` details, see `./lifecycle-commands.md`.

---

## Sub-command: run — Phase-Gate Coordinator Flow

### Prerequisites

- Must be in workspace root (`.claude/ecw/workspace.yml` exists)
- Read workspace.yml → service list

### Phase-Gate Architecture

Every Phase produces a mandatory artifact. Next Phase MUST verify it exists. No skipping.

```
Pre-flight → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
    │            │          │          │          │          │          │
    ▼            ▼          ▼          ▼          ▼          ▼          ▼
[user OK]  [plan draft] [plan+contracts] [task.md] [status.json] [verified] [pushed]
```

| Phase | Gate Artifact | Location |
|-------|--------------|----------|
| Pre-flight | User confirms readiness | interactive |
| Phase 1 | `cross-service-plan.md` (draft) | `session-data/{wf-id}/` |
| Phase 2 | `cross-service-plan.md` (final: has `## Interface Contracts` + `## Execution Order`) | `session-data/{wf-id}/` |
| Phase 3 | `workspace-task.md` per service | `{service}/.claude/ecw/` |
| Phase 4 | `status.json` per service | `{service}/` |
| Phase 5 | All compatibility checks pass | interactive |

**Enforcement**: At each Phase start, verify previous artifact exists. Missing → STOP, do not backfill silently.

---

### Pre-flight: ECW Readiness Check

```
Gate-in: workspace.yml readable
Process:
  For each service:
    Check {service}/.claude/ecw/ecw.yml and {service}/.claude/knowledge/
    Classify: ECW-ready / ECW-partial / ECW-absent

  AskUserQuestion: show readiness table.
  If any ECW-absent → Options: "Continue with source scan" / "Pause to init ECW"
Gate-out: User confirms
```

---

### Phase 1: Requirement Analysis + Draft Plan

```
Gate-in: Pre-flight confirmed
Process:
  1. Spawn one Explore Agent per service in SINGLE message (parallel).
     Each agent scans its directory:
       ECW-ready → read knowledge files first, code for gaps
       ECW-absent → scan source code directly
     Output (YAML): existing_interfaces, relevant_code, suggested_changes

  2. Collect results. Coordinator synthesizes:
     - Per-service scope
     - Cross-service dependencies (Provider/Consumer)

  3. AskUserQuestion: present scope summary, user confirms or corrects

  4. Write cross-service-plan.md DRAFT to session-data/{wf-id}/

  5. Update Subagent Ledger in session-state.md:
     | Phase 1 | Explore({svc}) | Explore | sonnet | — | HH:mm | Xs | per-service scan |
Gate-out: cross-service-plan.md exists
```

---

### Phase 2: Contract Definition + Plan Finalization

```
Gate-in: cross-service-plan.md draft exists
Process:
  1. Define precise contracts from Phase 1 analysis:
     - Dubbo: provider service, interface, method, current → new signature
     - MQ: producer service, topic, DTO class + fields
     - Maven: consumer service, API Jar, version change

  2. Determine execution order:
     Layer 1: Provider services (complete + mvn install before Layer 2)
     Layer 2: Consumer services (parallel)

  3. Update cross-service-plan.md → FINAL version (add contracts + execution order)
Gate-out: cross-service-plan.md has "## Interface Contracts" and "## Execution Order"
```

---

### Phase 3: User Confirmation + Task Distribution

```
Gate-in: cross-service-plan.md finalized
Process:
  1. AskUserQuestion: present full plan (scope, contracts, execution order).
     Options: "Confirm" / "Modify"
     Modify → update plan → re-present (loop until confirmed)

  2. Once confirmed, write workspace-task.md for EACH service:
     Location: {service}/.claude/ecw/workspace-task.md
     Contents:
       - Service's implementation scope
       - Relevant interface contracts
       - Concrete instructions (files, methods)
       - Completion protocol (write status.json)
       - "Do NOT re-analyze requirements — task is pre-planned"

  3. Verify: check workspace-task.md exists for every service before proceeding.
Gate-out: workspace-task.md exists for ALL services
```

---

### Phase 4: Multi-Session Parallel Implementation

```
Gate-in: workspace-task.md exists for ALL services
Process:
  Per layer in execution order:
    1. Open terminal split/tab per service (see ./terminal-adapters.md)
       Paste command (clipboard, not keystroke):
       cd {ws}/{svc} && claude "Read .claude/ecw/workspace-task.md and execute.
       Implement, test, run ecw:impl-verify. Write status.json when done."
       --name {svc}-worker --permission-mode acceptEdits

    2. Poll status.json per service (see ./coordination-protocol.md)

    3. Layer complete:
       - Failed → AskUserQuestion: retry / skip / abort
       - Provider layer + maven_action → mvn install/deploy
       - Proceed to next layer
Gate-out: status.json exists for ALL services
```

---

### Phase 5: Cross-Service Verification

```
Gate-in: ALL status.json exist
Process:
  Per-service impl-verify already ran in child sessions.
  Coordinator checks cross-service compatibility:
    a. Dubbo: Provider interface signature = Consumer call signature
    b. MQ: Producer DTO fields = Consumer DTO fields
    c. Maven: Consumer pom.xml API Jar version = Provider version

  All pass → proceed. Issues → present to user, suggest fixes.
Gate-out: Compatibility checks pass (or user accepts known issues)
```

---

### Phase 6: Summary & Push Confirmation

```
Gate-in: Phase 5 passed
Process:
  1. Aggregate status.json + git log per service
  2. Present summary: commits, files, deploy order
  3. AskUserQuestion: Push now or later?
Gate-out: Workflow complete
```

---

## Error Handling

| Scenario | Handling |
|----------|---------|
| Child session fails (status: failed) | Report, ask: retry / skip / abort |
| Child session blocked | Report, user resolves in split pane |
| Contract mismatch (Phase 3) | Present diff, user adjusts plan |
| Cross-service verification fails (Phase 5) | Present findings, suggest fix |
| Terminal adapter fails | Fall back to manual adapter |
| Polling timeout (30 min) | Notify, offer: continue / skip / abort |
| Maven install/deploy fails | Report, user fixes manually |

## Never Rules

- **Never skip Phase gates** — artifact must exist before next Phase
- **Never run Phase 4 before Phase 3** — unaligned contracts waste implementation
- **Never skip contract alignment** — single param mismatch breaks Consumer
- **Never use `keystroke` on macOS** — clipboard paste only (input method corruption)
- **Never assume terminal type** — detect or fall back to manual
- **Never run Provider + Consumer layers in parallel** — Consumer depends on Provider's API Jar

## Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "Services are independent, skip contract alignment" | Cross-service changes always have contracts. That's why you need a workspace. |
| "Provider API Jar hasn't changed, Consumer can start" | DTO may have new fields. Always complete Provider layer first. |
| "Terminal adapter failed, use subagents instead" | Subagents can't interact with user or show progress. Fall back to manual adapter. |
| "Phase 1 draft is good enough, skip Phase 2 finalization" | Without precise contracts (exact signatures, DTO fields), implementation will diverge between services. |
| "Only one service needs changes, dispatch directly" | Still write cross-service-plan.md — it's the gate artifact. Future Phases depend on it. |

## Supplementary Files

- `./lifecycle-commands.md` — create / status / push / destroy detailed process
- `./terminal-adapters.md` — Terminal detection + adapter implementations (Ghostty, iTerm2, tmux, manual)
- `./coordination-protocol.md` — status.json schema, polling mechanism, artifact locations
