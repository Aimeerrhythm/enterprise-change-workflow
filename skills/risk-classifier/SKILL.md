---
name: risk-classifier
description: >
  Use BEFORE any other skill when user proposes a change, feature, requirement,
  bug fix, or any code modification. MUST run before ecw:requirements-elicitation
  or ecw:domain-collab — if either would normally trigger, run this first.
---

# Risk Classifier

## Overview

Classify risk level (P0~P3) for any code change, **driving the depth of downstream workflow**. Executed in three phases: Phase 1 (requirement description stage, quick pre-assessment), Phase 2 (after plan completion, precise classification), Phase 3 (after implementation, calibrate prediction accuracy based on biz-impact-analysis feedback).

**Core Principle:** The process for changing a log statement should not be as heavy as changing inventory deduction logic.

## TDD Phase Notes

**TDD:RED** in routing tables means writing failing tests before implementation code. This is a structural step in the ECW pipeline, not an optional suggestion.

### Execution

When TDD:RED phase triggers, invoke `ecw:tdd` skill to execute the Red-Green-Refactor cycle. `ecw:tdd` differentiates by risk level: P0 includes verification logs, P1 full cycle, P2 simplified mode, P3 recommended but not mandatory.

### Risk-Level Differentiation

| Level | TDD Requirement | Details |
|-------|----------------|---------|
| P0-P2 | **Mandatory** | After plan completion (P0 includes spec-challenge), write failing tests covering plan test scenarios first, then write implementation code |
| P3 | **Recommended** | Routing does not include TDD step; user decides whether to test first |
| Bug | **Mandatory** | After systematic-debugging locates root cause, write a failing test that reproduces the bug, then fix |
| Fast Track | **Skip** | Fix speed takes priority; TDD not applicable; verify regression via mvn test after fix |

> **Configuration linkage**: When ecw.yml `tdd.enabled` is set to `false`, all "mandatory" above downgrades to "recommended" — user decides whether to test first.

### Skip Confirmation

TDD:RED for P0-P2 is a mandatory step with no skip option by default.

If user strongly requests to skip TDD during P0-P2 flow, use AskUserQuestion to confirm risk before allowing skip:
```
Question: "Confirm skip TDD? Without TDD, test coverage relies on post-implementation mvn test."
Options:
  1. "Continue TDD (Recommended)" — Write failing tests first, then implement
  2. "Skip TDD" — Implement directly (skip test-first)
```

## Bug Fix Routing

Bug fixes also go through this skill for risk pre-assessment first, then chain to `ecw:systematic-debugging` for diagnosis and fix:

```
bug report → risk-classifier (Phase 1, quick pre-assessment)
  → systematic-debugging (locate root cause)
  → TDD:RED (write failing test reproducing the bug)
  → fix (GREEN, make test pass)
  → mvn test (full regression)
  → ecw:impl-verify
  → ecw:biz-impact-analysis (if P0/P1)
  → Phase 3 calibration (automatic)
```

Regardless of risk level, bug fixes skip ecw:requirements-elicitation (bugs need diagnosis and fix, not requirement elicitation).

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

**This skill is the entry point for all change-type tasks.** After Phase 1, link to downstream skills based on risk level:

### Requirement Changes — Single Domain (Step 1 matches 0~1 domains)

| Risk Level | Downstream Skills |
|-----------|-------------------|
| P0 (Critical) | → `ecw:requirements-elicitation` → **Phase 2** → `ecw:writing-plans` → `ecw:spec-challenge` → **TDD:RED** → Implementation(GREEN) → `ecw:impl-verify` → `ecw:biz-impact-analysis` → **Phase 3** |
| P1 (High) | → `ecw:requirements-elicitation` → **Phase 2** → `ecw:writing-plans` → **TDD:RED** → Implementation(GREEN) → `ecw:impl-verify` → `ecw:biz-impact-analysis` → **Phase 3** |
| P2 (Medium) | → `ecw:writing-plans` → **TDD:RED** → Implementation(GREEN) → `ecw:impl-verify` |
| P3 (Low) | → Direct implementation (TDD recommended but not mandatory) |

