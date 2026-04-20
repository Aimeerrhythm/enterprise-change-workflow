---
name: spec-challenge
description: |
  Use when a design spec or solution document needs independent adversarial review.
  TRIGGER when: ecw:writing-plans completes for P0 changes or P1 cross-domain changes,
  or manually via /spec-challenge on any spec/plan file.
---

# Spec Challenge — Adversarial Plan Review

After a plan/design document is produced, dispatch the `spec-challenge` agent for independent adversarial review. Present the review report to the user, who confirms handling for each item.

**Announce at start:** "Using ecw:spec-challenge for adversarial plan review."

**Mode switch**: Update session-state.md MODE marker to `planning`.

## Trigger

- **Manual**: `/spec-challenge <file path>` — Launch review on specified document
- **Manual (no args)**: `/spec-challenge` — Auto-find the most recently produced spec file in current session
- **Automatic**: After ecw:writing-plans completes for P0 changes or P1 cross-domain changes

## Flow

```dot
digraph spec_challenge {
  rankdir=TB;

  "Collect review materials" [shape=box];
  "Dispatch spec-challenge agent" [shape=box];
  "Present review report" [shape=box];
  "Per-item user confirmation" [shape=box];
  "Author executes per user decisions" [shape=box];
  "Output response summary" [shape=box];
  "User final confirmation" [shape=box];
  "Review passed" [shape=doublecircle];

  "Collect review materials" -> "Dispatch spec-challenge agent";
  "Dispatch spec-challenge agent" -> "Present review report";
  "Present review report" -> "Per-item user confirmation";
  "Per-item user confirmation" -> "Author executes per user decisions";
  "Author executes per user decisions" -> "Output response summary";
  "Output response summary" -> "User final confirmation";
  "User final confirmation" -> "Review passed";
}
```

### Key Rule: User Drives Decisions

**After spec-challenge report returns, AI must NOT respond on its own.** Follow these steps strictly:

1. **Present** — Display the full spec-challenge review report verbatim
2. **Per-item confirmation** — For each fatal flaw (F1, F2, ...), use AskUserQuestion to let user choose handling:
   - ✅ Agree to modify — AI executes the modification
   - ❌ Disagree — User provides rationale, or AI drafts technical rebuttal for user confirmation
   - ❓ Needs discussion — Enter discussion until user decides
3. **Batch confirm improvements** — Improvement suggestions (I1, I2, ...) can be presented at once, letting user multi-select which to adopt/defer
4. **Execute** — AI executes per user-confirmed decisions
5. **Final confirmation** — Output response summary, review passes after user confirms

For blind spot annotations: Confirm whether they need to be explicitly noted in the document.

## Agent Dispatch Prompt Template

When dispatching the spec-challenge agent, Coordinator first determines `{affected_domains}`:
- **Auto-trigger**: Get domain list from current session's domain-collab report or risk-classifier output
- **Manual trigger**: Extract domain keywords from document content, match against project CLAUDE.md domain routing table; if undeterminable, set to "please infer involved domains from document content"

**Model selection**: `model: opus` (default from `models.defaults.analysis`; configurable via ecw.yml). Reason: adversarial review demands the strongest reasoning to find blind spots, logical gaps, and missed edge cases in plan design.

Use the following prompt structure:

```
Please review a technical plan document.

## Document to Review

File path: {document file path}

Please read the file yourself to get the full content.

## Project Context

Read `.claude/ecw/ecw.yml` to get project.name, read ecw.yml `paths.domain_registry` to get domain list.
Project knowledge documents are in the directory specified by ecw.yml `paths.knowledge_root`.
Cross-domain call relationships are recorded in `cross-domain-rules.md` under ecw.yml `paths.knowledge_common`.

Domains involved in the plan: {affected_domains}
Read relevant knowledge files for the above domains as needed to verify plan accuracy. Do not read all knowledge files at once.

## Source Code Reading Limits (CRITICAL — prevent timeout)

Read at most **10 source files** total. For each file, prefer Grep with limited context (`-A 5`) over full Read. Only Read full files for core interfaces or classes that directly participate in the change. Do NOT read complete implementations of large service classes — read class signatures and method signatures only. Knowledge files do not count toward this limit.

## Review Requirements

Review each dimension (accuracy, information quality, boundaries & blind spots, robustness) one by one.
Strictly follow the prescribed output format for the review report.

Please output the review report in Chinese.
```

