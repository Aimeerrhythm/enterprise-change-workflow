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
| Phase 2 | `analysis-report.md` per service | Child sessions | `{service}/.claude/ecw/` |
| Phase 3 | `confirmed-contract.md` per service | Coordinator | `{service}/.claude/ecw/` |
| Phase 4 | `status.json` per service | Child sessions | `{service}/` |
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
```

---

### Phase 1: Business Decomposition (Coordinator only, NO code analysis)

```
Gate-in: Pre-flight confirmed
Process:
  1. Read workspace.yml → original requirement + service list
  2. Coordinator decomposes requirement purely from business perspective:
     - What is each service responsible for?
     - Which services are Provider (data/event source) vs Consumer?
     - What cross-service interactions are needed?
     - What interaction patterns are involved? (Dubbo / MQ / both)
     NOTE: Do NOT read any service code in this phase.
           Ambiguous interaction patterns should be explicitly flagged, not guessed.

  3. AskUserQuestion: present per-service business responsibilities.
     For each service show:
       - Role (Provider / Consumer / Both)
       - Business responsibility (1-2 sentences)
       - Interaction type (Dubbo / MQ / unclear — flag for Phase 2)
     Options: "Confirm" / "Adjust"

  4. Once confirmed, write cross-service-plan.md (business layer):
     Location: .claude/ecw/session-data/{wf-id}/cross-service-plan.md
     Content: per-service roles, interaction patterns, open questions for Phase 2

  5. Write workspace-analysis-task.md for each service:
     Location: {service}/.claude/ecw/workspace-analysis-task.md
     Content (see template below)

Gate-out: cross-service-plan.md + workspace-analysis-task.md exist for all services
```

**workspace-analysis-task.md template:**

```markdown
## Original Requirement (full text, no paraphrasing)
{verbatim from user input}

## Coordinator's Initial Assessment (hypothesis — verify against your code)
- Your role: {Provider/Consumer/Both}
- Your responsibility: {1-2 sentences from Phase 1}
- Interaction pattern: {Dubbo/MQ/unclear}

## Other Services Context
{for each other service: their role and what they plan to do}

## Open Questions (flagged by Coordinator)
{any ambiguities about this service that need code analysis to resolve}

## Your Task (Phase 2 — Analysis Only)
1. Read your codebase to find the correct implementation entry points
2. Verify or correct the Coordinator's assessment — you have authority to override
3. Identify specific class + method for each change point
4. Determine the interaction pattern with other services (if unclear)
5. Output your technical plan in analysis-report.md
6. DO NOT implement anything yet — wait for contract alignment

## Output Format
Write analysis-report.md to .claude/ecw/analysis-report.md with:
  - Confirmed role (and corrections if any)
  - Implementation entry points (class + method + reason)
  - Your proposed interaction pattern (if previously unclear)
  - Any concerns or blockers
```

---

### Phase 2: Per-Service Code Analysis (Child sessions, interactive, parallel)

```
Gate-in: workspace-analysis-task.md exists for all services
Process:
  1. Open one terminal split/tab per service via terminal adapter (see ./terminal-adapters.md)
     Command: cd {ws}/{svc} && claude "Read .claude/ecw/workspace-analysis-task.md and execute Phase 2 analysis."
              --name {svc}-analyst --permission-mode acceptEdits

  2. Child sessions run in parallel (interactive — user can observe and intervene):
     - ECW-ready services: use knowledge files first, then scan code for gaps
     - ECW-absent services: scan source code directly
     - Each session identifies: specific class/method, interaction pattern, concerns
     - Each session writes analysis-report.md when done

  3. Poll for completion: check {service}/.claude/ecw/analysis-report.md every 5 seconds

  4. Coordinator reads all analysis-report.md files

