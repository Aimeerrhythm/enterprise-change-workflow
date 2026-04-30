# Impl-Verify Output Templates

### All findings are written to `impl-verify-findings.md` after each round. File format:

```markdown
<!-- ECW:VERIFY-STATUS: HAS-MUST-FIX -->

### Impl-Verify Round {N} — {dimension name}
...
```

Update the first-line marker to `<!-- ECW:VERIFY-STATUS: PASS -->` when convergence is confirmed (zero must-fix in the latest round). The `verify-completion` hook uses this marker to mechanically block task completion.

## Per-Round Output Format

```markdown
### Impl-Verify Round {N} — {dimension name}

**Check scope**: {cross-referenced artifacts + code file list}

**Findings**:

| # | Type | Reference Source | Code Location | Deviation Description | Severity |
|---|------|-----------------|--------------|----------------------|----------|
| 1 | State machine deviation | requirements: "A→B→C" | FooService.java:142 | Code allows A→C jump, missing state B | must-fix |
| 2 | Method too long | Engineering standards | BarService.java:60 | issue() method 50+ lines, mixes validation and business logic | suggestion |

**This round: {X} must-fix + {Y} suggestions.**
```

## Zero Must-Fix Output

```markdown
### Impl-Verify Round {N} — {dimension name}

**Check scope**: {cross-referenced artifacts + code file list}

**Findings**: No must-fix items. {Y} suggestions (non-blocking).

**This round zero must-fix, verification passed.**
```

## Final Pass Summary

```markdown
## Impl-Verify Verification Passed

After {N} rounds of verification (fixed {X} must-fix issues), implementation correctness check passed.

**Per-dimension results**:
- Round 1 (Requirements↔Code): {count} must-fix, resolved
- Round 2 (Domain Knowledge↔Code): {count} must-fix, resolved
- Round 3 (Plan↔Code): {count} must-fix, resolved
- Round 4 (Engineering Standards↔Code): {count} must-fix, resolved
- Round {M} (Fix re-verification): Zero must-fix ✓

**Unaddressed suggestions** ({count}, non-blocking):
| # | Location | Suggestion Content |
|---|----------|--------------------|
| 1 | ... | ... |

Verification passed. Task can be marked as complete.

**Next step** (read risk level from `.claude/ecw/session-data/{workflow-id}/session-state.md`; if file does not exist or lacks risk level field, use AskUserQuestion to ask user for current risk level):
- P0/P1 change → **Immediately** use Skill tool to invoke `ecw:biz-impact-analysis` to analyze business impact of code changes.
- P2 change → **Suggested** to run `ecw:biz-impact-analysis` (not mandatory; user may decide to skip).
- P3 / pure formatting change → No biz-impact-analysis needed.

If TaskList has a pending "ecw:biz-impact-analysis" Task, marking impl-verify Task as completed will automatically unblock that Task.
```

## Output Constraints

### In-Session Output Limits

Per-round findings table:
- **≤ 5 must-fix**: Output full findings table directly
- **> 5 must-fix**: Output summary in session (count + top 3 most severe items)
- **All findings**: After each verification pass completes, write all findings to `.claude/ecw/session-data/{workflow-id}/impl-verify-findings.md` regardless of count. This ensures findings survive context compaction during multi-round convergence.
- **Zero must-fix**: Use simplified output format, no more than 3 lines

Final pass summary:
- Summary no more than **15 lines** (one line per Round result + unaddressed suggestion list max 5 items)
- If there are skipped suggestions, list only the count, not details

### Fix Re-Verification Rounds

Fix re-verification rounds (Round N+) output only:
- Re-verified must-fix IDs + pass/fail result (table format, one item per line)
- New findings (if any)
- **Do not repeat already-passed Round results**
