# Phase 1: Root Cause Investigation — Detailed Steps

**BEFORE attempting ANY fix:**

**Step 1: Read Error Messages Carefully**
- Don't skip past errors or warnings
- Read stack traces completely
- Note line numbers, file paths, error codes

**Step 2: Reproduce Consistently**
- Can you trigger it reliably?
- What are the exact steps?
- If not reproducible, gather more data — don't guess

**Step 3: Check Recent Changes**
- What changed that could cause this?
- Git diff, recent commits
- New dependencies, config changes

**Step 4: Gather Evidence in Multi-Component Systems**

When system has multiple components (API → service → database, CI → build → deploy):

Before proposing fixes, add diagnostic instrumentation:
```
For EACH component boundary:
  - Log what data enters component
  - Log what data exits component
  - Verify environment/config propagation
  - Check state at each layer

Run once to gather evidence showing WHERE it breaks
THEN analyze evidence to identify failing component
THEN investigate that specific component
```

**Step 5: Domain Knowledge Cross-Reference**

Read `.claude/ecw/session-data/{workflow-id}/session-state.md` for risk level. Scale cross-reference depth by risk:

**P0/P1 — Full cross-domain tracing:**

1. From `.claude/ecw/ecw-path-mappings.md`, locate the bug's domain
2. Read domain's `business-rules.md` — check state machines, validation rules, concurrency controls
3. Query `cross-domain-calls.md` (§1) — trace upstream callers and downstream callees
4. Query `mq-topology.md` (§2) — check if affected code publishes/consumes messages; trace message flow
5. Query `shared-resources.md` (§3) — check if bug involves a shared service/component; list all consumers

> **Knowledge file robustness**: Verify each file exists before reading. For any missing file, log `[Warning: {file} not found, skipping this cross-reference dimension]` and continue with available files. If `ecw-path-mappings.md` is missing, use directory-based heuristic to infer domain (e.g., `src/main/java/{domain}/` path pattern).

**P2/P3 — Simplified check:**
1. Locate domain from `ecw-path-mappings.md`
2. Read domain's `business-rules.md`
3. Query `shared-resources.md` (§3) only — check shared resource contention

**If session-state.md doesn't exist** (e.g., debugging outside ECW flow), skip step 5 or use simplified check.

**Step 6: Trace Data Flow**

When error is deep in call stack:
- Where does bad value originate?
- What called this with bad value?
- Keep tracing up until you find the source
- Fix at source, not at symptom

**Phase 1 Checkpoint**: After completing all 6 steps, write evidence summary to `.claude/ecw/session-data/{workflow-id}/debug-evidence.md`:
```markdown
# Debug Evidence (Phase 1)
## Error: {error message summary}
## Reproduction: {steps or "not reproducible"}
## Recent Changes: {relevant git diff summary}
## Domain Cross-Reference: {findings from Step 5, or "skipped"}
## Data Flow Trace: {source of bad value, or "N/A"}
## Working Hypothesis: {initial hypothesis for Phase 2}
```
This ensures Phase 1 evidence survives context compaction during long debugging sessions.