### Requirement Changes — Cross-Domain (Step 1 matches 2+ domains)

When requirements span multiple business domains, use `ecw:domain-collab` (multi-domain collaboration analysis) **instead of** `ecw:requirements-elicitation`. ecw:domain-collab already includes per-domain deep analysis + Coordinator cross-validation, producing sufficient output to drive plan writing.

| Risk Level | Downstream Skills |
|-----------|-------------------|
| P0 (Critical) | → `ecw:domain-collab` (multi-domain) → **Phase 2** → `ecw:writing-plans` → `ecw:spec-challenge` → **TDD:RED** → Implementation(GREEN) → `ecw:impl-verify` → `ecw:biz-impact-analysis` → **Phase 3** |
| P1 (High) | → `ecw:domain-collab` (multi-domain) → **Phase 2** → `ecw:writing-plans` → `ecw:spec-challenge` → **TDD:RED** → Implementation(GREEN) → `ecw:impl-verify` → `ecw:biz-impact-analysis` → **Phase 3** |
| P2 (Medium) | → `ecw:domain-collab` (multi-domain) → `ecw:writing-plans` → **TDD:RED** → Implementation(GREEN) → `ecw:impl-verify` → `ecw:biz-impact-analysis` (suggested) |
| P3 (Low) | → `ecw:domain-collab` (multi-domain, simplified output) → Direct implementation (TDD recommended but not mandatory) |

> **Determination method:** During Step 1 domain identification, check the project CLAUDE.md domain routing section (keyword→domain mapping table) and count matched domains. 2+ domain matches = cross-domain requirement.
>
> **Confirmation node merge:** risk-classifier's AskUserQuestion outputs level + domain list + mode + downstream routing in one go. After user confirms, downstream skills (ecw:domain-collab / ecw:requirements-elicitation) **skip their own confirmation step** and execute directly.

### Implementation Strategy Selection

The "Implementation(GREEN)" in routing tables requires choosing implementation approach based on three dimensions: Task count, file count, and domain count:

| Condition | Strategy | Rationale |
|-----------|----------|-----------|
| Plan Tasks ≤ 3, involved files ≤ 5, single domain | **Direct implementation** (complete sequentially in main session) | Few tasks + few files; subagent dispatch overhead not worthwhile |
| Plan Tasks ≤ 3, but involved files ≥ 6 | **`ecw:impl-orchestration`** | File operations intensive; coordinator context will overflow |
| Plan Tasks ≤ 3, but ≥ 2 domains' code modifications | **`ecw:impl-orchestration`** | Cross-domain file spread increases context consumption |
| Plan Tasks 4-8, P0/P1 | **`ecw:impl-orchestration`** | Many complex tasks; subagent parallelism adds value |
| Plan Tasks 4-8, P2 | **Direct implementation** | Medium risk; parallelization overhead unnecessary |
| Plan Tasks > 8, P0/P1 | **`ecw:impl-orchestration`**, merge simple Tasks | Avoid subagent count explosion |
| P3 | **Direct implementation** | Low risk, no Plan |
| Bug fix, involved files ≤ 5 | **Direct implementation** | Usually single-point fix, no parallelism needed |
| Bug fix, involved files ≥ 6 | **`ecw:impl-orchestration`** | Complex bug fix spanning many files |

**Implementation strategy is determined after ecw:writing-plans completes, before entering implementation.** Based on three dimensions from the Plan file: (1) Task count, (2) total unique files involved across all Tasks, (3) number of domains whose code is modified. Scan all Tasks in the Plan to count files: aggregate `file_path` references in each Task, deduplicate, and count unique files. Count domains by mapping file paths through `ecw-path-mappings.md`.

**Rules for merging simple Tasks** (when Plan Tasks > 8):
- **Mergeable** (batch to 1-2 subagents): Single-file changes with no conditional branching — enum/constant definitions, DTO/VO new fields, Mapper single methods, config changes, doc sync
- **Must be independent**: Tasks involving state machines, cross-domain interfaces, multi-file coordination, conditional branching, or core business logic

