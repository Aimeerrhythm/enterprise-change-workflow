---
name: knowledge-track
description: Knowledge doc utilization tracking. After a dev task, analyzes how AI actually used knowledge docs during the conversation. Classifies as doc-hit/miss/redundant/misleading/code-derived. Recommended after ecw:impl-verify or ecw:biz-impact-analysis.
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

### Step 1: Review Document Access in Conversation

Scan all Read tool calls in this conversation, identify:
- Which knowledge docs were read
- After each read, whether document content influenced subsequent code generation or decisions

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
