# Enterprise Change Workflow (ECW) Plugin

## Overview

ECW provides structured change management workflows for large multi-module projects.

**Core workflow chain**: `risk-classifier` → `requirements-elicitation` / `domain-collab` → `writing-plans` → `spec-challenge` → `tdd` → `impl-orchestration` → `impl-verify` → `biz-impact-analysis` → `knowledge-track`

**Bug path**: `risk-classifier` → `systematic-debugging` → `tdd` → `impl-verify`

**Manual tools** (off-chain): `cross-review`, `knowledge-audit`, `knowledge-repomap`, `workspace`

## Workflow

```
ecw:risk-classifier (Phase 1 quick pre-assessment)
  ├─ Single-domain → ecw:requirements-elicitation → Phase 2 → ecw:writing-plans → [P0: ecw:spec-challenge]
  ├─ Cross-domain → ecw:domain-collab → Phase 2 → ecw:writing-plans → [P0/P1 cross-domain: ecw:spec-challenge]
  ├─ P2 → ecw:writing-plans
  ├─ P3 → Direct implementation
  └─ Bug → ecw:systematic-debugging
Post-implementation → ecw:impl-verify → [P0/P1: ecw:biz-impact-analysis → Phase 3 feedback calibration]
```

> Complete routing matrix (including per-level must_include/must_exclude): `skills/risk-classifier/workflow-routes.yml`

## Dependencies

- **No external plugin dependencies** — ECW is self-contained with all Skills (writing-plans, tdd, systematic-debugging, impl-orchestration, etc.); no other plugins needed.

## Project Configuration

**Important: Domain routing and business knowledge are defined in your project, not in this plugin.**

Run `/ecw-init` after installation for project initialization. Full file reference (Required Files, Artifact Files, Knowledge Files): see `docs/artifact-reference.md`.

## Architecture Design Reference

**Before implementing new features or fixing issues**, read `docs/design-principles.md` (6 litmus tests + State Ownership Inversion) and `docs/component-design-patterns.md` (7 component patterns). Use as:

1. **Design checklist** — Does the proposed change pass all 6 litmus tests?
2. **Bug root cause** — Does the bug violate a known principle? If yes, fix by reverting to the principle (not patching around it).
3. **Regression baseline** — After refactor, confirm no anti-patterns from the docs have been introduced.

Key rules (always enforced):
- **State Ownership Inversion**: Skills never write state (`current_phase`, `working_mode`, `next`). Hooks own all state transitions. Routing decisions live in `workflow-routes.yml`, not in SKILL.md.
- **Single Source of Truth**: Any fact/rule defined in exactly one place. If you need to update N files for one change, architecture is wrong.
- **Determinism over Probability**: If behavior MUST happen reliably, implement as Hook/script, not as Prompt instruction.
- **Document Loading Discipline**: CLAUDE.md only holds rules that >50% sessions need + directly constrain behavior + can't be derived from code. Everything else goes to `docs/` (read on demand). Never inline large tables or low-frequency reference into CLAUDE.md. Full criteria: `docs/component-design-patterns.md` §8.

## Completion Verification Rules

**Verification chain before declaring a task "complete":**

1. **`ecw:impl-verify`** — Implementation correctness verification, multi-round convergence until zero must-fix. Cross-references code vs requirements/domain knowledge/Plan/engineering standards, also covering code quality review (replaces code-reviewer).
2. **`verify-completion` hook (automatic)** — Mechanical checks: reference integrity, compilation, tests, knowledge sync. Technical check failures block completion.

> Hook is auto-executed by PreToolUse — no manual invocation needed. Hook hard intercepts include: broken reference check, residual reference check, Java compilation check, Java test check (controlled by ecw.yml `verification.run_tests`). Targeted reminders include: knowledge document sync reminder, TDD test coverage reminder (controlled by ecw.yml `tdd.check_test_files`).
>
> impl-verify executes before marking complete (P3 or pure formatting/comment changes can skip). Fix issues first, then re-verify. **Do not defer verification until user requests it.**
>
> **Relationship between implementation-phase review and impl-verify**: When using `ecw:impl-orchestration`, its built-in per-task spec review + code quality review (P0) provides immediate feedback, preventing error cascading to subsequent Tasks. impl-verify performs higher-level cross-validation from requirements/domain knowledge/Plan/engineering standards after all implementation completes. The two complement each other; neither replaces the other. See risk-classifier's "Implementation Strategy Selection" section for strategy rules.
>
> `ecw:cross-review` as a manual optional tool (`/ecw:cross-review`) is suitable for cross-file structural consistency checks in document-heavy changes; not in the required workflow.

## Skill Auto-Continue Mechanism

Skill-to-skill chaining (e.g., domain-collab → Phase 2 → writing-plans) is enforced by the `auto-continue` PostToolUse hook (`hooks/auto-continue.py`), not by prompt instructions in individual Skill files. The hook fires after each ECW Skill completes, reads `session-state.md` routing chain, and injects the remaining route as `systemMessage`. Individual Skills contain only business logic — no state transitions, no routing decisions (State Ownership Inversion).

## Documentation Sync Rules

**Must sync corresponding knowledge files after code changes. Check by change layer:**

- **Project structure** (module/component/dependency/data model changes) → Update corresponding docs under `project/`
- **Business logic** (state transition/business rule changes) → Update `.claude/knowledge/<domain>/business-rules.md`
- **Cross-domain integration** (call relationships/MQ/shared resources/external systems/e2e paths) → Update corresponding docs under `.claude/knowledge/common/`

## Impact Analysis Tool Distinction

| Tool | Phase | Input | Purpose |
|------|-------|-------|---------|
| `ecw:domain-collab` | **Requirement phase** (pre-implementation) | Natural language requirement description | Analyze which domains are affected, what changes each needs, cross-domain dependencies and conflicts |
| `ecw:biz-impact-analysis` | **Code phase** (post-implementation) | git diff | Analyze what business processes, external systems, e2e paths are actually impacted by completed code changes |

**Do not mix**: Use `ecw:domain-collab` during requirement analysis phase; use `ecw:biz-impact-analysis` after code changes.

### Project CLAUDE.md Integration

Need to add in project CLAUDE.md:
1. **Domain-level knowledge routing table** — Keyword→domain mapping for ecw:risk-classifier and ecw:domain-collab matching

Reference `templates/CLAUDE.md.snippet` for the template.

## Skill Trigger Conditions

Auto-chaining is driven by `workflow-routes.yml` routing chain + `auto-continue` hook. Manual invocation via `/ecw:{skill-name}`.

| Command | Description |
|---------|------------|
| `/ecw-init` | Initialize project ECW configuration |
| `/ecw-validate-config` | Check configuration completeness and correctness |
| `/ecw-upgrade` | Upgrade project ECW configuration to latest plugin version |