**Timeout**: 300s (adversarial review reads plan + multiple knowledge files). If Agent has not returned, terminate and offer retry (see Error Handling).

## User Confirmation Flow Details

### Step 1: Present Review Report

After spec-challenge agent returns:

1. **Return value validation**: Verify the report contains the required structure (## Fatal Flaws, ## Improvement Suggestions, ## Conclusion). If the report is missing critical sections:
   - Log to Ledger: `[FAILED: spec-challenge, reason: malformed report]`
   - Retry once with the same model
   - If retry also fails: output the partial report as-is with `[degraded: incomplete review]` header, proceed with whatever findings are available
2. **Ledger update**: Append one row to `.claude/ecw/session-data/{workflow-id}/session-state.md` Subagent Ledger table: `| spec-challenge | reviewer | ecw:spec-challenge | opus | large | {HH:mm} | {duration} |`. Scale reference: small (<20K tokens), medium (20-80K), large (>80K); spec-challenge agent is typically large. Note time before dispatch and compute duration after return.
3. **Persist report**: Write the full review report to `.claude/ecw/session-data/{workflow-id}/spec-challenge-report.md`. This MUST happen **before** any Plan modifications — the report is an independent artifact that records the original findings regardless of how the author responds.
4. **Present verbatim** the full review report to user. No responses, no judgments.

### Step 2: Per-Item Fatal Flaw Confirmation

For each fatal flaw (F1, F2, ...), use AskUserQuestion to ask the user:

```
Question: "[F{n}] {flaw title} — {flaw summary}. Your decision?"
Options:
  - "Agree to modify" — AI will modify the plan document to address this flaw
  - "Disagree" — Keep original plan; AI will draft technical rebuttal for your confirmation
  - "Needs discussion" — Enter discussion; you can provide additional context before deciding
```

**"Needs discussion" termination**: If user selects "Needs discussion" for the same flaw 3 times without reaching a decision, force closure: present the two options (agree/disagree) without the discussion option. Output `[Discussion limit reached for F{n}, forcing decision]`.

**Multiple fatal flaws can be combined into one AskUserQuestion (one question per flaw, max 4 per group).**

### Step 3: Batch Confirm Improvement Suggestions

After presenting the improvement suggestions (I1, I2, ...) list, use one multi-select AskUserQuestion for user to select which to adopt:

```
Question: "Which improvement suggestions should be adopted? Unselected ones will be deferred to future iterations."
multiSelect: true
Options: I1, I2, I3, ...
```

### Step 4: Execute Per User Decisions

Based on user selections:
- **Agreed fatal flaws** → Modify plan document, describe specific changes
- **Disagreed fatal flaws** → Draft technical rebuttal, present to user for confirmation
- **Adopted improvements** → Update document
- **Deferred improvements** → Record in document's "Future Iterations" section

**Plan Revision Strategy (CRITICAL)**:

The coordinator (main session) directly revises the plan document — do not dispatch a subagent for plan revision. Both the Plan content and the review findings are already in the coordinator's context, so delegating adds latency with no benefit.

Use Write to overwrite the entire plan file rather than incremental edits. Plan files are typically 50-80KB; do not use Edit for large plan files as exact-match replacement is fragile and error-prone on files of this size.

Exception: If the plan requires >30% content restructuring AND exceeds 100KB, a subagent may be dispatched, but it must also use Write (full overwrite), not Edit.

## Response Summary Format

After all items are handled, output summary table for user final confirmation:

```markdown
## Review Response Summary

| ID | Type | Title | User Decision | Execution Result |
|----|------|-------|--------------|-----------------|
| F1 | Fatal | ... | ✅ Agree to modify | Updated §3.2 |
| F2 | Fatal | ... | ❌ Disagree | Technical rebuttal: ... |
| F3 | Fatal | ... | ❓ Discussed, then agreed | Updated §4.1 |
| I1 | Improvement | ... | ✅ Adopted | Updated |
| I2 | Improvement | ... | ⏭️ Deferred | Recorded for future iterations |

**Status**: Awaiting user final confirmation
```

After outputting summary, use AskUserQuestion for user final confirmation:
- "Confirm passed" — Review complete, proceed to next phase
- "More changes needed" — User adds feedback, continue adjusting

## Review Completion Conditions

- User has **confirmed handling** for every fatal flaw
- All fatal flaws are either fixed (user agreed) or rebutted with technical rationale (user disagreed)
- User has selected which improvement suggestions to adopt/defer
- Document has been updated to reflect all "agree to modify" and "adopted" changes
- **User final confirmation** on response summary — review passed

## Error Handling

| Scenario | Handling |
|----------|---------|
| Spec-challenge Agent returns empty or fails | Record `FAILED` in Subagent Ledger → retry once → still fails: notify user `[DEGRADED: adversarial review unavailable]` and ask whether to proceed without review or retry manually |
| Spec-challenge Agent timeout (300s exceeded) | Record `TIMEOUT` in Subagent Ledger → **retry subagent once** (source code reading limits already enforced) → still times out: notify user and offer retry manually or proceed without review |
| Agent returns unstructured text (no F/I items) | Treat entire response as a single improvement suggestion (I1) and present to user for confirmation |
| `spec-challenge-report.md` write failure | Retry once → still fails: output full report in conversation and continue with user confirmation flow |

## Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "The plan is well-structured, probably no fatal flaws" | Well-structured plans with logical gaps are more dangerous than rough plans with sound logic. Structure is not correctness. |
| "The reviewer is being too harsh, these are edge cases" | Edge cases in P0/P1 changes become production incidents. The reviewer's job is to find them. |
| "User disagreed with the finding, so it's not important" | User drives decisions, but disagreement must come with technical rationale. Record the disagreement; do not silently drop the finding. |
| "Plan revision is a quick fix, I'll use Edit" | Large plan files (50-80KB) break Edit's exact-match replacement. Use Write for full overwrite. |
| "I'll skip the session split recommendation, user knows what to do" | Context management checkpoints are handled by PreCompact hook. Do not re-introduce session split AskUserQuestion — auto-continue to implementation. |

## Workflow Integration

### Auto-Trigger Scenarios

After ecw:writing-plans completes, ecw:spec-challenge adversarial review auto-triggers for:

- **P0 changes** (any domain mode)
- **P1 cross-domain changes** (high-risk changes involving 2+ domains — cross-domain coupling risks need independent review)

Flow:

1. ecw:writing-plans outputs plan file
2. **Trigger ecw:spec-challenge first** — Adversarial review of the plan
3. After challenge-response completes, present updated plan for user review
4. After user review passes, enter implementation

```
ecw:risk-classifier (P0 / P1 cross-domain)
  → ecw:requirements-elicitation / ecw:domain-collab
  → Phase 2
  → ecw:writing-plans: write plan
  → ecw:spec-challenge (adversarial review + author response)
  → user review (with challenge results visible)
  → implementation
```

### Post-Review: Auto-Continue to Implementation

After spec-challenge completes and user confirms review results (Plan updated), update session-state.md and **immediately proceed to implementation** — do NOT ask the user whether to continue or start a new session. All analysis artifacts are already persisted to `session-data/`; PreCompact hook automatically preserves checkpoints if context compression occurs.

> **CRITICAL — Auto-Continue Rule**: When `Auto-Continue` is `yes` in session-state.md:
> - Update session-state.md `Next` field, then **immediately invoke** the next skill based on Implementation Strategy:
>   - If `subagent-driven`: Invoke `ecw:tdd` (if `tdd.enabled: true` in ecw.yml), then `ecw:impl-orchestration`. If `tdd.enabled: false`, invoke `ecw:impl-orchestration` directly.
>   - If `direct`: Invoke `ecw:tdd` to begin the first Plan Task's RED phase.
> - Do NOT output additional confirmation text. The user already confirmed the workflow during Phase 1.
> - If `Auto-Continue` field is missing or `no`, fall back to showing strategy recommendation and waiting for user direction (backward compatibility).

### Manual Trigger

At any time, run `/spec-challenge <file path>` on any spec/plan file.
