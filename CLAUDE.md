# Enterprise Change Workflow (ECW) Plugin

## Overview

ECW provides structured change management workflows for large multi-module projects. Core capabilities:

1. **Risk Classification** (`ecw:risk-classifier`) — Classify code changes as P0~P3, driving downstream workflow depth
2. **Multi-Domain Collaboration Analysis** (`ecw:domain-collab`) — Parallel analysis + cross-validation for cross-domain requirements
3. **Requirements Elicitation** (`ecw:requirements-elicitation`) — Systematic questioning until full requirement understanding
4. **Implementation Planning** (`ecw:writing-plans`) — Risk-aware Plan writing + domain context injection
5. **Adversarial Review** (`ecw:spec-challenge`) — Independent adversarial review after plan production
6. **Test-First** (`ecw:tdd`) — Risk-differentiated TDD workflow + ecw.yml linkage
7. **Implementation Orchestration** (`ecw:impl-orchestration`) — Subagent-driven Plan execution + risk-aware review
8. **Systematic Debugging** (`ecw:systematic-debugging`) — Domain knowledge-driven root cause analysis + cross-domain tracing
9. **Implementation Correctness Verification** (`ecw:impl-verify`) — Multi-dimensional convergence verification: code ↔ requirements/rules/Plan/standards
10. **Business Impact Analysis** (`ecw:biz-impact-analysis`) — Analyze impact on business processes after code changes
11. **Cross-File Consistency Verification** (`ecw:cross-review`) — Inter-file structural consistency verification (manual optional tool)
12. **Knowledge Base Audit** (`ecw:knowledge-audit`) — Knowledge base health check: content composition, stale references, three-criteria compliance
13. **Knowledge Utilization Tracking** (`ecw:knowledge-track`) — Post-task doc utilization tracking (hit/miss/redundant/misleading)
14. **Code Structure Index** (`ecw:knowledge-repomap`) — Auto-generate Repo Map from component_types configuration
15. **Multi-Repo Workspace** (`ecw:workspace`) — Cross-service workspace with git worktree isolation + multi-session parallel development

## Workflow

```
ecw:risk-classifier (Phase 1 quick pre-assessment)
  ├─ Single-domain → ecw:requirements-elicitation → Phase 2 → ecw:writing-plans → [P0: ecw:spec-challenge]
  ├─ Cross-domain → ecw:domain-collab → Phase 2 → ecw:writing-plans → [P0/P1 cross-domain: ecw:spec-challenge]
  ├─ P2 → ecw:writing-plans
  ├─ P3 → Direct implementation
  └─ Bug → ecw:systematic-debugging
Post-implementation → ecw:impl-verify → ecw:biz-impact-analysis → [P0/P1: Phase 3 feedback calibration]
```

## Dependencies

- **No external plugin dependencies** — ECW is self-contained with all Skills (writing-plans, tdd, systematic-debugging, impl-orchestration, etc.); no other plugins needed.
- **BLOCKING RULE — Skill trigger priority**: When user proposes any change, requirement, or bug fix, invoke `ecw:risk-classifier` IMMEDIATELY — before reading code, before reading documentation, before any analysis. This is the unified entry point; all downstream workflow depth is determined by its classification result. Skipping this step means the entire ECW workflow will not activate.

## Project Configuration

**Important: Domain routing and business knowledge are defined in your project, not in this plugin.**

Run `/ecw-init` after installation for project initialization, or manually create the following files:

### Required Files

| File | Purpose |
|------|---------|
| `.claude/ecw/ecw.yml` | Project config (name, language, component types, scan patterns, paths) |
| `.claude/ecw/domain-registry.md` | Domain registry (domain definitions, knowledge directories, code directories) |
| `.claude/ecw/change-risk-classification.md` | Risk factor calibration (keyword→level mapping, sensitivity definitions) |
| `.claude/ecw/ecw-path-mappings.md` | Code path→domain mapping (used by biz-impact-analysis) |

### ECW Artifact Files (auto-generated)

