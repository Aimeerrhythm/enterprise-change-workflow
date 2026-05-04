---
name: risk-classifier
description: >
  BLOCKING — Invoke IMMEDIATELY when user proposes any code change, requirement,
  or bug. Run BEFORE reading code/docs. Classifies risk (P0-P3) for downstream workflow.
---

# Risk Classifier

## Overview

Classify risk level (P0~P3) for any code change, **driving the depth of downstream workflow**. Executed in three phases: Phase 1 (requirement description stage, quick pre-assessment), Phase 2 (after plan completion, precise classification), Phase 3 (after implementation, calibrate prediction accuracy based on biz-impact-analysis feedback).

**Output language**: Read `ecw.yml` → `project.output_language`. All artifact headings, table headers, and labels in `phase2-assessment.md` follow this language. `session-state.md` field keys stay English (machine-parsed).

**Core Principle:** The process for changing a log statement should not be as heavy as changing inventory deduction logic.

**Announce at start:** "Using ecw:risk-classifier to classify change risk level."

**Mode switch**: Update the MODE marker in session-state.md with YAML: `<!-- ECW:MODE:START -->` / `working_mode: analysis` / `<!-- ECW:MODE:END -->`.

## TDD Phase Notes

**TDD:RED** in routing tables means writing failing tests before implementation code. Invoke `ecw:tdd` which differentiates by risk level (P0: mandatory + verification logs, P1: mandatory, P2: simplified, P3: recommended). When ecw.yml `tdd.enabled: false`, all mandatory downgrades to recommended. Skip confirmation details: see `ecw:tdd` Skip Confirmation Protocol.

## Bug Fix Routing

Bug fixes go through this skill for risk pre-assessment, then chain to `ecw:systematic-debugging`. See `./workflow-routes.yml` for full routing. All levels skip ecw:requirements-elicitation.

## When to Use

- User proposes any requirement, feature change, bug fix, or code modification
- User says "I want to...", "need to change...", "add a feature...", "fix this..."
- **Must execute before ecw:requirements-elicitation**
- **Bug fixes must also go through this skill first**, then route to systematic-debugging

**When NOT to use:**
- Pure code reading/analysis/questions ("What does this class do?")
- User explicitly says "use PX" (manually specified level, skip auto-classification)
- Phase 1 already completed in current session and level not contested

## Skill Interaction

**This skill is the entry point for all change-type tasks.** After Phase 1, link to downstream skills based on risk level.

Read `./workflow-routes.yml` for the complete routing matrix, including:
- Requirement changes (single-domain and cross-domain routing)
- Bug fix routing
- Fast track routing
- Implementation strategy selection (direct vs ecw:impl-orchestration)
- Post-implementation task creation rules

> **Determination method:** During Step 1 domain identification, check the project CLAUDE.md domain routing section (keyword→domain mapping table) and count matched domains. 2+ domain matches = cross-domain requirement.
>
> **Confirmation node merge:** risk-classifier's AskUserQuestion outputs level + domain list + mode + downstream routing in one go. After user confirms, downstream skills (ecw:domain-collab / ecw:requirements-elicitation) **skip their own confirmation step** and execute directly.

### Implementation Strategy Selection

**Implementation strategy is determined after ecw:writing-plans completes, before entering implementation.** Based on three dimensions from the Plan file: (1) Task count, (2) total unique files involved across all Tasks, (3) number of domains whose code is modified. Scan all Tasks in the Plan to count files: aggregate `file_path` references in each Task, deduplicate, and count unique files. Count domains by mapping file paths through `ecw-path-mappings.md`.

See `./workflow-routes.yml` `impl_strategy` section for the full decision matrix.

**Relationship with impl-verify**:
- `ecw:impl-orchestration` has built-in per-task spec review + code quality review (P0), providing **immediate feedback** during implementation to prevent error cascading
- `ecw:impl-verify` performs cross-validation from requirements/domain knowledge/Plan/engineering standards **after all implementation completes** — a higher-level correctness check
- The two complement each other; neither replaces the other

---

## Phase 1: Quick Pre-Assessment

### Trigger Timing

After user describes requirement, **before the first downstream skill triggers**.

### Execution Steps

Read `./prompts/phase1-steps.md` for Phase 1 reasoning steps (keyword extraction, shared resource check, composite assessment).

### Phase 1 Output Format

Read `./phase1-output-template.md` for output format and user confirmation flow.

### State Persistence

After Phase 1 user confirmation, write ECW state to `.claude/ecw/session-data/{workflow-id}/session-state.md`. Generate `{workflow-id}` as `{YYYYMMDD}-{xxxx}` where `YYYYMMDD` comes from the `currentDate` system-reminder (reliable local date) and `xxxx` is a 4-digit random hex suffix (e.g., `20260429-a3f1`). Do NOT use Claude's internal time perception for the date or time component — it drifts from local timezone. Create the directory on first write.

**Before writing**, Read `./session-state-format.md` for the exact template, marker conventions, working modes, session data path conventions, and context advisory.

