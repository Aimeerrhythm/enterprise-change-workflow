# Session State File Format


## Workflow ID Generation

- **Date part**: Read from `currentDate` system-reminder (format `YYYY/MM/DD`) — this is injected by the runtime from the user's local clock and is timezone-correct. Convert to `YYYYMMDD`.
- **Suffix**: 4 random hex characters (e.g., `a3f1`). Never use wall-clock time (HH:mm) — Claude's internal time perception does not track local timezone reliably.
- **Example**: `20260429-a3f1`

## Template

Write this JSON file to `.claude/ecw/session-data/{workflow-id}/session-state.json`:

```json
{
  "risk_level": "P{X}",
  "current_phase": "risk-assessment-complete",
  "routing": ["{first-downstream-skill}"],
  "next": "{next skill to invoke}",
  "baseline_commit": "TBD"
}
```

## Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `risk_level` | string | yes | P0, P1, P2, or P3 |
| `current_phase` | string | yes | Current workflow phase (protocol values such as `risk-assessment-complete`, `plan-loaded`) |
| `routing` | string[] | yes | Write only `routing[0]` (first downstream skill); auto-continue hook reconstructs the full chain after this skill completes |
| `next` | string | yes | Next skill to invoke |
| `baseline_commit` | string | no | Git commit hash at workflow start (set to "TBD" initially, filled by post-edit-check hook) |

## Format Rules

- File is standard JSON — use `json.load()` / `json.dump()` for all reads and writes
- `routing` is a JSON array of strings, not a comma-separated string
- No markers, no YAML, no markdown — pure JSON

## Conflict Detection

Before writing, check if `.claude/ecw/session-data/{workflow-id}/session-state.json` already exists. If it does, regenerate the 4-digit suffix and re-check (max 3 attempts).