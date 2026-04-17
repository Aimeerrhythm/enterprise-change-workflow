---
name: biz-impact-analysis
description: |
  Use when code changes are complete and need business impact assessment.
  TRIGGER when: impl-verify passes (automatic for P0/P1), or manually via
  /biz-impact-analysis. DO NOT use for pre-implementation requirement analysis
  (use ecw:domain-collab instead).
---

# Business Impact Analysis

After code changes are complete, dispatch the `biz-impact-analysis` agent to analyze the impact of changes on business processes.

## Trigger

- **Manual**: `/biz-impact-analysis` — Analyze all changes on current branch vs master
- **Manual (specify range)**: `/biz-impact-analysis HEAD~3` — Analyze last N commits
- **Automatic**: Appended automatically after ecw:impl-verify completes

## Flow

1. **Determine Diff Range** — No args: use `git diff master...HEAD`; with args: use `git diff {args}` to get changed file list
2. **Coordinator Preprocessing** — Execute before Agent dispatch:
   1. Run `git diff --stat {diff_range}` to get change statistics
   2. Run `git diff --name-only {diff_range}` to get file list
   3. Read `ecw-path-mappings.md`, map file list to domains
   4. Fill above results into Agent prompt, replacing full diff
3. **Dispatch biz-impact-analysis agent** (`model: sonnet` — business impact analysis requires understanding domain relationships and dependency graphs) — Pass in preprocessed results, await impact analysis report
4. **Present analysis report** — Output the agent's formatted report directly; if unregistered cross-domain calls are found, remind to update dependency graph

## Agent Dispatch Prompt Template

When dispatching the biz-impact-analysis agent, use the following prompt structure:

```
Please analyze the business impact of the following code changes.

## Diff Range

{diff_range}

## Changed File Summary (Coordinator Preprocessed Results)

{git_diff_stat_output}

## Domain Identification Results

{file_to_domain_mapping}

## Instructions

Execute your 5-step analysis process.
Note: Full diff content has been preprocessed by Coordinator, providing file list and domain identification.
In Step 1, only execute `git diff {diff_range} -- {file_path}` for files that need method signature change inspection.
In Step 3 incremental scan, only read specific change content for files matching scan_patterns.
Do not execute `git diff {diff_range}` for full change content on all files.

Please output the impact analysis report in Chinese.
```

## Argument Parsing Rules

| Input | Diff Command |
|-------|-------------|
| `/biz-impact-analysis` | `git diff master...HEAD` |
| `/biz-impact-analysis HEAD~3` | `git diff HEAD~3...HEAD` |
| `/biz-impact-analysis abc123` | `git diff abc123...HEAD` |
| `/biz-impact-analysis abc123 def456` | `git diff abc123...def456` |

## Integration with impl-verify

When `ecw:impl-verify` completes:

1. impl-verify completes code correctness + quality verification (zero must-fix)
2. Dispatch biz-impact-analysis agent based on the same diff range
3. Output business impact analysis report

**Mandatory for P0/P1 changes**; suggested for P2+. The routing chain output by ecw:risk-classifier Phase 1 already includes `ecw:impl-verify + ecw:biz-impact-analysis`, and Phase 1 adds them to TaskCreate todo list.

## Integration with Phase 3

After biz-impact-analysis report is output:

1. If current change is **P0/P1** (read risk level from `.claude/ecw/session-state.md`), **immediately execute Phase 3 calibration** — use Skill tool to invoke `ecw:risk-classifier` with argument `--phase3`
2. If current change is **P2**, suggest executing Phase 3 (not mandatory; user decides)
3. Phase 3 no longer needs manual trigger — automatically chains after biz-impact-analysis completes

If TaskList has a pending "Phase 3 Calibration" Task, marking biz-impact-analysis Task as completed will automatically unblock that Task.

## Subagent Ledger Update

After Agent returns, append one row to `.claude/ecw/session-state.md` Subagent Ledger table:

```
| biz-impact-analysis | analyst | ecw:biz-impact-analysis | large |
```

Scale reference: small (<20K tokens), medium (20-80K), large (>80K). biz-impact-analysis agent is typically large (needs to read multiple knowledge files + code scanning).

## Notes

- Analysis results depend on dependency graph data quality under ecw.yml `paths.knowledge_common`
- The "Analysis Coverage" section in the report indicates which dimensions may have gaps
- "Unregistered cross-domain calls" flagged in the report need manual confirmation before updating dependency graph
- "Suspected stale entries" flagged in the report need manual confirmation before cleanup
