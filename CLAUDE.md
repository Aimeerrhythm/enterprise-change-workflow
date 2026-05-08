# Enterprise Change Workflow (ECW) Plugin

## Development Rules (for ECW contributors only)

**Before implementing new features or fixing issues**, read `docs/design-principles.md` and `docs/component-design-patterns.md`.

Key rules:
- **State Ownership Inversion**: Skills never write state. Hooks own all state transitions. Routing lives in `workflow-routes.yml`.
- **Single Source of Truth**: Any fact/rule defined in exactly one place.
- **Determinism over Probability**: If behavior MUST happen reliably, implement as Hook/script, not Prompt instruction.
- **Document Loading Discipline**: CLAUDE.md only holds rules that >50% sessions need + directly constrain behavior + can't be derived from code. Full criteria: `docs/component-design-patterns.md` §8.

Project file reference: `docs/artifact-reference.md`. Architecture compliance checklist: `CONTRIBUTING.md`.
