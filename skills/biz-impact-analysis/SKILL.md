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

**Announce at start:** "Using ecw:biz-impact-analysis to assess business impact of code changes."

**Output language**: Read `ecw.yml` → `project.output_language`. Pass to dispatched agent prompt. Report headings and labels follow this language.

## Flow

1. **Determine Diff Range** — No args: use `git diff master...HEAD`; with args: use `git diff {args}` to get changed file list
2. **Coordinator Preprocessing** — Execute before Agent dispatch:
   1. Run `git diff --stat {diff_range}` to get change statistics
   2. Run `git diff --name-only {diff_range}` to get file list
   3. Read `path-mappings.md`, map file list to domains
   4. Fill above results into Agent prompt, replacing full diff

> **Knowledge file robustness**: If `path-mappings.md` is missing, pass the raw file list to the Agent without domain mapping. The Agent will use path-based heuristic grouping and note `[Warning: path mappings not found, domain identification is heuristic]` in the report.
3. **Dispatch biz-impact-analysis agent** — Read `./prompts/agent-prompt-template.md` for the dispatch prompt structure and argument parsing rules. Model: `opus` (default from `models.defaults.analysis`; configurable via ecw.yml). Pass in preprocessed results, await impact analysis report
4. **Return value validation**: Verify the agent's report contains required sections ("Analysis Coverage", "Change Summary", "Direct Impact"). If the report is missing critical sections:
   - Log to Ledger: `[FAILED: biz-impact-analysis, reason: incomplete report]`
   - Retry once with the same model
   - If retry also fails: output the partial report as-is with `[degraded: incomplete analysis]` header, and warn user that manual impact review may be needed
5. **Auto-backfill knowledge base** — If the agent's report contains "Unregistered Cross-Domain Calls", execute the knowledge backfill procedure (see [Knowledge Auto-Backfill](#knowledge-auto-backfill) below)
6. **Present analysis report** — Write the full report to `session-data/{workflow-id}/biz-impact-report.md` (read the workflow-id from the STATUS block in session-state.json). Then output the agent's formatted report directly; append backfill summary if any calls were added

## Knowledge Auto-Backfill

When the agent's report flags "Unregistered Cross-Domain Calls", automatically backfill them into the knowledge base instead of relying on manual follow-up.

### Procedure

1. **Extract unregistered calls** — Parse the agent's report for all entries under "Unregistered Cross-Domain Calls" (or equivalent section). Each entry typically contains: caller domain, callee domain, call method (RPC/HTTP/MQ), caller class/method, callee class/method.

2. **Read existing matrix** — Read `.claude/knowledge/shared/cross-domain-calls.md` (path from ecw.yml `paths.knowledge_shared`).
   - If the file does not exist, skip backfill and output `[Warning: cross-domain-calls.md not found, skipping auto-backfill. Please create the file and backfill manually.]`

3. **Deduplicate** — For each unregistered call, check if an equivalent entry already exists in the matrix (match on caller domain + callee domain + call method + caller class). Skip entries that already exist.

4. **Append new entries** — Append only genuinely new calls to the end of the matrix table, preserving the existing table format. Use Edit tool (not Write) to append rows.
   - **Conservative strategy**: Only add entries. Never modify or delete existing entries.
   - Each appended row should include a trailing comment: `<!-- auto-backfilled by biz-impact-analysis {date} -->`

5. **Report backfill result** — Append the following summary to the end of the analysis report output. Section title and text follow `project.output_language`:

```
---
### Knowledge Auto-Backfill

Auto-backfilled {N} cross-domain call(s) to `cross-domain-calls.md`:
{list of added entries, one per line}

> Backfill strategy: append-only for confirmed new calls. Existing entries are never modified or deleted. Edit manually if adjustments are needed.
```

If N=0 (all flagged calls already existed), output instead:
```
---
### Knowledge Auto-Backfill

All unregistered calls flagged in the report already exist in the knowledge base. No backfill needed.
```

### Edge Cases

| Scenario | Handling |
|----------|---------|
| `cross-domain-calls.md` not found | Skip backfill, warn in report, suggest manual creation |
| `cross-domain-calls.md` has no table header | Skip backfill, warn: `[Warning: cross-domain-calls.md format unrecognized, skipping auto-backfill]` |
| Agent report has no "Unregistered Cross-Domain Calls" section | No backfill needed, skip silently |
| Agent report parsing ambiguous | Skip backfill for ambiguous entries, only backfill clearly parseable ones, note skipped count in summary |

## Integration with impl-verify

When `ecw:impl-verify` completes, dispatch biz-impact-analysis based on the same diff range. Trigger conditions by risk level: see `workflow-routes.yml`.

## Integration with Phase 3

After biz-impact-analysis report is output, mark the biz-impact-analysis Task as complete.

If TaskList has a pending "Phase 3 Calibration" Task, marking biz-impact-analysis Task as completed will automatically unblock that Task.

**Timeout**: 300s (agent reads multiple knowledge files and scans code). If Agent has not returned, terminate and offer retry (see Error Handling).

## Error Handling

| Scenario | Handling |
|----------|---------|
| Biz-impact-analysis Agent returns empty or fails | Record `FAILED` in Subagent Ledger → retry once → still fails: notify user `[DEGRADED: business impact analysis unavailable]` and suggest manual assessment |
| `path-mappings.md` missing | Agent cannot map files to domains → output `[Warning: path mappings not found, domain identification degraded]` and proceed with file-path-based heuristic grouping |
| Knowledge files missing (cross-domain-calls.md, mq-topology.md, etc.) | Agent logs `[Warning: {file} not found]` per missing file → analysis continues with available data, "Analysis Coverage" section in report reflects gaps |
| `git diff` returns empty | No changes to analyze → notify user and exit without dispatching agent |

## Supplementary Files

- `prompts/agent-prompt-template.md` — Agent dispatch prompt structure and argument parsing rules
- `prompts/common-rationalizations.md` — Anti-patterns to avoid

## Notes

- The "Analysis Coverage" section in the report indicates which dimensions may have gaps
- "Unregistered cross-domain calls" flagged in the report are auto-backfilled to `cross-domain-calls.md` (conservative: append-only, no modification/deletion)
- "Suspected stale entries" flagged in the report still need manual confirmation before cleanup