**REQUIRED — marker structure (non-negotiable):** The file MUST use `<!-- ECW:STATUS:START -->` / `<!-- ECW:STATUS:END -->` to wrap all status fields (`risk_level`, `auto_continue`, `routing`, `next`, etc.) in YAML format. Plain Markdown headings or bullet lists outside these markers are **not valid** — the auto-continue hook and session-recovery hooks use `parse_status()` which only reads YAML inside the marker-delimited STATUS section. Writing without markers (or with Markdown bold format instead of YAML) causes silent hook failure and breaks the entire downstream skill chain.

Record Subagent Ledger timestamps: note time before dispatch (`Started`, HH:mm) and compute elapsed time after return (`Duration`). Purposes: restore context in new sessions, user state viewing, monitoring scripts.

### Route Task Creation

After Phase 1 user confirmation, create pending Tasks for **post-implementation** workflow steps to prevent omission. See `./workflow-routes.yml` `post_impl_tasks` for rules per risk level.

**Creation method**: Use TaskCreate tool, set blockedBy dependency chain. **After all Tasks are created, update `session-state.md`'s `post_implementation_tasks` field with actual Task IDs** (e.g., `impl-verify(#3) → biz-impact-analysis(#4)`):

1. TaskCreate: **"ecw:impl-verify — Implementation correctness verification"** (pending)
2. TaskCreate: **"ecw:biz-impact-analysis — Business impact analysis"** (P0/P1 only, blockedBy: impl-verify)
3. TaskCreate: **"Phase 3 Calibration — Risk classification feedback"** (P0/P1 only, blockedBy: biz-impact-analysis)

> These Tasks remain visible during implementation (TaskList). Bug fixes follow the same pattern.

---

## Fast Track

### Applicable Scenarios

- Production incident emergency fix (hotfix)
- User explicitly says "urgent" / "hotfix" / "production issue" / "fix first, process later"

### Execution Logic

> Workflow steps and skip items are in the file specified by ecw.yml `paths.risk_factors` §Fast Track.

Key points: Retain Phase 1 to record level → 1-round simplified confirmation → lean plan → implementation (skip TDD) + mvn test → `ecw:impl-verify` → post-hoc `ecw:biz-impact-analysis` (tagged `[Fast Track]`) → Phase 3 calibration (tagged `[Fast Track]`).

### Fast Track Output

Read `./fast-track-output-template.md` for fast track output format.

---

## Phase 2: Precise Classification

> **One-liner**: Phase 1 guesses from keywords; Phase 2 queries the dependency graph. Executes automatically for P0/P1 after requirement analysis completes, before ecw:writing-plans.

### Quick Reference

| Item | Details |
|------|---------|
| **Who executes** | risk-classifier dispatches a subagent (`model: sonnet`, default from `models.defaults.verification`; configurable via ecw.yml) to query dependency graph; coordinator holds only structured YAML result |
| **When** | After ecw:requirements-elicitation / ecw:domain-collab completes, before ecw:writing-plans |
| **Applicable** | P0/P1 (have requirement analysis artifacts) |
| **Not applicable** | P2 (Phase 1 lightweight check already covered), P3, Bug fixes (skip requirement analysis, go directly to systematic-debugging) |
| **Input** | List of changed components from requirement analysis output |
| **Output** | Precise level + upgrade/downgrade handling |
| **Upgrade** | Mandatory: backfill missing workflow steps |
| **Downgrade** | Suggested: user may simplify, user decides |

**Important:** When outputting Phase 1, add "Phase 2 Precise Classification" to TaskCreate todo list to prevent omission.

### Subagent Dispatch

Coordinator dispatches a single subagent to execute Steps 1-4:

**Coordinator constructs prompt with:**
- Requirement summary + changed component list (from requirements-elicitation or domain-collab conclusion)
- Phase 1 pre-assessment result (P level + domains, from session-state.md)
- 5 knowledge file paths: cross-domain-calls.md, mq-topology.md, shared-resources.md, external-systems.md, e2e-paths.md (read paths from ecw.yml `paths.knowledge_common`)
- knowledge-summary.md path (if exists under `.claude/ecw/session-data/{workflow-id}/`, subagent uses it to reduce original file reads)
- Risk factor file path (from ecw.yml `paths.risk_factors`)

> **Knowledge file robustness**: Pass all paths to subagent. Missing files → subagent logs `[Warning: {file} not found]` and continues with available data (see Error Handling).

**Subagent return schema**: Read `./phase2-subagent-schema.md` for the expected YAML structure and validation rules.

**Model**: `model: sonnet` (default from `models.defaults.verification`; configurable via ecw.yml). Reason: dependency graph query is rule-based lookup, not creative reasoning.

**Timeout**: 180s. If subagent has not returned within this time, terminate and fall back to Phase 1 level (see Error Handling).

### Execution Steps

Read `./prompts/phase2-subagent-steps.md` for the subagent's reasoning steps (component extraction, dependency graph query, change type analysis, re-assessment).

### Step 5: Compare with Phase 1, Handle Upgrades/Downgrades

| Scenario | Action |
|----------|--------|
| Phase 2 > Phase 1 (upgrade) | **Mandatory**: Inform user, backfill missing workflow steps |
| Phase 2 < Phase 1 (downgrade) | **Suggested**: Inform user that downstream workflow can be simplified, user decides |
| Phase 2 = Phase 1 | Confirm assessment, continue execution |

