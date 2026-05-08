# Enterprise Change Workflow (ECW) Plugin

ECW is a Claude Code plugin — design all changes as reusable infrastructure: stable interfaces, zero host intrusion, configuration-driven.

## Rules

- **State Ownership Inversion**: Skills never write state. Hooks own all state transitions. Routing lives in `workflow-routes.yml`.
- **Single Source of Truth**: Any fact/rule defined in exactly one place. Other locations reference, never redefine.
- **Determinism over Probability**: If behavior MUST happen reliably, implement as Hook/script, not Prompt instruction.
- **Document Loading Discipline**: CLAUDE.md only holds rules that >50% sessions need + directly constrain behavior + can't be derived from code.

## Workflow

Before implementing, read `docs/design-principles.md` (full). Then read relevant sections of `docs/component-design-patterns.md` (see its index table).

Run `make all` before committing. File reference: `docs/artifact-reference.md`. Compliance checklist: `CONTRIBUTING.md`.
