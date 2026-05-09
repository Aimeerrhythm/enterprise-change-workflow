---
name: knowledge-audit
description: Knowledge base health audit. Scans knowledge docs, analyzes content composition, detects stale references, tiny/oversized files, three-criteria compliance, outputs health report and optimization suggestions.
---

# Knowledge Base Health Audit

You are a knowledge base quality auditor. When user invokes this Skill, perform a comprehensive health check on the project's knowledge base.

## Prerequisites

Check if `.claude/ecw/ecw.yml` exists:
- Exists → Read `paths.knowledge_root`
- Not exists → Use default `.claude/knowledge/`

## Audit Steps

### Step 1: Basic Statistics

Scan all `.md` files under knowledge root:
- Count total files, total lines
- Count files and lines per domain (first-level subdirectories)
- Identify tiny files (<25 lines) and oversized files (>300 lines)

```bash
find <knowledge_root> -name "*.md" -type f | wc -l
find <knowledge_root> -name "*.md" -type f -exec wc -l {} + | sort -n
```

### Step 2: Content Composition Analysis

For each non-`00-index.md` file, sample content (first 50 + middle 50 + last 50 lines), classify into:

| Content Type | Recognition Pattern | Value Assessment |
|-------------|-------------------|-----------------|
| **Pseudocode/Call chains** | Contains `→`, `FacadeImpl`, `BizServiceImpl`, `Manager` line-by-line translation | Low value (AI can read source directly) |
| **Business constraints/rules** | Contains "must", "not allowed", "priority", "condition", "invariant" | High value (cross-file aggregation) |
| **State transitions/tables** | Contains state machines, error code tables, dependency tables | Medium-high value (structured info) |
| **Config listings** | Contains Nacos, enum value lists, config item tables | Low value (stale-prone, greppable) |
| **Navigation/overview** | Contains directory structure, Facade map, entry locator table | High value (AI locating efficiency boost) |

Output estimated percentage for each type (based on sampling).

### Step 3: Three-Criteria Compliance Check

For high-percentage "Pseudocode/Call chains" and "Config listings", check if they meet any of the three criteria:

**Three-Criteria Standard** (keep if meets any one):
1. **Cross-file scattered** — Info scattered across 3+ files, AI needs extensive reading to piece together
2. **Implicit intent** — Code has what but no why, and not knowing why leads AI to wrong decisions in edge cases
3. **Counter-intuitive design** — Code behavior looks like a bug but is actually intentional business requirement

Content meeting none → Mark as "suggest deletion".

### Step 4: Stale Reference Detection

Based on `project.language`:

**Java projects**:
- Run `bash scripts/java/check-freshness.sh <project_root> <ecw_yml_path>`
- Script outputs markdown table with stale references and to-verify docs

**Other languages**:
- Manual: Extract class/function names from docs, search in code directories
- Check if `last-verified` date exceeds 90 days

### Step 5: Output Report

```markdown
# Knowledge Base Health Report

Generated: YYYY-MM-DD HH:MM

## Basic Statistics
- Total files: X
- Total lines: X
- Distribution by domain:

| Domain | Files | Lines |
|--------|-------|-------|
| ... | ... | ... |

## File Anomalies
- Tiny files (<25 lines): [list]
- Oversized files (>300 lines): [list]

## Content Composition
- Pseudocode/call chains: X% (suggest <10%)
- Business constraints/rules: X% (core value)
- State transitions/tables: X%
- Config listings: X% (suggest <5%)
- Navigation/overview: X%

## Three-Criteria Compliance
- Non-compliant content: X items
- [Specific locations and suggestions]

## Stale References
- Suspected stale: X items
- To verify: X items
- [Specific list]

## Optimization Suggestions
1. [Specific suggestion]
2. [Specific suggestion]
```

### Step 5.5: Review Pending Knowledge Entries

Read `.claude/ecw/knowledge-ops/pending-entries.md`.

If not exists or no entries with `Status: pending` — note "No pending knowledge entries." and skip.

**Add a summary section to the Step 5 report** (or output separately if report already printed):

```markdown
## Pending Entries Status
- Total pending: {count}
- By target file: {breakdown}
- Oldest pending: {date}
```

For each entry with Status = `pending`, present to user using AskUserQuestion:

**Options**: Accept / Reject / Edit then accept

**On Accept**:
- If `target_file` does not exist → Ask: "Target file `{path}` does not exist. Create it? (Y/n)"
  - Yes: Create file with minimal header (title + section)
  - No: Keep entry as pending with note `[NO-TARGET-FILE]`, move to next entry
- Read the `target_file`
- Append proposed content to the specified `target_section` (or end of file if section missing)
- Read back `target_file` to verify the content was written
  - If content not found: Keep Status = `pending`, note `[WRITE-FAILED]`, move to next entry
- Update entry Status from `pending` to `written`
- Log: "Written to `{target_file}` §`{target_section}`"

**On Reject**:
- Update entry Status from `pending` to `rejected`
- Entry stays in file to prevent regeneration of the same knowledge

**On Edit then accept**:
- User provides modified proposed content
- Write modified content to `target_file` at `target_section` (same flow as Accept)
- Update entry Status to `written`, note `(user-edited)`

### Step 6: Persist Stale References for Hook Consumption

Write structured stale reference data to `.claude/ecw/state/stale-refs.md`. This file is consumed by the `verify-completion` hook to produce targeted reminders on subsequent task completions.

```markdown
# Knowledge Stale References

> Auto-generated by ecw:knowledge-audit. Do not edit manually.
> Generated: YYYY-MM-DD HH:MM

## Stale Class References

| Doc | Class | Status |
|-----|-------|--------|
| [doc path] | `ClassName` | Not found in codebase |

## Overdue Verification

| Doc | last-verified | Days Overdue |
|-----|--------------|-------------|
| [doc path] | YYYY-MM-DD | N |
```

If no stale references or overdue docs found, delete the file (absence = clean state).

## Notes

- Use sampling strategy when reading files, no need to analyze line-by-line
- Report should be specific to file paths and sections, provide actionable suggestions
- If no knowledge directory exists, prompt user to run `/ecw-init`
- After audit, suggest running periodically (monthly or quarterly) to maintain health
