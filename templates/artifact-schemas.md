# ECW Artifact Schemas

Centralized schema definitions for all ECW workflow artifacts stored under `.claude/ecw/session-data/{workflow-id}/`.

## Localization

All artifact headings, table headers, and field labels MUST be output in the language configured by `ecw.yml` → `project.output_language`. The templates below use English as structural reference only — translate all human-readable text (headings, labels, descriptions) to the configured language when writing artifacts.

- `zh-CN`: 所有标题、表头、字段标签用中文输出
- `en`: Use English as-is from templates

**Exception**: `session-state.md` marker comments (`<!-- ECW:STATUS:START -->` etc.) and YAML field keys (`risk_level`, `domains`, `mode`, etc.) stay in English — they are machine-parsed by hooks.

## Overview

| Artifact | Writer | Readers | Purpose |
|----------|--------|---------|---------|
| `session-state.md` | risk-classifier Phase 1; all skills update MODE/LEDGER | All downstream skills | Workflow state, risk level, routing, subagent ledger |
| `domain-collab-report.md` | domain-collab Round 3 | risk-classifier Phase 2, writing-plans, impl-verify | Multi-domain analysis with components, conflicts, dependencies |
| `knowledge-summary.md` | domain-collab | risk-classifier Phase 2, writing-plans, impl-verify | Extracted knowledge file entries relevant to current change |
| `phase2-assessment.md` | risk-classifier Phase 2 | writing-plans, downstream skills | Precise risk classification with 3D factors and impact details |
| `requirements-summary.md` | requirements-elicitation | risk-classifier Phase 2, writing-plans, impl-verify | Full requirement spec with scope, data changes, edge cases |
| `impl-verify-findings.md` | impl-verify | impl-verify (convergence tracking) | Per-round findings with severity, code locations, deviations |
| `spec-challenge-report.md` | spec-challenge agent | User confirmation flow, plan author | Fatal flaws, improvement suggestions, user decisions |
| `cross-service-plan.md` | workspace coordinator Phase 1 | workspace coordinator Phase 3 | Business decomposition: per-service roles, interaction patterns, open questions |
| `confirmed-contract.md` | workspace coordinator Phase 3 | child sessions Phase 4 | Finalized cross-service contracts: field names/types, topic names, interface signatures, execution order |
| `status.json` | child sessions Phase 4 | workspace coordinator Phase 4 polling | Per-service implementation completion marker with commits and files changed |

---

## session-state.md

### Required Sections

```markdown
# ECW Session State

<!-- ECW:STATUS:START -->
risk_level: P{X}
domains: [{domain list}]
mode: {single-domain or cross-domain}
routing: [{ordered skill list}]
current_phase: phase1-complete
created: "{YYYY-MM-DD}"
workflow_id: "{YYYYMMDD-xxxx}"
baseline_commit: TBD
implementation_strategy: TBD
post_implementation_tasks: TBD
auto_continue: true
next: {next skill to invoke}
<!-- ECW:STATUS:END -->

<!-- ECW:MODE:START -->
working_mode: analysis
<!-- ECW:MODE:END -->

<!-- ECW:LEDGER:START -->
<!-- ECW:LEDGER:END -->
```

### Conventions

- Use `<!-- ECW:{NAME}:START/END -->` markers to delimit updatable sections
- Update only between matching markers — never overwrite the entire file
- All marker sections use **YAML** format; `routing` and `domains` are YAML lists; `auto_continue` is YAML boolean
- Working modes: `analysis` | `planning` | `implementation` | `verification`
- Ledger is a YAML list of dicts; scale: small (<20K tokens), medium (20-80K), large (>80K)
- See `skills/risk-classifier/session-state-format.md` for full template and LEDGER entry format

---

## domain-collab-report.md

### Required Sections

```markdown
# Multi-Domain Collaboration Analysis Report

## Requirement Summary
{user_requirement}

## Domain Overview (Merged Round 1 + Round 2)
| Domain | Round 1 Level | Post-Negotiation Level | Changed Components | Summary |

## Per-Domain Detailed Analysis
### {domain_name} Domain
- **Impact Level**: {level}
- **Summary**: {summary}
- **Components to Change**: table(Type, Name, Change Content, Verification)
- **State Changes**: {entity}: {from} → {to} ({trigger})
- **Cross-Domain Risks**: → {target}: {reason} ({type}: {resource})

## Inter-Domain Negotiation Findings
### Impact Level Changes
### Companion Changes Discovered in Negotiation
### Inter-Domain Conflicts

## Coordinator Cross-Validation Findings
### Omission Detection

## Cross-Domain Dependencies & Implementation Order

## Code Verification Results

## Risk Point Summary
```

---

## knowledge-summary.md

### Required Sections

```markdown
# Knowledge Summary (extracted during domain-collab analysis)

## Involved Domains: {domain list}

## Related Shared Resources
{Entries from shared-resources.md relevant to this change}

## Related Cross-Domain Calls
{Entries from cross-domain-calls.md involving changed domains}

## Related MQ Topics
{Entries from mq-topology.md involving changed domains}

## Related Business Rules Summary
{Per domain: state machines and validation rules from business-rules.md}
```

---

## phase2-assessment.md

### Required Sections

