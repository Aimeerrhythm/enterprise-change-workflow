# Common Mistakes

| Mistake | Consequence | Correction |
|---------|------------|------------|
| Risk assessment proceeded without waiting for user confirmation | User cannot adjust level | Must wait for user confirmation before invoking downstream skills |
| P0 change skipped ecw:spec-challenge | Plan blind spots unexposed | Roll back, run ecw:spec-challenge |
| Downgrade applied without user confirmation | Workflow simplified without human approval | Downgrade is suggested; requires human confirmation |
| Only checked keywords, skipped §3 | Missed shared resource impact | Risk assessment must check §3 |
| Cross-domain requirement routed to ecw:requirements-elicitation | Missing per-domain independent analysis and cross-validation | 2+ domain matches must route to ecw:domain-collab |
| Forgot ecw:biz-impact-analysis after impl-verify | Business impact of code changes not assessed | P0/P1 changes must invoke `/biz-impact-analysis` after impl-verify |
| P0-P2 change skipped TDD:RED | No failing test to prove test effectiveness | Test-first is a structural requirement, not optional |
| Bug fix without reproduction test | Fix correctness cannot be automatically verified | Write reproduction test first (RED), then fix to make it pass (GREEN) |
