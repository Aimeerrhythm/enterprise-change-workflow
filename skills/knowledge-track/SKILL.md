---
name: knowledge-track
description: Knowledge doc utilization tracking. Manual-only — invoke with `/ecw:knowledge-track` after a dev task; analyzes how AI actually used knowledge docs during the conversation. Classifies as doc-hit/miss/redundant/misleading/code-derived. Not part of any automatic routing chain.
---

# Knowledge Doc Utilization Tracking

You are a documentation effectiveness tracker. When user invokes this Skill after completing a development task, review how AI utilized knowledge docs during this conversation.

## Prerequisites

Check if `.claude/ecw/ecw.yml` exists:
- Exists → Read `paths.knowledge_root`
- Not exists → Use defaults `.claude/knowledge/` and `.claude/ecw/knowledge-ops/doc-tracker.md`

Check if doc-tracker file exists:
- Not exists → Copy template from ECW plugin `templates/doc-tracker.md` to create it

## Tracking Steps

### Step 1: Load Knowledge Read Log

Read `.claude/ecw/session-data/{workflow-id}/knowledge-reads.jsonl`.

This file is auto-populated by the `knowledge-read-logger` hook on every Read
call to knowledge files. Each line is a JSON object:
```json
{"ts": "2026-05-04T10:16:05", "file": ".claude/knowledge/payment/business-rules.md", "offset": 100, "limit": 50}
```

The `offset` and `limit` fields are optional — they appear only when a partial read
was performed (non-zero offset or explicit limit). Absent means the full file was read.

It covers **all sessions** that shared the same workflow-id (Session 1 + Session 2), so
cross-session reads are not lost even when the workflow was split across multiple sessions.

**If the file does not exist** (legacy session or non-ECW context):
- Fall back to scanning Read tool calls in the **current** conversation context only
- Note the limitation: cross-session reads from prior sessions will not be visible

### Step 2: Classify Each Document Access

| Event Type | Criteria |
|-----------|----------|
| **doc-hit** | Read doc, info directly influenced code output or decision |
| **doc-miss** | Relevant doc exists but wasn't read, user later corrected (or should have) |
| **doc-redundant** | Read doc, but still had to read source code to write code — doc provided no incremental info |
| **doc-misleading** | Read doc, but doc info inconsistent with current code, caused wrong output |
| **code-derived** | Took 3+ rounds of source code reading to derive info not covered in knowledge base |

### Step 3: Identify Uncovered Knowledge

If AI derived a cross-file business constraint through extensive code reading that isn't recorded in knowledge base → Mark as potential knowledge base addition.

Additions must meet at least one of the three criteria:
1. **Cross-file scattered** — Info scattered across 3+ files
2. **Implicit intent** — Code has what but no why
3. **Counter-intuitive design** — Behavior looks like a bug but is intentional

### Step 4: Append Record

Append an entry at the end of the "Records" section in doc-tracker file:

```markdown
### YYYY-MM-DD - [Task summary]
- **doc-hit**: [doc path] §[section] → [how it helped the task]
- **doc-miss**: [doc path] §[section] → [doc existed but wasn't read, what user corrected]
- **doc-redundant**: [doc path] → [read but unused]
- **doc-misleading**: [doc path] §[section] → [specific inconsistency between doc and code]
- **code-derived**: [spent N rounds reading which files] → [knowledge eventually derived]
- **potential addition**: [describe new knowledge worth adding to knowledge base]
```

Omit any event type that didn't occur in this task.

### Step 4.5: Generate Candidate Entry for Code-Derived Knowledge

Skip this step entirely if Step 3 identified no code-derived events.

For each code-derived event from Step 3:

**1. Validate against three criteria** — The derived knowledge must meet at least one:
- **Cross-file scattered**: info derived from 3+ source files
- **Implicit intent**: code has what but not why, and the why was non-obvious
- **Counter-intuitive design**: behavior looks like a bug but is intentional

If none apply, skip this event (not worth a candidate entry).

**2. Check for backlog** — Read `.claude/ecw/knowledge-ops/pending-entries.md` if it exists:
- Count entries with `Status: pending` for the same target_file
- If count ≥ 10 → Skip generation for that target_file, append a note to the doc-tracker
  record (Step 4): `⚠️ Pending entries backlog (10+ items). Run /ecw:knowledge-audit to clear.`

**3. Deduplication check** — For each existing entry under the same target_file:
- Extract key terms from the candidate's summary (class names, function names, business nouns)
- Compare with the first sentence of each existing entry
- If word overlap > 60% → Skip (similar entry already exists)
- If Status = `rejected` for a near-identical entry → Skip (user already declined)

**4. Generate candidate entry** — Append to `.claude/ecw/knowledge-ops/pending-entries.md`
(create the file with header if it does not exist):

```markdown
### [Auto-generated] {one-line summary}

- **Status**: pending
- **Source task**: {YYYY-MM-DD} - {task summary from Step 5}
- **Derived from**: {list of source files AI read to derive this knowledge}
- **Rounds spent**: {N rounds of source code reading}
- **Target file**: {which knowledge file this should be added to}
- **Target section**: {section name in target file, or "new section"}
- **Criterion met**: {cross-file-scattered | implicit-intent | counter-intuitive}

**Proposed content:**

> {The actual knowledge to add — concise, factual, focused on constraints
> and rules, not implementation details. Match the style of existing files.}

**Evidence:**

> {Which files, what pattern was observed, why this is non-obvious from
> reading any single file.}

---
```

If no events qualify after all checks, skip this step and do not create pending-entries.md.

### Step 5: Brief Summary

One sentence on documentation utilization efficiency, e.g.:
> "This task: 3 doc-hits, 1 code-derived. Knowledge base coverage good. Suggest adding XXX cross-domain call rules."

## ECW Workflow Integration

Recommended usage timing:
1. **After ecw:impl-verify completes** — Implementation verified, review knowledge utilization during development
2. **After ecw:biz-impact-analysis completes** — Impact analysis done, retrospective before workflow conclusion

After accumulating 15-20 records, run `/ecw:knowledge-audit` with tracking data for comprehensive analysis.

## Notes

- Record honestly — don't embellish. redundant and misleading must be recorded truthfully
- If no knowledge docs were read during conversation, record "No knowledge base usage in this task" and analyze why
- Don't speculate — only record events that actually occurred in the conversation
- doc-misleading is the most important signal — immediately remind user to update the corresponding doc
