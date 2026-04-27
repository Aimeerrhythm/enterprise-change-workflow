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

Gate-out: cross-service-plan.md + workspace-analysis-task.md exist for all services
         Update session-state.md: Phase 1 → ✅ 完成; Subagent Ledger Explore agents → complete
```

**workspace-analysis-task.md template:**

```markdown
## Original Requirement (verbatim — do not paraphrase)
{exact text from workspace.yml.requirement}

## Coordinator's Business Assessment (hypothesis — verify against your code)
- Your role: {Provider / Consumer / Both}
- Your business responsibility: {1-2 sentences, business language only — no class names or method names}
- Interaction type: {Dubbo / MQ / unclear}

## Cross-Service Context (for risk classification)
- Interaction type: {MQ / Dubbo / unclear}
- Contract change type: {new field (backward compatible) / field removal / signature change / new topic / other}
- Other services involved:
  {for each other service: name → role → what they plan to do}

## Analysis Strategy
ECW Status: {ECW-ready / ECW-partial / ECW-absent}
{if ECW-ready or ECW-partial}:
  Read .claude/knowledge/<relevant domain>/ FIRST.
  Scan source code only for gaps not covered by knowledge docs.
{if ECW-absent}:
  No knowledge files available. Scan source code directly.

## Other Services Context
{for each other service: their role and business responsibility from Phase 1}

## Open Questions (flagged by Coordinator — needs code analysis to resolve)
{any ambiguities that Phase 2 must investigate, e.g. unclear interaction type, unknown entry points}

## Your Task (Phase 2 — Analysis Only, do NOT implement yet)
1. Follow the Analysis Strategy above — knowledge files first if ECW-ready
2. Find the correct implementation entry points yourself (class + method + reason)
3. Verify or correct the Coordinator's business assessment — you have authority to override
4. Determine the interaction pattern if marked unclear
5. Write your technical plan to .claude/ecw/session-data/{wf-id}/analysis-report.md
6. Phase 2 analysis is done after writing analysis-report.md. Do NOT proceed to implementation.
   A new session will be opened by the coordinator for Phase 4 implementation.

