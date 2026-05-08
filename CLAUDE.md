# Enterprise Change Workflow (ECW) Plugin

## Overview

ECW: risk-driven change management workflow. Entry point: `ecw:risk-classifier`. Routing: `workflow-routes.yml`. Commands: `/ecw-init`, `/ecw-validate-config`, `/ecw-upgrade`.

## Architecture Design Reference

**Before implementing new features or fixing issues**, read `docs/design-principles.md` (6 litmus tests + State Ownership Inversion) and `docs/component-design-patterns.md` (9 component patterns). Use as:

1. **Design checklist** — Does the proposed change pass all 6 litmus tests?
2. **Bug root cause** — Does the bug violate a known principle? If yes, fix by reverting to the principle (not patching around it).
3. **Regression baseline** — After refactor, confirm no anti-patterns from the docs have been introduced.

Key rules (always enforced):
- **State Ownership Inversion**: Skills never write state (`current_phase`, `working_mode`, `next`). Hooks own all state transitions. Routing decisions live in `workflow-routes.yml`, not in SKILL.md.
- **Single Source of Truth**: Any fact/rule defined in exactly one place. If you need to update N files for one change, architecture is wrong.
- **Determinism over Probability**: If behavior MUST happen reliably, implement as Hook/script, not as Prompt instruction.
- **Document Loading Discipline**: CLAUDE.md only holds rules that >50% sessions need + directly constrain behavior + can't be derived from code. Everything else goes to `docs/` (read on demand). Never inline large tables or low-frequency reference into CLAUDE.md. Full criteria: `docs/component-design-patterns.md` §8.

## Completion Verification Rules

Before declaring any task "complete":

1. **`ecw:impl-verify`** must pass (zero must-fix findings). P3 or pure formatting changes can skip.
2. **`verify-completion` hook** fires automatically — blocks on broken references, compilation failure, test failure. No manual invocation needed.

Do not defer verification until user requests it. Fix issues first, then re-verify.

## Documentation Sync Rules

**Must sync corresponding knowledge files after code changes. Check by change layer:**

- **Project structure** (module/component/dependency/data model changes) → Update corresponding docs under `project/`
- **Business logic** (state transition/business rule changes) → Update `.claude/knowledge/<domain>/business-rules.md`
- **Cross-domain integration** (call relationships/MQ/shared resources/external systems/e2e paths) → Update corresponding docs under `.claude/knowledge/common/`

## Project Configuration

Run `/ecw-init` after installation for project initialization. Full file reference: see `docs/artifact-reference.md`.