**Relationship with impl-verify**:
- `ecw:impl-orchestration` has built-in per-task spec review + code quality review (P0), providing **immediate feedback** during implementation to prevent error cascading
- `ecw:impl-verify` performs cross-validation from requirements/domain knowledge/Plan/engineering standards **after all implementation completes** — a higher-level correctness check
- The two complement each other; neither replaces the other

### Bug Fix Changes

| Risk Level | Downstream Skills |
|-----------|-------------------|
| Any level | → invoke `ecw:systematic-debugging` (locate root cause) → **TDD:RED** (write reproduction test) → Fix(GREEN) → mvn test → `ecw:impl-verify` → ecw:biz-impact-analysis (P0/P1) → **Phase 3** |

Bug fixes skip ecw:requirements-elicitation, but risk level still determines post-fix ecw:biz-impact-analysis requirements.

**Phase 2** executes automatically after requirement analysis (ecw:requirements-elicitation / ecw:domain-collab) completes, before ecw:writing-plans (see Phase 2 section below).

---

## Phase 1: Quick Pre-Assessment

### Trigger Timing

After user describes requirement, **before the first downstream skill triggers**.

### Execution Steps

#### Step 1: Keyword Extraction & Domain Identification

Extract from user's requirement description:
- **Business keywords** → Map to domains (reference project CLAUDE.md domain routing section (keyword→domain mapping table))
- **Operation keywords** → Determine operation type (CRUD, state changes, message format, etc.)
- **Sensitive words** → Directly trigger high-risk flag
- **Domain match count** → Count how many distinct domains matched (for single-domain/cross-domain routing, see Skill Interaction)

**Domain match determination:** Read keywords from project CLAUDE.md domain routing section (keyword→domain mapping table), match against user input one by one. Record matched domain list and count, output to Phase 1 report.

**Sensitive word determination:** → Read the file specified by ecw.yml `paths.risk_factors` (default `.claude/ecw/change-risk-classification.md`) §Quick Reference for the complete keyword→estimated level mapping table. Match any sensitive word → at least P1.

#### Step 2: Quick Shared Resource Check

Read `shared-resources.md` (§3) under ecw.yml `paths.knowledge_common`, check whether classes/methods mentioned by user appear in the shared resources table.

→ Read the file specified by ecw.yml `paths.risk_factors` (default `.claude/ecw/change-risk-classification.md`) §Factor 1: Impact Scope for the domain dependency count→risk level threshold mapping.

**Note:** Phase 1 checks §3 (shared resources) + §2 (MQ topology, only check if user-mentioned keywords involve MQ Topics). Does not check §1/§4/§5 (deferred to Phase 2).

**P2 lightweight check:** For P2 single-domain requirements (skips ecw:requirements-elicitation, no requirement analysis artifacts), Phase 1's §3 + §2 check results serve as final risk signals. If shared resources or MQ Topic write-operation changes are discovered, **upgrade to P1 immediately** — do not wait for Phase 2.

#### Step 3: Composite Assessment

```
Total Risk = max(Keyword Estimated Level, Shared Resource Level)
Cross-Domain = Step 1 matched domain count >= 2 ? "cross-domain" : "single-domain"
```

> Full three-dimensional factor definitions (Impact Scope / Change Type / Business Sensitivity) are in the file specified by ecw.yml `paths.risk_factors` §Three-Dimensional Risk Factors. Phase 1 uses only the first two dimensions for quick assessment; Phase 2 uses all three.

If information is insufficient to determine, **default to P2** (better to over-process than under-process).

Look up "Total Risk + Cross-Domain determination" in the Skill Interaction routing table to determine downstream workflow.

### Phase 1 Output Format

First output a brief assessment (no more than 5 lines):

```markdown
## Change Risk Pre-Assessment (Phase 1)

**P{X}** | {single-domain/cross-domain} ({domain list}) | {multi-domain collab/B/none} | {one-line rationale}

Downstream routing: {full routing chain, e.g., ecw:domain-collab(multi-domain) → Phase 2 → ecw:writing-plans → TDD:RED → Implementation(GREEN) → ecw:biz-impact-analysis → Phase 3}
```

