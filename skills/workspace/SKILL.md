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

All coordinator-written files (cross-service-plan.md, workspace-analysis-task.md, confirmed-contract.md, session-state.md) must use this language for all headings, labels, and descriptive text. Pass `output_language` value explicitly in every dispatched child session prompt and in workspace-analysis-task.md.

**File encoding**: All files written by coordinator or child sessions must use native UTF-8 characters. Never use Unicode escape sequences (uXXXX or \uXXXX format) for any characters including Chinese. Write characters directly as-is.

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
- Read workspace.yml → service list + original requirement

### Phase-Gate Architecture

```
Pre-flight → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
    │            │          │          │          │          │          │
    ▼            ▼          ▼          ▼          ▼          ▼          ▼
[user OK]  [biz-plan]  [analysis]  [contract]  [status]  [verified]  [pushed]
```

| Phase | Gate Artifact | Written by | Location |
|-------|--------------|------------|----------|
| Pre-flight | User confirms readiness | — | interactive |
| Phase 1 | `cross-service-plan.md` (business layer only) | Coordinator | `session-data/{wf-id}/` |
| Phase 2 | `analysis-report.md` per service | Child sessions | `{service}/.claude/ecw/session-data/{wf-id}/` |
| Phase 3 | `confirmed-contract.md` per service | Coordinator | `{service}/.claude/ecw/session-data/{wf-id}/` |
| Phase 4 | `status.json` per service | Child sessions | `{service}/.claude/ecw/session-data/{wf-id}/` |
| Phase 5 | Compatibility checks pass | Coordinator | interactive |

**Enforcement**: At each Phase start, verify previous artifact exists. Missing → STOP, report — do not backfill silently.

---

### Pre-flight: ECW Readiness Check

```
Gate-in: workspace.yml readable
Process:
  For each service:
    Check {service}/.claude/ecw/ecw.yml and {service}/.claude/knowledge/
    Classify: ECW-ready / ECW-partial / ECW-absent

  AskUserQuestion: show readiness table (language follows output_language).
  If any ECW-absent → Options: "Continue with source scan" / "Pause to init ECW"
Gate-out: User confirms
          Write initial session-state.md:
            Location: .claude/ecw/session-data/{wf-id}/session-state.md
            Content: Pre-flight → ✅ 完成; all subsequent phases → ⏳ 待开始
```

---

### Phase 1: Business Decomposition (Coordinator only, NO code analysis)

**Information constraint**: Phase 1 uses ONLY `workspace.yml.requirement` text and the user's stated business context. No code reading of any kind is permitted — no Read, Bash, Glob, Grep, or Explore tools. If code-level detail is needed to answer a question, that question is an Open Question for Phase 2, not something to resolve here.

**Output standard**: cross-service-plan.md and workspace-analysis-task.md must contain ONLY business-level content — service roles, interaction types, open questions. Any class name, method name, field name, or SQL in Phase 1 output is a violation.

```
Gate-in: Pre-flight confirmed
Process:
  1. Read workspace.yml → original requirement + service list
     (This is the ONLY information source for Phase 1)

  2. Decompose requirement from pure business perspective:
     - What is each service responsible for in this change?
     - Which services are Provider (data/event source) vs Consumer?
     - What cross-service interaction is needed? (MQ / Dubbo / unclear)
     If interaction type cannot be determined from the requirement alone → mark as "unclear",
     Phase 2 child session will investigate. Do NOT read code to guess.

  3. AskUserQuestion: present per-service business responsibilities.
     For each service show:
       - Role (Provider / Consumer / Both)
       - Business responsibility (1-2 sentences, business language only)
       - Interaction type (Dubbo / MQ / unclear — flag for Phase 2)
     Options: "Confirm" / "Adjust"

  4. Once confirmed, write cross-service-plan.md (business layer only):
     Location: .claude/ecw/session-data/{wf-id}/cross-service-plan.md
     Content: per-service roles, interaction patterns, open questions for Phase 2
     Encoding: native UTF-8, no escape sequences

  5. Write workspace-analysis-task.md for each service:
     Location: {service}/.claude/ecw/session-data/{wf-id}/workspace-analysis-task.md
     Content (see template below)
     Encoding: native UTF-8, no escape sequences

  6. Update session-state.md:
     - Phase 1 row → ✅ 完成
     - Subagent Ledger: record Explore agents as complete
     (This step is mandatory — gate-out verifies it)

Gate-out: ALL of the following must be true:
  - cross-service-plan.md exists at session-data/{wf-id}/
  - workspace-analysis-task.md exists for all services
  - session-state.md Phase 1 row = ✅ 完成
```

