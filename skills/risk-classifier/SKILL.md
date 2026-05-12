---
name: risk-classifier
description: >
  Use when user proposes any requirement, feature change, or code modification ("I want to...",
  "need to change...", "add a feature..."). Must run before reading code or starting implementation.
  Classifies change risk (P0–P3) to drive downstream workflow depth. Not for bug fixes
  (use ecw:systematic-debugging) or when user manually specifies a risk level.
---

# Risk Classifier

## Overview

Classify risk level (P0~P3) for any **requirement or feature change**, driving the depth of downstream workflow.

**Output language**: Read `ecw.yml` → `project.output_language`. All artifact headings, table headers, and labels follow this language. `session-state.json` field keys stay English (machine-parsed).

**Core Principle:** The process for changing a log statement should not be as heavy as changing inventory deduction logic.

**Announce at start:** "Using ecw:risk-classifier to classify change risk level."

## When to Use

- User proposes any requirement, feature change, or code modification
- User says "I want to...", "need to change...", "add a feature...", "implement..."
- **Must execute before ecw:requirements-elicitation**

**When NOT to use:**
- Pure code reading/analysis/questions ("What does this class do?")
- User explicitly says "use PX" (manually specified level, skip auto-classification)
- Initial risk assessment already completed in current session and level not contested
- **Bug fixes** — use `ecw:systematic-debugging` as the entry point instead

---

## Initial Risk Assessment

Read `./prompts/risk-assessment-guide.md` for assessment steps and output format.

### State Persistence

Read `./session-state-format.md` to write session state — includes JSON schema, workflow ID generation, and conflict detection. On conflict: regenerate workflow ID up to max 3 attempts before prompting user.

`routing[0]` values:
- `ecw:requirements-elicitation` — single-domain requirement
- `ecw:domain-collab` — cross-domain requirement
- `ecw:writing-plans` — P2 entry (no requirement analysis needed)
- (omit routing field entirely) — P3 direct implementation

**Why session-state.json format is non-negotiable**: the auto-continue hook reads `routing` and `next` to inject the next skill in the chain. If markers are missing or the JSON is malformed, the hook silently no-ops — the model loses routing guidance and the workflow chain breaks. Conform to `./session-state-format.md` exactly; do not improvise field names or omit the marker block.


## Error Handling

| Scenario | Fallback |
|----------|---------|
| `shared-resources.md` missing | Skip shared-resource risk dimension; determine cross-domain by keyword count only |
| Domain `business-rules.md` missing | Skip business sensitivity for that domain; rely on Change Type Risk only |
| CLAUDE.md domain routing table absent | Default `entry_skill` to `ecw:requirements-elicitation`; flag as uncertain in output |
| `session-state.json` write failure | Retry once → still fails: output JSON inline in conversation for manual save |

## Supplementary Files

- `workflow-routes.yml` — Routing matrix (single source of truth) + implementation strategy + post-impl tasks
- `prompts/risk-assessment-guide.md` — Risk assessment steps + output and confirmation flow
- `prompts/common-mistakes.md` — Anti-patterns checklist
- `session-state-format.md` — JSON schema, workflow ID generation, conflict detection