Then **immediately use `AskUserQuestion` tool** for user confirmation (confirm level + domains + routing in one go); do not output lengthy text waiting for manual reply. After user confirms, downstream skills execute directly without re-confirmation.

**AskUserQuestion invocation:**

```
Question: "Risk level P{X}, proceed with the above workflow?"
Options:
  1. "Proceed (Recommended)" — Execute with current level and routing
  2. "Adjust level" — Upgrade or downgrade risk level (will ask target level after selection)
  3. "Analysis only" — Complete impact analysis without entering implementation
  4. "Emergency fix" — Use fast track, skip full workflow
```

If **P0/P1 involving inventory, state machines, MQ, or other high-sensitivity changes**, prepend a multi-select confirmation question before the options:

```
Question: "Do any of the following apply? (affects risk assessment)"
multiSelect: true
Options:
  1. "Pre-release freeze period" — Currently in release freeze window
  2. "External system coordination needed" — Requires other teams to co-release
  3. "None of the above" — Neither applies
```

After user selection, execute the corresponding route directly without re-confirmation.

### State Persistence

After Phase 1 user confirmation, write ECW state to `.claude/ecw/session-state.md` (user may adjust level during confirmation; writing after confirmation ensures data accuracy):

```markdown
# ECW Session State

<!-- ECW:STATUS:START -->
- **Risk Level**: P{X}
- **Domains**: {domain list}
- **Mode**: {single-domain/cross-domain}
- **Routing**: {full routing chain}
- **Current Phase**: phase1-complete
- **Created**: {YYYY-MM-DD HH:mm}
- **Implementation Strategy**: TBD (determined after ecw:writing-plans based on Task count)
- **Post-Implementation Tasks**: {fill after Route Task Creation, e.g., "impl-verify(#3) → biz-impact-analysis(#4) → phase3(#5)"}
<!-- ECW:STATUS:END -->

<!-- ECW:MODE:START -->
- **Working Mode**: analysis
<!-- ECW:MODE:END -->

<!-- ECW:LEDGER:START -->
## Subagent Ledger

| Phase | Agent | Type | Est. Scale |
|-------|-------|------|-----------|
<!-- ECW:LEDGER:END -->
```

This file serves as the sole persistence carrier for ECW workflow state. Each skill's coordinator appends Subagent Ledger rows after Agent dispatch completes. Purposes:
- Restore context when continuing work in a new session
- User can view current ECW workflow state
- Manual recovery after compression (user says "read ECW state")
- Monitoring scripts to assess subagent consumption

> **Marker-based updates**: session-state.md uses `<!-- ECW:{NAME}:START/END -->` markers to delimit updatable sections. When updating a section (e.g. STATUS, LEDGER, MODE), only replace content between the matching markers — **never overwrite the entire file**. Standard marker names: `STATUS` (workflow fields), `MODE` (working mode), `LEDGER` (subagent table), `STOP` (auto-updated by Stop hook).

> **Working modes**: Each skill sets the `MODE` marker section on entry to declare the current working mode. This helps post-compaction recovery understand the workflow phase. Mode definitions:
>
> | Mode | Set by | Behavior |
> |------|--------|----------|
> | `analysis` | risk-classifier, requirements-elicitation, domain-collab | Focus on understanding requirements; read broadly before concluding |
> | `planning` | writing-plans, spec-challenge | Design implementation approach; prioritize cross-file consistency |
> | `implementation` | impl-orchestration, tdd, systematic-debugging | Write code; keep atomic commits; run tests after each change |
> | `verification` | impl-verify, biz-impact-analysis | Review completed work; severity-grade findings; do not modify code |
>
> **Mode switch**: When entering a skill, update the MODE marker: `<!-- ECW:MODE:START -->\n- **Working Mode**: {mode}\n<!-- ECW:MODE:END -->`

