---
name: risk-classifier
description: >
  BLOCKING — Invoke IMMEDIATELY when user proposes any requirement or feature change.
  Run BEFORE reading code/docs. Classifies risk (P0-P3) for downstream workflow.
---

# Risk Classifier

## Overview

Classify risk level (P0~P3) for any **requirement or feature change**, driving the depth of downstream workflow.

> **For bug fixes**: Use `ecw:systematic-debugging` directly — it is the entry point for all bug fix workflows.

**Output language**: Read `ecw.yml` → `project.output_language`. All artifact headings, table headers, and labels follow this language. `session-state.json` field keys stay English (machine-parsed).

**Core Principle:** The process for changing a log statement should not be as heavy as changing inventory deduction logic.

**Announce at start:** "Using ecw:risk-classifier to classify change risk level."

## TDD Phase Notes

**TDD:RED** in routing tables means writing failing tests before implementation code. Invoke `ecw:tdd` which differentiates by risk level (P0: mandatory + verification logs, P1: mandatory, P2: simplified, P3: recommended). When ecw.yml `tdd.enabled: false`, all mandatory downgrades to recommended. Skip confirmation details: see `ecw:tdd` Skip Confirmation Protocol.

## When to Use

- User proposes any requirement, feature change, or code modification
- User says "I want to...", "need to change...", "add a feature...", "implement..."
- **Must execute before ecw:requirements-elicitation**

**When NOT to use:**
- Pure code reading/analysis/questions ("What does this class do?")
- User explicitly says "use PX" (manually specified level, skip auto-classification)
- Initial risk assessment already completed in current session and level not contested
- **Bug fixes** — use `ecw:systematic-debugging` as the entry point instead

## Skill Interaction

**This skill is the entry point for all requirement-type tasks.** After the initial risk assessment, the auto-continue hook rebuilds the complete routing chain from `routing[0] + tail(risk_level)`. LLM writes only `risk_level` and `routing[0]`; the hook computes the remaining chain.

`routing[0]` values:
- `ecw:requirements-elicitation` — single-domain requirement
- `ecw:domain-collab` — cross-domain requirement
- `ecw:writing-plans` — P2 entry (no requirement analysis needed)
- (omit routing field entirely) — P3 direct implementation

Read `./workflow-routes.yml` for the complete routing matrix, including:
- Requirement changes (single-domain and cross-domain routing)
- Fast track routing
- Implementation strategy selection (direct vs ecw:impl-orchestration)
- Post-implementation task creation rules

> **Determination method:** During Step 1 domain identification, check the project CLAUDE.md domain routing section (keyword→domain mapping table) and count matched domains. 2+ domain matches = cross-domain requirement.
>
> **Confirmation node merge:** risk-classifier's AskUserQuestion outputs level + domain list + mode + downstream routing in one go. After user confirms, downstream skills (ecw:domain-collab / ecw:requirements-elicitation) **skip their own confirmation step** and execute directly.

### Implementation Strategy Selection

**Determined after ecw:writing-plans completes, before entering implementation.** Scan all Tasks in the Plan: aggregate `file_path` references, deduplicate for unique file count. Count domains by mapping file paths through `ecw-path-mappings.md`. See `./workflow-routes.yml` `impl_strategy` for the full decision matrix.

**Relationship with impl-verify**:
- `ecw:impl-orchestration` has built-in per-task spec review + code quality review (P0), providing **immediate feedback** during implementation to prevent error cascading
- `ecw:impl-verify` performs cross-validation from requirements/domain knowledge/Plan/engineering standards **after all implementation completes** — a higher-level correctness check
- The two complement each other; neither replaces the other

---

## Initial Risk Assessment

### Trigger Timing

After user describes requirement, **before the first downstream skill triggers**.

### Execution Steps

Read `./prompts/risk-assessment-guide.md` for risk assessment steps (keyword extraction, shared resource check, composite assessment).

### Assessment Output Format

Use the "Assessment Output and Confirmation Flow" section in `./prompts/risk-assessment-guide.md`.

### State Persistence

After user confirmation of the initial risk assessment, write ECW state to `.claude/ecw/session-data/{workflow-id}/session-state.json`.

Read `./session-state-format.md` for the exact JSON schema, field reference, workflow ID generation, conflict detection, and context advisory.

**Routing field:** Write only `routing[0]` (the first downstream skill). The auto-continue hook reconstructs the full chain from `routing[0] + tail(risk_level)` after this skill completes.

### Route Task Creation

After user confirmation of the initial risk assessment, create pending Tasks for **post-implementation** workflow steps to prevent omission. See `./workflow-routes.yml` `post_impl_tasks` for rules per risk level.

**Creation method**: Use TaskCreate tool, set blockedBy dependency chain:

1. TaskCreate: **"ecw:impl-verify — Implementation correctness verification"** (pending)
2. TaskCreate: **"ecw:biz-impact-analysis — Business impact analysis"** (P0/P1 only, blockedBy: impl-verify)

> These Tasks remain visible during implementation (TaskList).

---

## Fast Track

### Applicable Scenarios

- Production incident emergency fix (hotfix)
- User explicitly says "urgent" / "hotfix" / "production issue" / "fix first, process later"

### Execution Logic

Key points: retain the initial risk assessment to record level → 1-round simplified confirmation → lean plan → implementation (skip TDD) + mvn test → `ecw:impl-verify` → post-hoc `ecw:biz-impact-analysis` (tagged `[Fast Track]`).

### Fast Track Output

Fast Track uses the same risk assessment output, then appends:

```markdown
### Mode: Fast Track

> Entered emergency fix mode. Skipping full requirement elicitation, spec-challenge, and TDD.
> Will run ecw:biz-impact-analysis post-fix.

### Quick Confirmation (3 questions)
1. What is the issue symptom and impact scope?
2. Fix approach (what to change, how to change)?
3. Is there a temporary mitigation already deployed?
```

---

## Manual Trigger

In addition to automatic triggering, the following manual scenarios are supported:

| Command | Purpose |
|---------|---------|
| `/risk-classify` | Manually trigger risk assessment for current requirement |
| `/risk-classify P0` | Manually force-assign level, skip auto-classification |
| `/risk-classify --recheck` | Re-run risk assessment (use when scope expansion discovered mid-implementation) |
| `/risk-classify --hotfix` | Enter Fast Track, use simplified fix workflow |

---

## Error Handling

**Standard ECW error recovery patterns applicable to this skill:**

| Scenario | Handling |
|----------|---------|
| Knowledge file missing (`shared-resources.md`, `mq-topology.md`, risk factors file, etc.) | Log `[Warning: {file} not found, analysis degraded]` → continue with available data. Skip the corresponding assessment dimension |
| `session-state.json` write failure | Retry once → still fails: output session state content directly in conversation so user can manually save |

## Supplementary Files

- `workflow-routes.yml` — Routing matrix (single source of truth) + implementation strategy + post-impl tasks
- `prompts/risk-assessment-guide.md` — Risk assessment steps + output and confirmation flow
- `prompts/common-mistakes.md` — Anti-patterns checklist
- `session-state-format.md` — Session state file template, marker conventions, working mode definitions, context advisory