**workspace-analysis-task.md template:** See `./workspace-analysis-task-template.md` (Read on demand when writing workspace-analysis-task.md for each service).

---

### Phase 2: Per-Service Code Analysis (Child sessions, interactive, parallel)

```
Gate-in: workspace-analysis-task.md exists for all services at .claude/ecw/session-data/{wf-id}/
         Self-check: if session-state.md Phase 1 ≠ ✅ 完成 → update it now before proceeding
Process:
  1. Generate per-service start scripts and open one terminal tab per service
     via terminal adapter (see ./terminal-adapters.md § Service Scripts)

     Script name: start-{svc}.sh
     Script prompt: "Read .claude/ecw/session-data/{wf-id}/workspace-analysis-task.md and follow all instructions."
     Flags: --name {svc}-analyst --permission-mode bypassPermissions

  2. Child sessions run in parallel (interactive — user can observe and intervene):
     Each session follows workspace-analysis-task-template.md: analysis → poll contract → impl.
     Session behavior details are in the template; coordinator only monitors artifacts.

  3. Poll for completion: check {service}/.claude/ecw/session-data/{wf-id}/analysis-report.md
     every 5 seconds

  4. Coordinator reads all analysis-report.md files

  5. Update session-state.md:
     - Phase 2 row → ✅ 完成
     - Subagent Ledger: record analyst child sessions as complete

Gate-out: ALL of the following must be true:
  - analysis-report.md exists for all services at .claude/ecw/session-data/{wf-id}/
  - session-state.md Phase 2 row = ✅ 完成
```

---

### Phase 3: Contract Alignment + Conflict Resolution

```
Gate-in: analysis-report.md exists for all services at .claude/ecw/session-data/{wf-id}/
         Self-check: if session-state.md Phase 2 ≠ ✅ 完成 → update it now before proceeding
Process:
  1. Cross-validate for conflicts:

     a. MQ contracts:
        Producer's topic name / DTO fields ↔ Consumer's expected topic / DTO fields
     b. Dubbo contracts:
        Provider's interface signature ↔ Consumer's expected call signature
     c. Interaction pattern conflicts:
        Service A wants sync Dubbo ↔ Service B prefers async MQ
     d. Responsibility boundary conflicts:
        Both/neither claim ownership of shared logic

  2. If conflicts found → AskUserQuestion per conflict (language follows output_language):
     Present:
       - Which services disagree
       - Each side's reasoning
       - Option A / Option B / Option C (custom)
     User decides → coordinator records decision

  3. Once all contracts aligned:
     - Update cross-service-plan.md with final contracts
     - Write confirmed-contract.md for EACH affected service:
       Location: {service}/.claude/ecw/session-data/{wf-id}/confirmed-contract.md
       Encoding: native UTF-8, no escape sequences
       Content scope — ONLY cross-service contract layer:
         - field names, field types, nullable annotations
         - topic names / interface signatures
         - interaction_pattern (mq / dubbo) for Phase 4 dispatch logic
         - execution order (layer assignment)
         - impl-verify requirement: "impl-verify MUST pass before writing status.json"
       Content exclusion — do NOT include:
         - class names, method names, internal implementation entry points
           (these are in analysis-report.md, owned by child sessions)
         - task decomposition or implementation steps
           (child sessions own this via ecw:writing-plans)

  4. Update session-state.md:
     - Phase 3 row → ✅ 完成

Gate-out: ALL of the following must be true:
  - confirmed-contract.md exists for all services at .claude/ecw/session-data/{wf-id}/
  - session-state.md Phase 3 row = ✅ 完成
```
### Phase 4: Per-Service Implementation (analysis sessions continue, parallel or layered)