> **Session advisory — context management**:
>
> After Plan completion (writing-plans finishes), evaluate whether to continue or start a new session:
>
> | Signal | Advisory |
> |--------|----------|
> | P0/P1 with prior domain-collab or requirements-elicitation | **Strongly recommend new session** — requirement analysis + plan writing likely consumed 100K+ context |
> | P2 with Plan ≥ 5 Tasks | **Recommend new session** — TDD for many tasks will push context toward compaction threshold |
> | P2 with Plan ≤ 4 Tasks, no prior requirement analysis | **Continue** — context overhead is manageable |
> | P3 | **Continue** — no formal plan, minimal context |
>
> Full workflow for P0 cross-domain changes typically requires 500+ turns. Recommend switching to a new session after plan completion (after spec-challenge) to avoid context compression causing information loss.
>
> **New session recovery**: Tasks created by TaskCreate do not persist across sessions. When a new session reads `session-state.md` to restore context, it needs to re-create pending Tasks based on the `Post-Implementation Tasks` field (using the TaskCreate rules above).

### Route Task Creation

After Phase 1 user confirmation, create pending Tasks for **post-implementation** workflow steps to prevent omission:

| Risk Level | Tasks to Create |
|-----------|----------------|
| P0/P1 | `ecw:impl-verify` → `ecw:biz-impact-analysis` → `Phase 3 Calibration` |
| P2 | `ecw:impl-verify` (biz-impact-analysis suggested but not mandatory) |
| P3 | None |

**Creation method**: Use TaskCreate tool, set blockedBy dependency chain. **After all Tasks are created, update `session-state.md`'s `Post-Implementation Tasks` field with actual Task IDs** (e.g., `impl-verify(#3) → biz-impact-analysis(#4)`):

1. TaskCreate: **"ecw:impl-verify — Implementation correctness verification"**
   - description: "After implementation completes, execute `/ecw:impl-verify`. Pass only with zero must-fix findings. Mark this Task complete and continue to next."
   - status: pending
2. TaskCreate: **"ecw:biz-impact-analysis — Business impact analysis"** (P0/P1 only)
   - description: "After impl-verify passes, execute `/ecw:biz-impact-analysis` to analyze business impact of code changes."
   - blockedBy: [impl-verify task ID]
3. TaskCreate: **"Phase 3 Calibration — Risk classification feedback"** (P0/P1 only)
   - description: "After biz-impact-analysis report is produced, execute Phase 3 calibration to compare predicted vs. actual impact."
   - blockedBy: [biz-impact-analysis task ID]

> These Tasks remain visible during implementation (TaskList). After AI completes all implementation tasks, it will see the pending impl-verify Task and naturally proceed to the next step.
>
> **Bug fixes** follow the same pattern: All levels create `ecw:impl-verify`; P0/P1 additionally create `ecw:biz-impact-analysis` → `Phase 3 Calibration` (same blockedBy chain as requirement changes).

---

## Fast Track

### Applicable Scenarios

- Production incident emergency fix (hotfix)
- User explicitly says "urgent" / "hotfix" / "production issue" / "fix first, process later"

### Execution Logic

> Workflow steps and skip items are in the file specified by ecw.yml `paths.risk_factors` §Fast Track.

Key points: Retain Phase 1 to record level → 1-round simplified confirmation → lean plan → implementation (skip TDD) + mvn test → `ecw:impl-verify` → post-hoc `ecw:biz-impact-analysis` (tagged `[Fast Track]`) → Phase 3 calibration (tagged `[Fast Track]`).

### Fast Track Routing Table

| Risk Level | Downstream Skills |
|-----------|-------------------|
| Any level | → Phase 1 quick confirmation → lean plan (skip requirement elicitation, spec-challenge, TDD) → implementation + mvn test → `ecw:impl-verify` → `ecw:biz-impact-analysis` (tagged `[Fast Track]`) → Phase 3 calibration |

### Fast Track Output Format

Append to Phase 1 output:

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

## Phase 2: Precise Classification

> **One-liner**: Phase 1 guesses from keywords; Phase 2 queries the dependency graph. Executes automatically for P0/P1 after requirement analysis completes, before ecw:writing-plans.

