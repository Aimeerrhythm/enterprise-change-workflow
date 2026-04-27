# Anti-Patterns

## Never Rules

- Start implementation on main/master without explicit user consent
- Skip spec compliance review
- Proceed with unfixed spec issues
- Make subagent read plan file (provide full text)
- Skip scene-setting context
- Ignore subagent questions
- Accept "close enough" on spec compliance
- Skip review loops (issues found = fix = re-review)
- Let self-review replace actual review (both needed)
- **Start code quality review before spec compliance passes** (wrong order)
- Move to next task while review has open issues
- **Skip fact-forcing gate** — implementers must quote task requirements before editing and check cross-domain file ownership
- **Dispatch parallel tasks that share files** — file-conflict detection must prevent this; if missed, merge will fail
- **Send parallel Agent calls in separate messages** — all same-layer dispatches go in ONE message
- **Implement any task directly as coordinator** — always dispatch implementer subagents, even for the last remaining task or serial fallback. The coordinator coordinates; subagents implement. Implementing directly bypasses ecw.yml `models` config (coordinator runs on its own model, not the configured `implementation` model) and gateguard hook enforcement
- **Edit source code to fix spec review issues** — dispatch a repair implementer subagent instead. Same reason: coordinator edits bypass models config and hooks

## Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "These tasks are independent enough to skip dependency graph construction" | File-level conflicts are invisible from task descriptions. Two tasks touching the same file will cause merge conflicts. Build the graph. |
| "Single-message dispatch is awkward, I'll send them separately" | Sequential dispatch defeats parallelism. All same-layer tasks MUST go in one message. This is the entire point of parallel execution. |
| "Spec review passed, no need for code quality review at P0" | P0 error cost is extreme. Spec review checks correctness; code quality review checks maintainability. Both are mandatory at P0. |
| "The implementer said DONE, I trust the report" | Implementer reports may be incomplete or optimistic. Spec reviewer must read actual code independently. |
| "Pre-flight check failed but it's probably pre-existing" | Pre-existing failures cause cascading confusion across task dispatches. Fix or get user approval before proceeding. |
| "Task is BLOCKED after 2 retries, but one more try might work" | 2 re-dispatches is the hard limit. Escalate to user. Retrying without changes wastes budget. |
| "Only 2-3 tasks left, easier to just implement them myself" | Coordinator implementing directly bypasses ecw.yml `models` config (uses coordinator's model instead of configured `implementation` model) and skips gateguard hook enforcement. Always dispatch subagents — even for a single remaining task. |
| "Spec review found a small fix, I'll edit it inline instead of dispatching" | Coordinator editing code directly has the same bypass problem. Dispatch a repair implementer subagent — it takes 30s and respects the configured model + hooks. |
