# Full Report Template

Used when writing the collaboration analysis report to `.claude/ecw/session-data/{workflow-id}/domain-collab-report.md`.

```markdown
# Multi-Domain Collaboration Analysis Report

## Requirement Summary
{user_requirement}

## Domain Overview (Merged Round 1 + Round 2)
| Domain | Round 1 Level | Post-Negotiation Level | Changed Components | Summary |
|--------|--------------|----------------------|-------------------|---------|
| {domain_name} | {round1_level} | {final_level} | {count} | {summary} |

## Per-Domain Detailed Analysis

### {domain_name} Domain
**Impact Level**: {impact_level}
**Summary**: {summary}

**Components to Change:**
| Type | Name | Change Content | Verification |
|------|------|---------------|-------------|
| {type} | {name} | {change} | verified/stale |

**State Changes:**
- {entity}: {from} → {to} ({trigger})

**Cross-Domain Risks:**
- → {target}: {reason} ({type}: {resource})

### (next domain...)

## Inter-Domain Negotiation Findings

### Impact Level Changes
(If any domain's impact level upgraded after Round 2 negotiation, list the change reason)
| Domain | Round 1 Level | Post-Negotiation Level | Reason |
|--------|--------------|----------------------|--------|
| {domain} | {round1_level} | {round2_level} | {reason} |
(If all domain levels unchanged, show "No level changes")

### Companion Changes Discovered in Negotiation
(Changes each domain discovered in Round 2 that are needed due to other domains' changes)
| Domain | New Component | Change Content | Triggered By |
|--------|--------------|---------------|-------------|
| {domain} | {component} | {change} | {source_domain}'s {what} change |
(If no companion changes, show "None")

### Inter-Domain Conflicts
(Conflicts found in Round 2 negotiation + Coordinator cross-validation)
| Domain A | Domain B | Conflict Description | Suggestion |
|----------|----------|---------------------|------------|
| {domain_a} | {domain_b} | {description} | {suggestion} |
(If no conflicts, show "None")

## Coordinator Cross-Validation Findings
### Omission Detection
- {domain}: Domain A flagged cross_domain_risk pointing to {domain}, but {domain} reported none in both Round 1 and negotiation — suggest confirming

## Cross-Domain Dependencies & Implementation Order
(Based on cross_domain_risks dependency relationships, suggest implementation order)
1. First modify {depended-upon domain} (called/consumed by other domains)
2. Then modify {dependent domain}
3. Finally modify {downstream domain}

## Code Verification Results
- verified: {name} — confirmed to exist
- stale: {name} — knowledge docs record it but not found in code, suggest confirming

## Risk Point Summary
- {notes from each domain}
```