```
Gate-in: confirmed-contract.md exists for all services at .claude/ecw/session-data/{wf-id}/
         Self-check: if session-state.md Phase 3 ≠ ✅ 完成 → update it now before proceeding
Process:
  Analysis sessions detect confirmed-contract.md via polling and continue into Phase 4 automatically.
  Coordinator does NOT generate new Phase 4 scripts — no user action needed at this phase.
  Child session behavior (MQ parallel / Dubbo non-blocking scheduling) is defined in
  workspace-analysis-task-template.md — coordinator does not need to manage dispatch.

  Poll: check {service}/.claude/ecw/session-data/{wf-id}/status.json every 5 seconds,
        timeout 30 minutes.
  Failed -> AskUserQuestion: retry / skip / abort

  After all status.json received:
  Update session-state.md:
    - Phase 4 row → ✅ 完成
    - Subagent Ledger: update service child sessions (same sessions from Phase 2) to complete

Gate-out: ALL of the following must be true:
  - status.json exists for all services at .claude/ecw/session-data/{wf-id}/
  - session-state.md Phase 4 row = ✅ 完成
```

### Phase 5: Cross-Service Verification

```
Gate-in: status.json exists at {service}/.claude/ecw/session-data/{wf-id}/ for all services
         Self-check: if session-state.md Phase 4 ≠ ✅ 完成 → update it now before proceeding
Process:
  Each service's ecw:impl-verify already ran inside child sessions.
  Coordinator performs additional cross-service checks:

  MQ checks:
    a. Producer DTO field name = Consumer DTO field name (exact match)
    b. Producer DTO field type = Consumer DTO field type (e.g. String ↔ String)
    c. Nullable annotation consistent (both nullable or both required)
    d. Topic name: Producer publish topic = Consumer subscribe topic

  Dubbo checks:
    a. Provider interface method signature = Consumer call signature
       (method name, parameter types, return type, exception declarations)
    b. Maven: Consumer pom.xml API Jar version = Provider published version

  All pass → proceed. Issues → present findings, suggest which service to fix.

  Update session-state.md:
    - Phase 5 row → ✅ 完成

Gate-out: All checks pass (or user accepts known issues)
          session-state.md Phase 5 row = ✅ 完成
```

---

### Phase 6: Summary & Push Confirmation

```
Gate-in: Phase 5 passed
         Self-check: if session-state.md Phase 5 ≠ ✅ 完成 → update it now before proceeding
Process:
  1. Aggregate status.json + git log per service
  2. Present summary:
     - Commits, files changed per service
     - Deploy order (from confirmed-contract.md)
     - ECW coverage per service: ECW-ready (full flow) or ECW-absent (impl-verify only)
  3. AskUserQuestion: Push now or later?
  4. Knowledge tracking: For ECW-ready services, /ecw:knowledge-track is auto-invoked
     by impl-verify on pass. Report which services completed
     knowledge-track and which skipped it (ECW-absent services skip by design).
  5. Update session-state.md:
     - Phase 6 row → ✅ 完成
     - MODE → complete
Gate-out: Workflow complete
```

**Session-state Phase naming note** (Issue 8):
coordinator's session-state.md Phase Status table must use SKILL.md Phase numbers (1-6).
Do not invent custom phase names. If coordinator compresses Phase 1-3 into fewer steps,
annotate the Artifact column to explain (e.g. "Phase 1+2+3 compressed — code-free business decomp only").

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

## Anti-Patterns

Read `./prompts/anti-patterns.md` for never-rules and common rationalizations to avoid.

## Supplementary Files

- `./lifecycle-commands.md` — create / status / push / destroy detailed process
- `./terminal-adapters.md` — Terminal detection + adapter implementations (Ghostty, iTerm2, tmux, manual)
- `./coordination-protocol.md` — status.json / api-ready.json schema, polling mechanism, artifact locations
- `./workspace-analysis-task-template.md` — Child session task template (analysis → impl full flow)
- `./prompts/anti-patterns.md` — Never rules + common rationalizations