**Coordinator receives YAML**, then:
- Execute Step 5 (compare + handle upgrades/downgrades) based on YAML data
- Output Phase 2 report in the defined format
- Write checkpoint to `.claude/ecw/session-data/{workflow-id}/phase2-assessment.md` (see Session Data Path Convention for path resolution)

### Phase 2 Output Format

**Before generating Phase 2 report**, Read `./phase2-output-template.md` for the exact output structure.

> **Downstream Handoff**: After outputting Phase 2 report and writing checkpoint, update session-state.md `next` field (YAML key, inside the `<!-- ECW:STATUS:START/END -->` marker block) and invoke the next skill in the routing chain (typically `ecw:writing-plans`).

---

## Phase 3: Feedback Calibration (Post-Implementation)

> **One-liner**: Phase 1/2 predict by rules; Phase 3 validates prediction accuracy using actual biz-impact-analysis data and outputs configuration calibration suggestions.

### Quick Reference

| Item | Details |
|------|---------|
| **Who executes** | risk-classifier itself (no agent dispatch) |
| **When** | Automatically after ecw:biz-impact-analysis report is produced |
| **Applicable** | P0/P1 (mandatory), P2 (suggested), Fast Track (execute alongside post-hoc biz-impact-analysis) |
| **Not applicable** | P3 (no biz-impact-analysis, no Phase 3) |
| **Input** | Phase 1/Phase 2 prediction data + ecw:biz-impact-analysis report |
| **Output** | Calibration suggestions (does not auto-modify configuration) |

### Trigger Timing

After ecw:biz-impact-analysis completes, executed by the current session's workflow driver (i.e., when the "Phase 3 Calibration" Task from route task creation becomes executable, AI executes this section's logic). No Agent dispatch. Prerequisites: Phase 1 or Phase 2 produced a risk level in current session, and ecw:biz-impact-analysis report has been generated.

### Execution Steps

Read `./prompts/phase3-steps.md` for Phase 3 reasoning steps (compare predicted vs actual, determine accuracy, output suggestions, persist records).

### Notes

- Phase 3 **does not auto-modify any configuration files**, only outputs suggestions
- Calibration records are auto-appended to `calibration-log.md`; accumulated records can be used to identify systematic deviation patterns
- Instincts are auto-extracted to `instincts.md`; high-confidence instincts (>0.7) are injected by SessionStart hook to influence future Phase 1 assessments
- Fast Track post-hoc biz-impact-analysis also triggers Phase 3

---

## Manual Trigger

In addition to automatic triggering, the following manual scenarios are supported:

| Command | Purpose |
|---------|---------|
| `/risk-classify` | Manually trigger Phase 1 for current requirement |
| `/risk-classify P0` | Manually force-assign level, skip auto-classification |
| `/risk-classify --recheck` | Re-execute Phase 2 (use when scope expansion discovered mid-implementation) |
| `/risk-classify --hotfix` | Enter Fast Track, use simplified fix workflow |
| `/risk-classify --phase3` | Execute Phase 3 calibration (use after biz-impact-analysis report is produced) |

---

## Error Handling

**Standard ECW error recovery patterns applicable to this skill:**

| Scenario | Handling |
|----------|---------|
| Phase 2 subagent returns empty or malformed YAML | Record `FAILED` in Subagent Ledger → retry once with explicit "return YAML only" instruction → still fails: output `[DEGRADED: Phase 2 unavailable, proceeding with Phase 1 level]` and skip Phase 2 |
| Knowledge file missing (`shared-resources.md`, `mq-topology.md`, risk factors file, etc.) | Log `[Warning: {file} not found, analysis degraded]` → continue with available data. Phase 1: skip corresponding check dimension. Phase 2 subagent: pass available paths only |
| `session-state.md` write failure | Retry once → still fails: output session state content directly in conversation so user can manually save |
| `phase2-assessment.md` / `calibration-log.md` / `calibration-history.md` / `instincts.md` write failure | Retry once → still fails: output content in conversation and continue workflow |

## Supplementary Files

- `workflow-routes.yml` — Routing matrix (single source of truth) + implementation strategy + post-impl tasks
- `prompts/phase1-steps.md` — Phase 1 reasoning steps
- `prompts/phase2-subagent-steps.md` — Phase 2 subagent reasoning steps
- `prompts/phase3-steps.md` — Phase 3 calibration reasoning steps
- `prompts/common-mistakes.md` — Anti-patterns checklist
- `phase1-output-template.md` — Phase 1 output format and confirmation flow
- `phase2-output-template.md` — Phase 2 precise classification report format
- `phase2-subagent-schema.md` — Phase 2 subagent YAML return schema
- `phase3-output-template.md` — Phase 3 calibration output (3 variants by determination)
- `phase3-calibration-formats.md` — Steps 4-6 file formats: calibration-log, calibration-history, instincts
- `fast-track-output-template.md` — Fast track output format
- `session-state-format.md` — Session state file template, marker conventions, working mode definitions, context advisory
