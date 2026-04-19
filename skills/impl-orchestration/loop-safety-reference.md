# Loop Safety Controls

Guard against infinite loops and runaway subagent costs.

## Per-Task Iteration Limits

| Review Type | Max Rounds | On Limit Reached |
|-------------|-----------|-----------------|
| Spec compliance review | **3** | Escalate to user: list unresolved spec gaps, ask whether to accept, adjust plan, or abort task |
| Code quality review (P0) | **2** | Escalate to user: list remaining quality issues, ask whether to accept or defer to impl-verify |
| BLOCKED re-dispatch | **2** | Escalate to user: provide full blocked context, ask for guidance |
| NEEDS_CONTEXT re-dispatch | **3** | Escalate to user: the task may be under-specified in the plan |

## Global Budget

**Total subagent dispatches across all tasks: maximum 50.** Count every Agent tool call (implementer, spec-reviewer, code-quality, re-dispatch). Parallel dispatches in the same message each count as 1.

When approaching the limit (≥ 40), warn user: "Approaching global dispatch budget ({N}/50). {M} tasks remaining."

If budget exhausted before all tasks complete, escalate to user with options:
1. "Extend budget" — continue with +15 dispatches
2. "Switch to direct implementation" — complete remaining tasks without subagents
3. "Stop here" — mark remaining tasks as pending for next session

## Repeated Error Detection

Track spec review failure reasons per task. If the **same spec gap** (matching description) appears in 2 consecutive review rounds after implementer claims to have fixed it:

1. **Pause** the review loop
2. **Report** to user: "Task {N} spec review found the same issue ({description}) in 2 consecutive rounds after fix attempts."
3. **Ask** via AskUserQuestion:
   - "Re-dispatch with more capable model" — upgrade model tier
   - "Provide additional context" — user adds clarification
   - "Skip this check" — accept the current implementation with a note

## Stall Detection

If a single task consumes **≥ 6 subagent dispatches** (implementation + reviews + re-dispatches combined), pause and escalate:

"Task {N} has consumed {count} dispatches without completing. This suggests the task may be too complex or the plan may need revision."

## Layer Timeout

If all implementers in a layer exceed their individual timeouts AND total layer wall-clock time exceeds **600s**, terminate remaining agents:
1. Collect results from completed agents
2. Move timed-out tasks to a retry sub-layer
3. Retry with simplified scope or escalated model
4. If retry also times out, escalate to user
