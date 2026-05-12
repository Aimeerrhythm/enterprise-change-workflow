# ECW Design Reference

Quick-lookup reference for ECW architectural rules, state schema, and key decisions.
For full rationale, see `docs/design-principles.md`.

## Core Architecture Rules

| Rule | Description |
|------|-------------|
| **State Ownership Inversion** | Skills never write routing state. Hooks own all state transitions. |
| **Single Source of Truth** | `workflow-routes.yml` is the only place routing chains are defined. |
| **Determinism over Probability** | Reliable behavior = Hook/script, not Prompt instruction. |
| **Two Entry Points** | Requirements: `ecw:risk-classifier`. Bug fixes: `ecw:systematic-debugging`. |

## Session State Schema

`session-state.json` fields (written by risk-classifier or systematic-debugging):

| Field | Type | Description |
|-------|------|-------------|
| `risk_level` | `P0`–`P3` | Risk classification |
| `change_type` | `requirement`\|`bug` | Change category |
| `routing` | `list[str]` | Full routing chain (rebuilt by hook for requirements) |
| `next` | `str` | Next ECW skill to invoke |
| `current_phase` | `str` | Current phase marker (e.g., `risk-assessment-loaded`) |


## Routing Chain Construction

For **requirement** changes: risk-classifier LLM writes only `routing[0]` and `risk_level`.
The auto-continue hook PostToolUse rebuilds: `routing = [routing[0]] + tail(risk_level)`.

| `risk_level` | `routing[0]` options | Tail |
|-------------|---------------------|------|
| P0 | requirements-elicitation / domain-collab | writing-plans → spec-challenge → TDD:RED → impl-verify → biz-impact-analysis |
| P1 | requirements-elicitation / domain-collab | writing-plans → TDD:RED → impl-verify → biz-impact-analysis |
| P2 | writing-plans | TDD:RED → impl-verify |
| P3 | (empty) | (empty — direct implementation) |

For **bug** changes: systematic-debugging writes the full fixed chain directly.

## Key Files

| File | Role |
|------|------|
| `skills/risk-classifier/workflow-routes.yml` | Routing matrix, impl strategy, skill metadata |
| `skills/risk-classifier/session-state-format.md` | JSON schema for session-state.json |
| `docs/artifact-reference.md` | All ECW artifact files (paths, write timing) |
| `docs/component-design-patterns.md` | Per-component design patterns |
