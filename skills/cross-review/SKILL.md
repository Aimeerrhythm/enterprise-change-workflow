---
name: cross-review
description: >
  Use when document-heavy changes need cross-file consistency verification
  (tables, lists, terminology, counts may be inconsistent across files).
  Manual-only tool, not in the required workflow. Invocable via /ecw:cross-review.
---

# Cross-Review — Structured Cross-File Verification

Execute multi-round cross-consistency verification on changed files. Exit only when a round produces zero findings. Focuses on inter-file structural consistency.

## Why This Is Needed

The same concept described in different sections of the same file or across multiple files often becomes inconsistent (table row counts differ, list items missing, terminology mixed). This is especially common in document-heavy changes (multiple markdown files cross-referencing each other). Structured multi-dimensional verification + convergence loop systematically eliminates these issues.

## Trigger

- **Manual**: `/ecw:cross-review`
- Applicable scenarios: Document-heavy changes (when multiple markdown/config files cross-reference each other)
- Not in the required development workflow — code correctness and quality are handled by `ecw:impl-verify`

## Relationship with Other Verification Components

| Component | What It Reviews | Distinction |
|-----------|----------------|------------|
| **ecw:cross-review (this skill)** | Intra-file/cross-file structural consistency | Multi-round convergence, focuses on document consistency, manual optional |
| ecw:impl-verify | Code correctness + quality | Multi-round convergence, focuses on code vs requirements/rules/Plan/standards, mandatory step |
| ecw:spec-challenge | Plan blind spots, boundary conditions | Plan phase, not implementation phase |
| verify-completion hook | Reference existence, compilation, knowledge sync | Mechanical hard intercept, not semantic check |

## Execution Protocol

### Round 1 — Cross-File Consistency Matrix

**Goal**: Is the same concept described consistently across multiple files?

**Operations**:

1. List all files changed in this round (`git diff --name-only` or from task context)
2. Extract **structured content** from each file:
   - Table rows (markdown table rows)
   - List items (bulleted/numbered lists)
   - Enumerated values (e.g., "4 checks", "6 knowledge files")
   - Config items (YAML keys, JSON fields)
   - Dimension/field lists (e.g., comparison table rows)
3. For the same concept appearing in 2+ files, cross-compare item by item:
   - Table A row count = Table B row count?
   - List A items = List B items? Same content?
   - Are terms/names consistent across all files? (e.g., "Phase 3" vs "Risk Phase 3")
   - Do quantity references ("4 checks") match actual content?
4. For each inconsistency, record: `[FileA:line] vs [FileB:line] — describe the difference`

### Round 2+ (Conditional Trigger) — Fix Side-Effect Check

**Triggered only when Round 1 found issues that have been fixed.**

**Operations**:

1. For files involved in fixes, re-run Round 1 cross-comparison
2. Confirm fixes did not introduce new inconsistencies
3. If this round finds more issues, fix and continue to next round

### Convergence Condition

**Most recent round has zero findings → exit, output verification passed report.**

- **Loop cap**: Maximum 5 rounds. If findings remain after 5 rounds, output all unresolved items and suggest user intervention.
- **Recurring inconsistency detection**: If the same inconsistency (same File A + File B + same concept) appears in 2 consecutive rounds, mark it as `[Known issue: persists after fix attempt]` and exclude from convergence blocking. This prevents infinite loops from inconsistencies that resist automated fixing.

## Output Format

Per-round output:

```markdown
### Cross-Review Round {N} — {dimension name}

**Check scope**: {file list}

**Findings**:

| # | File A | File B | Inconsistency Description | Severity |
|---|--------|--------|--------------------------|----------|
| 1 | README.md:148 | ecw-validate-config.md:132 | Knowledge file list differs by 1 item (missing cross-domain-rules.md) | must-fix |
| 2 | SKILL.md:395 | SKILL.md:320 | Step 4 table has 4 rows, Step 1 table has 5 rows (missing "external systems") | must-fix |

**This round: {N} issues found. Will execute Round {M} after fixes.**
```

Zero findings output:

```markdown
### Cross-Review Round {N} — {dimension name}

**Check scope**: {file list}

**Findings**: None

**This round zero findings, verification passed.**
```

Final pass summary:

```markdown
## Cross-Review Verification Passed

After {N} rounds of verification (fixed {M} issues), cross-file consistency check passed for all changed files.
```

## Error Handling

| Scenario | Handling |
|----------|---------|
| `git diff --name-only` returns empty | No changed files to review → notify user and exit |
| File listed in diff no longer exists (deleted after diff) | Skip that file in cross-comparison, note `[Skipped: {file} deleted]` |

## Constraints

- **Loop cap**: Maximum 5 rounds. If findings remain after 5 rounds, output all unresolved items and suggest user intervention.
- **Skippable scenarios**: Pure formatting changes, comment/log-only changes with clearly no business logic impact.
- **Out of scope**:
  - Does not verify code correctness or quality (ecw:impl-verify's responsibility)
  - Does not analyze business impact (ecw:biz-impact-analysis's responsibility)
  - Does not check compilation/references (verify-completion hook's responsibility)
  - Does not review plan design (ecw:spec-challenge's responsibility)

## Common Cross-Inconsistency Patterns

For focused attention in Round 1:

| Pattern | Example |
|---------|---------|
| **List length mismatch** | README says "6 knowledge files", validate-config only checks 5 |
| **Table dimension omission** | Comparison table Step 1 has 5 dimension rows, Step 4 template only has 4 |
| **Inconsistent terminology** | One place says "Phase 3", another says "Risk Phase 3" |
| **Component reference omission** | Added new command, but ecw-init "Next Steps" doesn't mention it |
| **Incomplete routing chain** | Workflow diagram has a step, but Skill Interaction table does not |
| **Config-implementation desync** | Template added a field, but validation command doesn't check it |