### Quick Reference

| Item | Details |
|------|---------|
| **Who executes** | risk-classifier dispatches a subagent (`model: sonnet`) to query dependency graph; coordinator holds only structured YAML result |
| **When** | After ecw:requirements-elicitation / ecw:domain-collab completes, before ecw:writing-plans |
| **Applicable** | P0/P1 (have requirement analysis artifacts) |
| **Not applicable** | P2 (Phase 1 lightweight check already covered), P3, Bug fixes (skip requirement analysis, go directly to systematic-debugging) |
| **Input** | List of changed components from requirement analysis output |
| **Output** | Precise level + upgrade/downgrade handling |
| **Upgrade** | Mandatory: backfill missing workflow steps |
| **Downgrade** | Suggested: user may simplify, user decides |

**Important:** When outputting Phase 1, add "Phase 2 Precise Classification" to TaskCreate todo list to prevent omission.

### Execution Steps

#### [Subagent] Step 1: Extract Changed Component List from Requirement Analysis

Extract all components to be modified from requirement analysis results:
- ecw:requirements-elicitation → Extract entities/components from "Data Changes" and "Workflow" sections of requirement summary
- ecw:domain-collab → Extract class names and resource names from each domain's `affected_components` YAML field

> Information granularity is class-level (not method-level), sufficient for dependency graph queries.

### Subagent Dispatch

Coordinator dispatches a single subagent to execute Steps 1-4:

**Coordinator constructs prompt with:**
- Requirement summary + changed component list (from requirements-elicitation or domain-collab conclusion)
- Phase 1 pre-assessment result (P level + domains, from session-state.md)
- 5 knowledge file paths: cross-domain-calls.md, mq-topology.md, shared-resources.md, external-systems.md, e2e-paths.md (read paths from ecw.yml `paths.knowledge_common`)
- knowledge-summary.md path (if exists, subagent uses it to reduce original file reads)
- Risk factor file path (from ecw.yml `paths.risk_factors`)

**Subagent executes** Steps 1-4 internally and returns structured YAML:

```yaml
risk_level: P{X}
phase1_level: P{Y}
level_change: upgraded | downgraded | unchanged
affected_domains: [domain1, domain2]
classification_factors:
  impact_scope: {level: P{X}, details: "..."}
  change_type: {level: P{X}, details: "..."}
  business_sensitivity: {level: P{X}, details: "..."}
dependency_graph:
  cross_domain_calls: [{from: X, to: Y, method: Z}]
  mq_impacts: [{topic: T, publishers: [...], consumers: [...]}]
  shared_resources: [{resource: R, consumers: [...]}]
  external_impacts: [{system: S, direction: inbound|outbound, interface: I}]
  e2e_paths: [{path_name: P, affected_step: S}]
upgrade_reason: "..."  # if upgraded
```

**Coordinator receives YAML**, then:
- Execute Step 5 (compare + handle upgrades/downgrades) based on YAML data
- Output Phase 2 report in the defined format
- Write checkpoint to `.claude/ecw/session-data/phase2-assessment.md`

**Model**: `model: sonnet` (dependency graph query is rule-based lookup, not creative reasoning)

#### [Subagent] Step 2: Full Dependency Graph Query

**Knowledge summary priority read**: If `.claude/ecw/knowledge-summary.md` exists (generated by domain-collab), read cross-domain dependency info from that file first. Only read original knowledge files when summary file does not exist or has insufficient information.

For each affected class/method:

| Query | Data Source | Purpose |
|-------|------------|---------|
| Cross-domain calls | §1 `cross-domain-calls.md` | Who calls this class? Who does this class call? (2 hops) |
| MQ impact | §2 `mq-topology.md` | What consumers/publishers for involved Topics? |
| Shared resource fanout | §3 `shared-resources.md` | Full list of consumer domains |
| External systems | §4 `external-systems.md` | Inbound/outbound interface impact |
| End-to-end paths | §5 `e2e-paths.md` | Which path, which step affected |

#### [Subagent] Step 3: Change Type Analysis

