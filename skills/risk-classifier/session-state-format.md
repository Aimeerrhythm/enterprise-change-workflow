# Session State File Format

## Template

Write this template to `.claude/ecw/session-data/{workflow-id}/session-state.md`:

```markdown
# ECW Session State

<!-- ECW:STATUS:START -->
risk_level: P{X}
domains: [{domain list}]
mode: {single-domain or cross-domain}
routing: [{ordered skill list}]
current_phase: phase1-complete
created: "{YYYY-MM-DD}"
workflow_id: "{YYYYMMDD-xxxx}"
baseline_commit: TBD
implementation_strategy: TBD
post_implementation_tasks: TBD
auto_continue: true
next: {next skill to invoke}
<!-- ECW:STATUS:END -->

<!-- ECW:MODE:START -->
working_mode: analysis
<!-- ECW:MODE:END -->

<!-- ECW:LEDGER:START -->
<!-- ECW:LEDGER:END -->
```

## Format Rules

- All marker sections use **YAML** format (not Markdown)
- `routing` and `domains` are **YAML lists** (square brackets), not comma-separated strings
- `auto_continue` is **YAML boolean** (`true`/`false`), not string
- String values containing special characters must be quoted (`"2026-05-04"`, `"20260504-a3f1"`)
- LEDGER section is a **YAML list of dicts**, one dict per subagent dispatch

**CRITICAL: always use the `<!-- ECW:STATUS:START/END -->` markers.** The auto-continue hook reads the STATUS section via `read_marker_section("STATUS")`. If STATUS content is written outside these markers, the hook silently no-ops and the downstream skill chain breaks.

## LEDGER Entry Format

Each subagent dispatch appends one entry:

```yaml
- phase: {skill or sub-phase name}
  agent: {agent identifier}
  type: {general or ecw:skill-name}
  model: {opus, sonnet, haiku}
  scale: {small, medium, large}
  started: "{HH:mm}"
  duration: "{~Ns or ~Nm Ns}"
```

## Workflow ID Generation

- **Date part**: Read from `currentDate` system-reminder (format `YYYY/MM/DD`) — this is injected by the runtime from the user's local clock and is timezone-correct. Convert to `YYYYMMDD`.
- **Suffix**: 4 random hex characters (e.g., `a3f1`). Never use wall-clock time (HH:mm) — Claude's internal time perception does not track local timezone reliably.
- **Example**: `20260429-a3f1`
- **Created field**: Use the date from `currentDate` only, formatted as `YYYY-MM-DD` (no time component).

## Marker Conventions

session-state.md uses `<!-- ECW:{NAME}:START/END -->` markers to delimit updatable sections. When updating a section (e.g. STATUS, LEDGER, MODE), only replace content between the matching markers — **never overwrite the entire file**. Standard marker names: `STATUS` (workflow fields), `MODE` (working mode), `LEDGER` (subagent list), `STOP` (auto-updated by Stop hook).

## Working Mode Definitions

Each skill sets the `MODE` marker section on entry to declare the current working mode. This helps post-compaction recovery understand the workflow phase.

| Mode | Set by | Behavior |
|------|--------|----------|
| `analysis` | risk-classifier, requirements-elicitation, domain-collab | Focus on understanding requirements; read broadly before concluding |
| `planning` | writing-plans, spec-challenge | Design implementation approach; prioritize cross-file consistency |
| `implementation` | impl-orchestration, tdd, systematic-debugging | Write code; keep atomic commits; run tests after each change |
| `verification` | impl-verify, biz-impact-analysis | Review completed work; severity-grade findings; do not modify code |

**Mode switch**: When entering a skill, update the MODE marker with YAML: `working_mode: {mode}`

## Session Advisory — Context Management

After Plan completion (writing-plans finishes), evaluate whether to continue or start a new session:

| Signal | Advisory |
|--------|----------|
| P0/P1 with prior domain-collab or requirements-elicitation | **Strongly recommend new session** — requirement analysis + plan writing likely consumed 100K+ context |
| P2 with Plan ≥ 5 Tasks | **Recommend new session** — TDD for many tasks will push context toward compaction threshold |
| P2 with Plan ≤ 4 Tasks, no prior requirement analysis | **Continue** — context overhead is manageable |
| P3 | **Continue** — no formal plan, minimal context |

Full workflow for P0 cross-domain changes typically requires 500+ turns. Recommend switching to a new session after plan completion (after spec-challenge) to avoid context compression causing information loss.

**New session recovery**: Tasks created by TaskCreate do not persist across sessions. When a new session reads `session-state.md` to restore context, it needs to re-create pending Tasks based on the `post_implementation_tasks` field.
