---
name: ecw-development
description: Rules for developing and maintaining ECW plugin components (skills, agents, hooks)
scope: ecw-internal
---

# ECW Internal Development Rules

Rules Claude must follow when modifying ECW plugin itself (skills, agents, hooks, templates).

## SKILL.md Structure

- `[must-follow]` SKILL.md must have YAML frontmatter with `name` (matching directory name) and non-empty `description`
- `[must-follow]` SKILL.md must stay under 500 lines — split into sub-files or extract shared instructions if exceeded
- `[must-follow]` Must include an Error Handling table (scenario → handling format)
- `[must-follow]` Must include a Common Rationalizations table — max 5 entries, each unique to that skill
- `[recommended]` Include a Downstream Handoff section with explicit transition logic

## Routing and Transitions

- `[must-follow]` Full routing chain is defined only in risk-classifier — downstream skills reference via `ecw:skill-name`, never restate full routes
- `[must-follow]` Skills with Auto-Continue blocks must include backward-compatibility guard (check `Auto-Continue` field in session-state.md)
- `[must-follow]` Update session-state.md `Next` field before invoking the downstream skill

## Agent Templates

- `[must-follow]` Agent `.md` files must have YAML frontmatter with: name, description, model, tools
- `[must-follow]` Every agent must have a `## ... Boundary` section declaring single-task identity and prohibiting invoke/spawn of other skills
- `[must-follow]` Review agents (spec-reviewer, domain-analyst, domain-negotiator, impl-verifier) must declare a numeric source code reading limit (e.g., "at most N source files")
- `[recommended]` Agent output format: YAML for structured data, Markdown for reports — do not mix

## Hook Development

- `[must-follow]` Hook `main()` must be wrapped in try/except; except branch must output `{"result": "continue"}` and `sys.exit(0)` (fail-open semantics)
- `[must-follow]` Hook output goes through stdout JSON only; logging goes through stderr
- `[must-follow]` Reuse `marker_utils.py` / `ecw_config.py` shared functions — do not redefine them in individual hooks

## Context Efficiency

- `[must-follow]` Do not duplicate identical instruction text across skills (Ledger format, knowledge robustness, etc.) — use cross-references or shared instructions
- `[recommended]` Each skill's Common Rationalizations should contain only anti-patterns unique to that skill, not generic entries repeated elsewhere
- `[recommended]` Agent prompt templates should not embed static content obtainable by file reads (e.g., full knowledge base path listings)

## Testing

- `[must-follow]` New skills must be registered in `anchor_keywords.yaml` with critical keywords
- `[must-follow]` New agents must be added to `test_agent_hardening.py` agent lists
- `[recommended]` New hooks should have corresponding `test_{hook_name}.py` unit tests