## Output Format
Write analysis-report.md to .claude/ecw/session-data/{wf-id}/analysis-report.md with:
  - Confirmed role (and corrections to coordinator's assessment if any)
  - Implementation entry points (class + method + reason, found by your own analysis)
  - Proposed interaction pattern (if was unclear)
  - Any concerns or blockers

## Stale Plans Notice
Ignore any files in .claude/plans/ that predate this workspace session (wf-id: {wf-id}).
They belong to other workflows. Only act on plans tagged with this wf-id.

## Session State Updates
Update .claude/ecw/session-data/{wf-id}/session-state.md at:
- Phase 2 complete: record confirmed role + entry points summary
```

---

### Phase 2: Per-Service Code Analysis (Child sessions, interactive, parallel)

```
Gate-in: workspace-analysis-task.md exists for all services at .claude/ecw/session-data/{wf-id}/
Process:
  1. Generate Phase 2 start scripts and open one terminal tab per service
     via terminal adapter (see ./terminal-adapters.md § Phase 2 Scripts)

     Script prompt: "Read .claude/ecw/session-data/{wf-id}/workspace-analysis-task.md and execute Phase 2 analysis."
     Flags: --name {svc}-analyst --permission-mode bypassPermissions

  2. Child sessions run in parallel (interactive — user can observe and intervene):
     - ECW-ready services: use knowledge files first, then scan code for gaps
     - ECW-absent services: scan source code directly
     - Each session identifies: specific class/method, interaction pattern, concerns
     - Each session writes analysis-report.md and then EXITS (Phase 2 is done)

  3. Poll for completion: check {service}/.claude/ecw/session-data/{wf-id}/analysis-report.md
     every 5 seconds

  4. Coordinator reads all analysis-report.md files

Gate-out: analysis-report.md exists for all services at .claude/ecw/session-data/{wf-id}/
```

---

### Phase 3: Contract Alignment + Conflict Resolution

```
Gate-in: analysis-report.md exists for all services at .claude/ecw/session-data/{wf-id}/
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

Gate-out: confirmed-contract.md exists for all services at .claude/ecw/session-data/{wf-id}/
```
### Phase 4: Per-Service Implementation (NEW child sessions, parallel or layered)

```
Gate-in: confirmed-contract.md exists for all services at .claude/ecw/session-data/{wf-id}/
Process:
  Phase 2 sessions have exited. Coordinator opens NEW Phase 4 child sessions.

  1. Generate Phase 4 start scripts via terminal adapter (see ./terminal-adapters.md):

     For ECW-ready / ECW-partial services (have CLAUDE.md + BLOCKING RULE):
       Prompt: "You have a new implementation task for this service.
                Context:
                - Cross-service contract: .claude/ecw/session-data/{wf-id}/confirmed-contract.md
                - Your service's code analysis: .claude/ecw/session-data/{wf-id}/analysis-report.md
                Implement all changes required by the contract.
                When complete, write status.json to .claude/ecw/session-data/{wf-id}/status.json."
       Flags: --name {svc}-impl --permission-mode bypassPermissions
       Note: BLOCKING RULE drives the full internal ECW flow autonomously:
             risk-classifier → writing-plans → tdd → impl → impl-verify → knowledge-track.
             Only status.json is specified explicitly as the coordinator's completion signal.

     For ECW-absent services (no CLAUDE.md / no BLOCKING RULE):
       Prompt: "Read .claude/ecw/session-data/{wf-id}/confirmed-contract.md and
                .claude/ecw/session-data/{wf-id}/analysis-report.md.
                Implement the changes described in the contract.
                After implementation: run /ecw:impl-verify.
                After impl-verify passes: write status.json to
                .claude/ecw/session-data/{wf-id}/status.json."
       Flags: --name {svc}-impl --permission-mode bypassPermissions

  2. Dispatch order (based on interaction_pattern in confirmed-contract.md):
     MQ interaction:
       -> Open ALL Phase 4 sessions in parallel (no compile dependency)
     Dubbo interaction:
       -> Open Layer 1 (Provider) sessions first
       -> Wait for Layer 1 status.json at .claude/ecw/session-data/{wf-id}/
       -> After Layer 1: run mvn install/deploy in Provider worktree
       -> Then open Layer 2 (Consumer) sessions

  Per service (each child session independently):
    a. Read confirmed-contract.md -- authoritative cross-service contract
    b. Read analysis-report.md -- own service's code analysis from Phase 2
    c. Decompose into tasks:
       ECW-ready: ecw:writing-plans auto-triggered by BLOCKING RULE
       ECW-absent: manual decomposition based on analysis-report.md
    d. Implement -> test -> ecw:impl-verify (-> ecw:knowledge-track auto-invoked by impl-verify for ECW-ready)
    e. Write status.json:
       Location: {service}/.claude/ecw/session-data/{wf-id}/status.json
       completed_at: current actual time ($(date -Iseconds)), NOT workflow ID timestamp

  Poll: check {service}/.claude/ecw/session-data/{wf-id}/status.json every 5 seconds,
        timeout 30 minutes.
  Failed -> AskUserQuestion: retry / skip / abort

Gate-out: status.json exists for all services at .claude/ecw/session-data/{wf-id}/
```

### Phase 5: Cross-Service Verification

```
Gate-in: status.json exists at {service}/.claude/ecw/session-data/{wf-id}/ for all services
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
Gate-out: All checks pass (or user accepts known issues)
```

---

### Phase 6: Summary & Push Confirmation

```
Gate-in: Phase 5 passed
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

## Never Rules

- **Never skip Phase gates** — artifact must exist before next Phase
- **Never use code-reading tools in Phase 1** — Phase 1 information source is workspace.yml requirement ONLY. No Read, Bash, Glob, Grep, or Explore tools. If code detail is needed to answer a question, it's an Open Question for Phase 2, not something to resolve in Phase 1.
- **Never put code-level detail in Phase 1 output** — class names, method names, field names, SQL in cross-service-plan.md or workspace-analysis-task.md are Phase 1 violations.
- **Never have coordinator write implementation tasks** — child sessions own task decomposition via ecw:writing-plans; coordinator distorts when it specifies "which class/method"
- **Never paraphrase the original requirement** — pass verbatim text to child sessions; paraphrasing loses intent
- **Never resolve contract conflicts without user** — architecture decisions (sync vs async, who owns what) require human judgment
- **Never run Provider + Consumer in parallel for Dubbo** — Consumer depends on Provider's API Jar. For MQ, parallel execution after Phase 3 contract confirmation is correct.
- **Never use `keystroke` on macOS** — clipboard paste only (input method corruption)
- **Never assume terminal type** — detect or fall back to manual

## Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "I'll just quickly scan the code in Phase 1 to confirm the interaction pattern" | Phase 1 is information-constrained: workspace.yml only. If you can't determine the pattern from the requirement, mark it "unclear" and let Phase 2 investigate. Scanning code in Phase 1 produces class-level detail that belongs to child sessions — and your scan will be incomplete anyway. |
| "I'll just write the implementation task for the service, it'll be faster" | Coordinator doesn't know the service's internal structure. Child sessions do. Pre-written tasks will have wrong class/method locations. |
| "The business decomposition is obvious, skip Phase 1 confirmation" | Interaction patterns (Dubbo vs MQ, sync vs async) are often ambiguous. Get user confirmation before Phase 2 starts. |
| "The contract conflict is minor, I'll just pick one side" | Even minor contract decisions (field name, type) affect multiple services. Always surface to user. |
| "Phase 2 child sessions are taking too long, I'll analyze the code myself" | Coordinator doesn't have the service-specific knowledge that child sessions + ECW knowledge files provide. |
| "Only one service changed its contract, I'll update only that one" | Contract changes cascade. If wms changes DTO, both sci AND ofc might be affected. Check all consumers. |

## Supplementary Files

- `./lifecycle-commands.md` — create / status / push / destroy detailed process
- `./terminal-adapters.md` — Terminal detection + adapter implementations (Ghostty, iTerm2, tmux, manual)
- `./coordination-protocol.md` — status.json schema, polling mechanism, artifact locations
