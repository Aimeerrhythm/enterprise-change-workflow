# Session State File Format

## Template

Write this JSON file to `.claude/ecw/session-data/{workflow-id}/session-state.json`:

```json
{
  "risk_level": "P{X}",
  "current_phase": "risk-assessment-complete",
  "routing": ["skill-1", "TDD:RED", "Implementation(GREEN)", "impl-verify"],
  "next": "{next skill to invoke}",
  "auto_continue": true,
  "baseline_commit": "TBD"
}
```

## Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `risk_level` | string | yes | P0, P1, P2, or P3 |
| `current_phase` | string | yes | Current workflow phase (protocol values such as `risk-assessment-complete`, `plan-loaded`) |
| `routing` | string[] | yes | Ordered list of skills/steps in the workflow chain |
| `next` | string | yes | Next skill to invoke |
| `auto_continue` | boolean | yes | Whether auto-routing is active |
| `baseline_commit` | string | no | Git commit hash at workflow start (set to "TBD" initially, filled by post-edit-check hook) |

## Format Rules

- File is standard JSON — use `json.load()` / `json.dump()` for all reads and writes
- `routing` is a JSON array of strings, not a comma-separated string
- `auto_continue` is a JSON boolean (`true`/`false`), not a string
- No markers, no YAML, no markdown — pure JSON

## Workflow ID Generation

- **Date part**: Read from `currentDate` system-reminder (format `YYYY/MM/DD`) — this is injected by the runtime from the user's local clock and is timezone-correct. Convert to `YYYYMMDD`.
- **Suffix**: 4 random hex characters (e.g., `a3f1`). Never use wall-clock time (HH:mm) — Claude's internal time perception does not track local timezone reliably.
- **Example**: `20260429-a3f1`

## Conflict Detection

Before writing, check if `.claude/ecw/session-data/{workflow-id}/session-state.json` already exists. If it does, regenerate the 4-digit suffix and re-check (max 3 attempts).

## Session Advisory — Context Management

After Plan completion (writing-plans finishes), evaluate whether to continue or start a new session:

| Signal | Advisory |
|--------|----------|
| P0/P1 with prior domain-collab or requirements-elicitation | **Strongly recommend new session** — requirement analysis + plan writing likely consumed 100K+ context |
| P2 with Plan >= 5 Tasks | **Recommend new session** — TDD for many tasks will push context toward compaction threshold |
| P2 with Plan <= 4 Tasks, no prior requirement analysis | **Continue** — context overhead is manageable |
| P3 | **Continue** — no formal plan, minimal context |

**New session recovery**: When a new session reads `session-state.json` to restore context, it re-creates pending Tasks based on the routing chain.