```markdown
## Change Risk Precise Assessment (Phase 2)

### Risk Level: P{X} (Phase 1 pre-assessment: P{Y}, {upgraded/downgraded/unchanged})

### Classification Factors
| Factor | Level | Rationale |
|--------|-------|-----------|
| Impact Scope | P{X} | {shared resources/cross-domain calls/MQ Topics} |
| Change Type | P{X} | {state machine/signature/SQL etc.} |
| Business Sensitivity | P{X} | {inventory/tasks/orders etc.} |

### Impact Scope Details
- **Shared resources:** {list}
- **Cross-domain calls:** {list}
- **MQ Topics:** {list}
- **End-to-end paths:** {path ID + affected steps}
- **External systems:** {list}

### Level Change
{upgrade/downgrade/unchanged + workflow adjustment}

### Downstream Workflow (Updated)
{remaining steps based on final level}
```

---

## requirements-summary.md

### Required Sections

```markdown
## Requirement Summary: [Title]

### Problem Statement
[1-2 sentences]

### Scope
- In scope: [list]
- Out of scope: [list]
- Assumptions: [list]

### Detailed Requirements
[By functional area, each with acceptance criteria]

### Data Changes
[New/modified entities, fields, states]

### Workflow
[Step-by-step with decision points]

### Edge Cases & Error Handling
[Each scenario with expected behavior]

### Analysis Findings
- Critical/important findings integrated above
- User decisions on open questions: [list]

### Open Questions
[Unresolved questions]
```

---

## impl-verify-findings.md

### Per-Round Format

```markdown
### Impl-Verify Round {N} — {dimension name}

**Check scope**: {cross-referenced artifacts + code file list}

**Findings**:

| # | Type | Reference Source | Code Location | Deviation Description | Severity |
|---|------|-----------------|--------------|----------------------|----------|

**This round: {X} must-fix + {Y} suggestions.**
```

### Final Pass Summary

```markdown
## Impl-Verify Verification Passed

After {N} rounds (fixed {X} must-fix issues):

**Per-dimension results**:
- Round 1 (Requirements↔Code): {count} must-fix, resolved
- Round 2 (Domain Knowledge↔Code): {count} must-fix, resolved
- Round 3 (Plan↔Code): {count} must-fix, resolved
- Round 4 (Engineering Standards↔Code): {count} must-fix, resolved

**Unaddressed suggestions** ({count}, non-blocking)
```

### Severity Definitions

- **must-fix**: Will cause bug or incident in production. Blocks convergence.
- **suggestion**: Improvement opportunity. Non-blocking.

### Output Constraints

- ≤5 must-fix: full table in session
- \>5 must-fix: summary + top 3 in session, full table in file
- Zero must-fix: ≤3 lines
- All findings always written to file (survives compaction)

---

## spec-challenge-report.md

### Required Sections

```markdown
## Fatal Flaws
### F{n}: {title}
{description, technical impact, edge case implications}

## Improvement Suggestions
### I{n}: {title}
{description, benefit}

## Conclusion
{overall robustness assessment}
```

### Response Summary (appended after user confirmation)

```markdown
## Review Response Summary

| ID | Type | Title | User Decision | Execution Result |
|----|------|-------|--------------|-----------------|
| F1 | Fatal | ... | ✅ Agree to modify | Updated §X.Y |
| I1 | Improvement | ... | ⏭️ Deferred | Recorded |
```

### User Decision Options

- Fatal flaws: Agree to modify / Disagree (with rebuttal) / Needs discussion
- Improvements: Adopt / Defer

---

## cross-service-plan.md

Written by workspace coordinator at Phase 1 end (business-layer only, no code detail).
Updated at Phase 3 end with final contracts.

### Required Sections

```markdown
## Cross-Service Plan: {requirement title}

## Service Roles
| Service | Role | Business Responsibility |
|---------|------|------------------------|
| {svc}   | Provider / Consumer / Both | {1-2 sentence business description} |

## Interaction Patterns
| From | To | Pattern | Open Questions |
|------|----|---------|----------------|
| {svc-a} | {svc-b} | MQ / Dubbo / unclear | {questions for Phase 2} |

## Open Questions for Phase 2
- {question}: needs {service} to investigate
```

### Phase 3 Update (append after contract alignment)

```markdown
## Final Contracts (Phase 3)
{MQ topic names, DTO field alignments, Dubbo interface signatures, execution order}
```

---

## confirmed-contract.md

Written by workspace coordinator per service at Phase 3 end.
Contains ONLY cross-service contract layer — no internal class/method names.

### Required Sections

```markdown
## Confirmed Contract: {service_id}

## Interaction Pattern
- interaction_pattern: mq | dubbo
- execution_layer: {N}  # 1 = first, higher = later

## MQ Contract (if applicable)
- topic: {topic_name}
- role: Producer | Consumer
- dto_fields:
  - {field_name}: {type} (nullable: true|false)

## Dubbo Contract (if applicable)
- role: Provider | Consumer
- interface: {fully.qualified.InterfaceName}
- method: {methodName}({param_type}): {return_type}

## Verification Requirement
impl-verify MUST pass before writing status.json
```

### Exclusions

Do NOT include: class names, method names, internal entry points, task decomposition,
or "A or B" choices. Surface architecture decisions to user via AskUserQuestion.

---

## status.json

Written by child session at Phase 4 end. Read by coordinator Phase 4 polling.

### Required Fields

```json
{
  "service": "{service_id}",
  "status": "completed | failed | blocked",
  "summary": "Brief description of what was implemented",
  "files_changed": [
    "relative/path/to/ChangedFile.java"
  ],
  "commits": [
    "abc1234 feat: brief commit message"
  ],
  "error": null
}
```

### Status Values

- `completed`: all implementation and impl-verify done
- `failed`: implementation attempted but encountered unrecoverable errors
- `blocked`: cannot proceed, needs coordinator or user intervention