Gate-out: analysis-report.md exists for all services
```

---

### Phase 3: Contract Alignment + Conflict Resolution

```
Gate-in: analysis-report.md exists for all services
Process:
  1. Coordinator reads all analysis-report.md files
  2. Cross-validate for conflicts:

     a. MQ contracts:
        Producer's topic name / DTO fields ↔ Consumer's expected topic / DTO fields
     b. Dubbo contracts:
        Provider's interface signature ↔ Consumer's expected call signature
     c. Interaction pattern conflicts:
        Service A wants sync Dubbo ↔ Service B prefers async MQ
     d. Responsibility boundary conflicts:
        Both/neither claim ownership of shared logic

  3. If conflicts found → AskUserQuestion per conflict (language follows output_language):
     Present:
       - Which services disagree
       - Each side's reasoning
       - Option A / Option B / Option C (custom)
     User decides → coordinator records decision

  4. Once all contracts aligned:
     - Update cross-service-plan.md with final contracts
     - Write confirmed-contract.md for EACH affected service:
       Location: {service}/.claude/ecw/confirmed-contract.md
       Content: final contract decisions relevant to this service + execution order

  5. Notify child sessions (still open from Phase 2):
     Coordinator writes confirmed-contract.md → child sessions poll for it

Gate-out: confirmed-contract.md exists for all services
```

---

### Phase 4: Per-Service Task Decomposition + Implementation (Child sessions)

```
Gate-in: confirmed-contract.md exists for all services
Process:
  Child sessions (still open from Phase 2) detect confirmed-contract.md and proceed:

  Per service (each child session independently):
    1. Read confirmed-contract.md — this is the authoritative contract
    2. Run ecw:writing-plans to decompose into concrete Tasks:
       - Based on own code analysis (from Phase 2) + confirmed contract
       - Coordinator does NOT decompose — child session owns this
    3. Execute plan: implement → test → ecw:impl-verify
    4. Write status.json when complete

  Execution order (per confirmed-contract.md):
    Layer 1: Provider services first (complete + mvn install/deploy before Layer 2)
    Layer 2: Consumer services in parallel

  Poll: check {service}/status.json every 5 seconds, timeout 30 minutes.
  Failed → AskUserQuestion: retry / skip / abort

Gate-out: status.json exists for all services
```

---

### Phase 5: Cross-Service Verification

```
Gate-in: status.json exists for all services
Process:
  Each service's ecw:impl-verify already ran inside child sessions.
  Coordinator performs additional cross-service checks:
    a. Dubbo: Provider interface signature = Consumer call signature
    b. MQ: Producer DTO fields = Consumer DTO fields
    c. Maven: Consumer pom.xml API Jar version = Provider published version

  All pass → proceed. Issues → present findings, suggest which service to fix.
Gate-out: All checks pass (or user accepts known issues)
```

---

### Phase 6: Summary & Push Confirmation

```
Gate-in: Phase 5 passed
Process:
  1. Aggregate status.json + git log per service
  2. Present summary: commits, files, deploy order (from confirmed-contract.md)
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
- **Never analyze code in Phase 1** — business decomposition must be code-free; code analysis belongs to child sessions in Phase 2
- **Never have coordinator write implementation tasks** — child sessions own task decomposition via ecw:writing-plans; coordinator distorts when it specifies "which class/method"
- **Never paraphrase the original requirement** — pass verbatim text to child sessions; paraphrasing loses intent
- **Never resolve contract conflicts without user** — architecture decisions (sync vs async, who owns what) require human judgment
- **Never run Provider + Consumer layers in parallel** — Consumer depends on Provider's API Jar
- **Never use `keystroke` on macOS** — clipboard paste only (input method corruption)
- **Never assume terminal type** — detect or fall back to manual

## Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "I'll just write the implementation task for the service, it'll be faster" | Coordinator doesn't know the service's internal structure. Child sessions do. Pre-written tasks will have wrong class/method locations. |
| "The business decomposition is obvious, skip Phase 1 confirmation" | Interaction patterns (Dubbo vs MQ, sync vs async) are often ambiguous. Get user confirmation before code analysis. |
| "The contract conflict is minor, I'll just pick one side" | Even minor contract decisions (field name, type) affect multiple services. Always surface to user. |
| "Phase 2 child sessions are taking too long, I'll analyze the code myself" | Coordinator doesn't have the service-specific knowledge that child sessions + ECW knowledge files provide. |
| "Only one service changed its contract, I'll update only that one" | Contract changes cascade. If wms changes DTO, both sci AND ofc might be affected. Check all consumers. |

## Supplementary Files

- `./lifecycle-commands.md` — create / status / push / destroy detailed process
- `./terminal-adapters.md` — Terminal detection + adapter implementations (Ghostty, iTerm2, tmux, manual)
- `./coordination-protocol.md` — status.json schema, polling mechanism, artifact locations
