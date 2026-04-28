# Anti-Patterns

## Never Rules

- **Never leave implementation options in confirmed-contract.md** — the contract must specify exactly one approach. If the coordinator is unsure which approach to take, surface the decision to the user via AskUserQuestion before writing the contract. Leaving "A or B" choices in the contract shifts an architecture decision onto the child session, making implementation non-reproducible.
- **Never let child sessions write coordinator's session-state.md** — coordinator is the sole owner of `.claude/ecw/session-data/{wf-id}/session-state.md`. Child sessions only write their own artifacts (analysis-report.md, status.json). State updates are always done by the coordinator at gate transitions.
- **Never skip Phase gates** — artifact must exist before next Phase
- **Never use code-reading tools in Phase 1** — Phase 1 information source is workspace.yml requirement ONLY. No Read, Bash, Glob, Grep, or Explore tools. If code detail is needed to answer a question, it's an Open Question for Phase 2, not something to resolve in Phase 1.
- **Never put code-level detail in Phase 1 output** — class names, method names, field names, SQL in cross-service-plan.md or workspace-analysis-task.md are Phase 1 violations.
- **Never have coordinator write implementation tasks** — child sessions own task decomposition via ecw:writing-plans; coordinator distorts when it specifies "which class/method"
- **Never paraphrase the original requirement** — pass verbatim text to child sessions; paraphrasing loses intent
- **Never resolve contract conflicts without user** — architecture decisions (sync vs async, who owns what) require human judgment
- **Never run Provider + Consumer in parallel for Dubbo without api-ready.json** — Consumer must use non-blocking scheduling: skip Dubbo-dependent tasks until Provider writes api-ready.json, work on independent tasks first. For MQ, full parallel execution is correct.
- **Never generate Phase 4 start scripts** — Analysis sessions continue into Phase 4 automatically after detecting confirmed-contract.md. The coordinator does not open new sessions at Phase 4.
- **Never use `keystroke` on macOS** — clipboard paste only (input method corruption)
- **Never assume terminal type** — detect or fall back to manual

## Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "I'll just quickly scan the code in Phase 1 to confirm the interaction pattern" | Phase 1 is information-constrained: workspace.yml only. If you can't determine the pattern from the requirement, mark it "unclear" and let Phase 2 investigate. Scanning code in Phase 1 produces class-level detail that belongs to child sessions — and your scan will be incomplete anyway. |
| "I'll just write the implementation task for the service, it'll be faster" | Coordinator doesn't know the service's internal structure. Child sessions do. Pre-written tasks will have wrong class/method locations. |
| "The business decomposition is obvious, skip Phase 1 confirmation" | Interaction patterns (Dubbo vs MQ, sync vs async) are often ambiguous. Get user confirmation before Phase 2 starts. |
| "The contract conflict is minor, I'll just pick one side" | Even minor contract decisions (field name, type) affect multiple services. Always surface to user. |
| "Phase 2 child sessions are taking too long, I'll analyze the code myself" | Coordinator doesn't have the service-specific knowledge that child sessions + ECW knowledge files provide. |
| "Only one service changed its contract, I'll update only that one" | Contract changes cascade. If wms changes DTO, both sci AND ofc might be affected. Check all consumers. |