Analyze change patterns described in the plan:
- Does it involve state machine changes?
- Does it delete/rename public methods?
- Does it modify method signatures?
- Does it involve SQL write-operation changes?

#### [Subagent] Step 4: Re-assess Risk Level

```
Phase 2 Level = max(Impact Scope, Change Type, Business Sensitivity)
```

Reference the three-dimensional factor table in the file specified by ecw.yml `paths.risk_factors`.

#### Step 5: Compare with Phase 1, Handle Upgrades/Downgrades

| Scenario | Action |
|----------|--------|
| Phase 2 > Phase 1 (upgrade) | **Mandatory**: Inform user, backfill missing workflow steps |
| Phase 2 < Phase 1 (downgrade) | **Suggested**: Inform user that downstream workflow can be simplified, user decides |
| Phase 2 = Phase 1 | Confirm assessment, continue execution |

### Phase 2 Output Format

```markdown
## Change Risk Precise Assessment (Phase 2)

### Risk Level: P{X} (Phase 1 pre-assessment: P{Y}, {upgraded/downgraded/unchanged})

### Classification Factors
| Factor | Level | Rationale |
|--------|-------|-----------|
| Impact Scope | P{X} | {details: which shared resources/cross-domain calls/MQ Topics} |
| Change Type | P{X} | {details: state machine/signature/SQL etc.} |
| Business Sensitivity | P{X} | {details: inventory/tasks/orders etc.} |

### Impact Scope Details
- **Shared resources:** {list}
- **Cross-domain calls:** {list}
- **MQ Topics:** {list}
- **End-to-end paths:** {path ID + affected steps}
- **External systems:** {list}

### Level Change
{upgrade → list workflow steps to backfill}
{downgrade → list workflow steps that can be skipped (suggested, user decides)}
{unchanged → "Phase 1 pre-assessment was accurate, proceed as planned"}

### Downstream Workflow (Updated)
{list remaining workflow steps based on final level}
```

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

#### Step 1: Compare Predicted vs. Actual

Extract actual impact metrics from biz-impact-analysis report, compare with Phase 1/Phase 2 predictions:

| Dimension | Phase 1 Predicted | Phase 2 Precise | biz-impact-analysis Actual | Deviation |
|-----------|------------------|-----------------|---------------------------|-----------|
| Affected domain count | {predicted} | {refined} | {actual} | {+/-N} |
| Cross-domain calls | {predicted} | {refined} | {actual} | {+/-N} |
| MQ Topics | {predicted} | {refined} | {actual} | {+/-N} |
| External systems | {predicted} | {refined} | {actual} | {+/-N} |
| End-to-end paths | {predicted} | {refined} | {actual} | {+/-N} |
| Changed file count | — | — | {actual} | — |

#### Step 2: Determine Prediction Accuracy

Based on biz-impact-analysis actual impact scope, use the three-dimensional factor table (Impact Scope / Change Type / Business Sensitivity) in `change-risk-classification.md` to reverse-derive "actual appropriate level". Compare against Phase 2 level (if Phase 2 was executed) or Phase 1 level:

| Scenario | Determination |
|----------|--------------|
| Predicted level = actual appropriate level | **Accurate** |
| Over-predicted (e.g., P0 but actually only 1 domain, 0 MQ) | **Over-alert** |
| Under-predicted (e.g., P2 but actually 3+ domains, multiple MQ) | **Missed** |

#### Step 3: Output Calibration Suggestions

**When deviation is significant** (level difference ≥ 2, or key dimension deviation ≥ 50%), output calibration suggestions:

```markdown
## Risk Prediction Calibration Suggestions (Phase 3)

### Predicted vs. Actual
| Dimension | Phase 1 Predicted | Phase 2 Precise | biz-impact-analysis Actual |
|-----------|------------------|-----------------|---------------------------|
| Risk Level | P{x} | P{y} | Should be P{z} |
| Affected domain count | {n} | {n} | {n} |
| Cross-domain calls | {n} | {n} | {n} |
| MQ Topics | {n} | {n} | {n} |
| External systems | {n} | {n} | {n} |

### Deviation Analysis
{Root cause analysis: Why was the prediction inaccurate?}
- Keyword match missed? → change-risk-classification.md needs additional keywords
- Shared resource table incomplete? → shared-resources.md needs consumer domain list additions
- Domain registry scope inaccurate? → domain-registry.md needs code directory adjustment
- Cross-domain call matrix missing? → cross-domain-calls.md needs call relationship additions

### Suggested Adjustments
- `change-risk-classification.md`: {specific suggestion, e.g., "Upgrade keyword XXX from P2 to P1"}
- `shared-resources.md`: {e.g., "Add consumer domain list for shared resource XXX"}
- `domain-registry.md`: {e.g., "Expand code directory scope for domain XXX"}
- `cross-domain-calls.md`: {e.g., "Add call relationship A→B"}

> Above are suggestions only. Require user confirmation before manual configuration changes.
```

**When prediction is accurate**, output brief confirmation:

```
Phase 3 calibration complete: Predicted level P{x} matches actual impact. No adjustments needed.
```

**When deviation is minor** (level difference 1 and key dimension deviation < 50%), record but do not output suggestions:

```
Phase 3 calibration complete: Predicted level P{x}, actual closer to P{y}. Minor deviation within acceptable range.
```

#### Step 4: Append Calibration Record

After each Phase 3 execution, append calibration results to `.claude/ecw/calibration-log.md` (path configurable via ecw.yml `paths.calibration_log`).

Append format:

```markdown
### {YYYY-MM-DD} — {change summary}

| Dimension | Phase 1 | Phase 2 | Actual |
|-----------|---------|---------|--------|
| Risk Level | P{x} | P{y} | P{z} |
| Affected domain count | {n} | {n} | {n} |
| Cross-domain calls | {n} | {n} | {n} |
| MQ Topics | {n} | {n} | {n} |
| External systems | {n} | {n} | {n} |

**Determination**: {Accurate / Over-alert / Missed / Minor deviation}
**Deviation cause**: {one-line explanation; write "—" if no deviation}

---
```

> If file does not exist, first copy initial template from `templates/calibration-log.md` (or create an empty file with header).

### Notes

- Phase 3 **does not auto-modify any configuration files**, only outputs suggestions
- Calibration records are auto-appended to `calibration-log.md`; accumulated records can be used to identify systematic deviation patterns
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

## Common Mistakes

| Mistake | Consequence | Correction |
|---------|------------|------------|
| Phase 1 proceeded without waiting for user confirmation | User cannot adjust level | Must wait for user confirmation before invoking downstream skills |
| P0 change skipped ecw:spec-challenge | Plan blind spots unexposed | Roll back, run ecw:spec-challenge |
| Phase 2 upgrade did not backfill workflow | High-risk change went through low-risk workflow | Upgrade is mandatory; must backfill |
| Downgrade applied without user confirmation | Workflow simplified without human approval | Downgrade is suggested; requires human confirmation |
| Only checked keywords, skipped §3 | Missed shared resource impact | Phase 1 must check §3 |
| Cross-domain requirement routed to ecw:requirements-elicitation | Missing per-domain independent analysis and cross-validation | 2+ domain matches must route to ecw:domain-collab |
| Forgot ecw:biz-impact-analysis after impl-verify | Business impact of code changes not assessed | P0/P1 changes must invoke `/biz-impact-analysis` after impl-verify |
| P0-P2 change skipped TDD:RED | No failing test to prove test effectiveness | Test-first is a structural requirement, not optional |
| Bug fix without reproduction test | Fix correctness cannot be automatically verified | Write reproduction test first (RED), then fix to make it pass (GREEN) |
| Skipped Phase 3 after biz-impact-analysis | Prediction deviation not discovered; rules cannot improve | Must execute Phase 3 calibration after biz-impact-analysis report |
| Phase 3 suggestion applied without user confirmation | Single change may be coincidental; auto-modification may introduce bias | Phase 3 only outputs suggestions; user decides whether to adopt |