| File | Write Timing | Purpose |
|------|-------------|---------|
| `.claude/ecw/session-data/{workflow-id}/session-state.md` | After risk-classifier Phase 1 output | ECW workflow state record + Subagent Ledger, for new session recovery |
| `.claude/ecw/session-data/{workflow-id}/domain-collab-report.md` | After domain-collab Round 3 completes | Full multi-domain collaboration analysis report |
| `.claude/ecw/session-data/{workflow-id}/knowledge-summary.md` | After domain-collab Round 3 completes | Knowledge file summary, reused across skills |
| `.claude/ecw/session-data/{workflow-id}/spec-challenge-report.md` | After spec-challenge agent returns | Adversarial review report |
| `.claude/ecw/session-data/{workflow-id}/requirements-summary.md` | After requirements-elicitation completes | Requirement summary checkpoint for downstream cold-start |
| `.claude/ecw/session-data/{workflow-id}/phase2-assessment.md` | After risk-classifier Phase 2 completes | Phase 2 structured conclusion for downstream cold-start |
| `.claude/ecw/session-data/{workflow-id}/impl-verify-findings.md` | After each impl-verify pass | All findings (replaces >5 threshold) |
| `.claude/ecw/calibration-log.md` | After Phase 3 calibration | Full-dimension comparison log (detailed tables for human review and pattern analysis) |
| `.claude/ecw/state/calibration-history.md` | After Phase 3 calibration | Concise structured index for Phase 1 automated quick-lookup |
| `.claude/ecw/state/instincts.md` | After Phase 3 calibration | Learned heuristic rules, injected by SessionStart when confidence > 0.7 |
| `.claude/ecw/knowledge-ops/doc-tracker.md` | After each knowledge-track run | Doc utilization tracking records (hit/miss/redundant/misleading) |
| `.claude/ecw/knowledge-ops/repo-map.md` | After knowledge-repomap / ecw-init | Auto-generated code structure index |
| `.claude/ecw/state/stale-refs.md` | After knowledge-audit run | Stale reference findings, consumed by verify-completion hook |
| `.claude/ecw/workspace.yml` | After workspace create | Workspace config: services, branches, build settings (workspace root only) |
| `.claude/ecw/session-data/{workflow-id}/cross-service-plan.md` | After workspace run Phase 1-3 | Cross-service change plan: dependencies, contracts, execution order |
| `{service}/.claude/ecw/workspace-task.md` | Before workspace run Phase 4 | Per-service task dispatched to child session |
| `{service}/status.json` | After child session completes | Child session completion marker, read by coordinator |

### Knowledge Files (populate as needed)

| File | Purpose |
|------|---------|
| `.claude/knowledge/common/cross-domain-rules.md` | Cross-domain call rules and global constraints |
| `.claude/knowledge/common/cross-domain-calls.md` | Cross-domain direct call matrix |
| `.claude/knowledge/common/mq-topology.md` | MQ Topic publish/consume relationships |
| `.claude/knowledge/common/shared-resources.md` | Cross-domain shared resource table |
| `.claude/knowledge/common/external-systems.md` | External system integrations |
| `.claude/knowledge/common/e2e-paths.md` | End-to-end critical paths |

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

| Skill | Auto Trigger | Manual Trigger |
|-------|-------------|---------------|
| ecw:risk-classifier | User proposes change/requirement/bug | `/ecw:risk-classifier` |
| ecw:domain-collab | risk-classifier routes (cross-domain) | `/ecw:domain-collab <description>` |
| ecw:requirements-elicitation | risk-classifier routes (single-domain P0/P1) | `/ecw:requirements-elicitation` |
| ecw:writing-plans | After requirement analysis/Phase 2 (P0-P2) | `/ecw:writing-plans` |
| ecw:spec-challenge | After ecw:writing-plans (P0 any; P1 cross-domain only) | `/ecw:spec-challenge <file>` |
| ecw:tdd | Before implementation code (P0-P2, risk-classifier routes) | `/ecw:tdd` |
| ecw:impl-orchestration | During Plan execution (4+ Tasks, P0/P1) | `/ecw:impl-orchestration` |
| ecw:systematic-debugging | Bug/test failure (risk-classifier routes) | `/ecw:systematic-debugging` |
| ecw:impl-verify | After implementation (P0-P2) | `/ecw:impl-verify` |
| ecw:biz-impact-analysis | After impl-verify | `/ecw:biz-impact-analysis [range]` |
| ecw:cross-review | — | `/ecw:cross-review` (manual optional) |
| ecw:knowledge-audit | — | `/ecw:knowledge-audit` (manual, periodic) |
| ecw:knowledge-track | — | `/ecw:knowledge-track` (manual, post-task) |
| ecw:knowledge-repomap | — | `/ecw:knowledge-repomap` (manual, after refactors) |
| ecw:workspace | User mentions multiple services/repos for cross-service development | `/ecw:workspace create\|run\|status\|push\|destroy` |

| Command | Description |
|---------|------------|
| `/ecw-init` | Initialize project ECW configuration |
| `/ecw-validate-config` | Check configuration completeness and correctness |
| `/ecw-upgrade` | Upgrade project ECW configuration to latest plugin version |
