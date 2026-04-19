# Session State File Format

## Template

Write this template to `.claude/ecw/session-data/{workflow-id}/session-state.md`:

```markdown
# ECW Session State

<!-- ECW:STATUS:START -->
- **Risk Level**: P{X}
- **Domains**: {domain list}
- **Mode**: {single-domain/cross-domain}
- **Routing**: {full routing chain}
- **Current Phase**: phase1-complete
- **Created**: {YYYY-MM-DD HH:mm}
- **Workflow ID**: {YYYYMMDD-HHmm}
- **Implementation Strategy**: TBD (determined after ecw:writing-plans based on Task count)
- **Post-Implementation Tasks**: {fill after Route Task Creation, e.g., "impl-verify(#3) → biz-impact-analysis(#4) → phase3(#5)"}
- **Auto-Continue**: yes
<!-- ECW:STATUS:END -->

<!-- ECW:MODE:START -->
- **Working Mode**: analysis
<!-- ECW:MODE:END -->

<!-- ECW:LEDGER:START -->
## Subagent Ledger

| Phase | Agent | Type | Est. Scale | Started | Duration |
|-------|-------|------|-----------|---------|----------|
<!-- ECW:LEDGER:END -->
```

## Marker Conventions

session-state.md uses `<!-- ECW:{NAME}:START/END -->` markers to delimit updatable sections. When updating a section (e.g. STATUS, LEDGER, MODE), only replace content between the matching markers — **never overwrite the entire file**. Standard marker names: `STATUS` (workflow fields), `MODE` (working mode), `LEDGER` (subagent table), `STOP` (auto-updated by Stop hook).

## Working Mode Definitions

Each skill sets the `MODE` marker section on entry to declare the current working mode. This helps post-compaction recovery understand the workflow phase.

| Mode | Set by | Behavior |
|------|--------|----------|
| `analysis` | risk-classifier, requirements-elicitation, domain-collab | Focus on understanding requirements; read broadly before concluding |
| `planning` | writing-plans, spec-challenge | Design implementation approach; prioritize cross-file consistency |
| `implementation` | impl-orchestration, tdd, systematic-debugging | Write code; keep atomic commits; run tests after each change |
| `verification` | impl-verify, biz-impact-analysis | Review completed work; severity-grade findings; do not modify code |

**Mode switch**: When entering a skill, update the MODE marker: `<!-- ECW:MODE:START -->\n- **Working Mode**: {mode}\n<!-- ECW:MODE:END -->`

## Session Advisory — Context Management

After Plan completion (writing-plans finishes), evaluate whether to continue or start a new session:

| Signal | Advisory |
|--------|----------|
| P0/P1 with prior domain-collab or requirements-elicitation | **Strongly recommend new session** — requirement analysis + plan writing likely consumed 100K+ context |
| P2 with Plan ≥ 5 Tasks | **Recommend new session** — TDD for many tasks will push context toward compaction threshold |
| P2 with Plan ≤ 4 Tasks, no prior requirement analysis | **Continue** — context overhead is manageable |
| P3 | **Continue** — no formal plan, minimal context |

Full workflow for P0 cross-domain changes typically requires 500+ turns. Recommend switching to a new session after plan completion (after spec-challenge) to avoid context compression causing information loss.

**New session recovery**: Tasks created by TaskCreate do not persist across sessions. When a new session reads `session-state.md` to restore context, it needs to re-create pending Tasks based on the `Post-Implementation Tasks` field.
