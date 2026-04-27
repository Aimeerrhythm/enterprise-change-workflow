# Common Mistakes

| Mistake | Consequence | Correction |
|---------|------------|------------|
| Phase 1 proceeded without waiting for user confirmation | User cannot adjust level | Must wait for user confirmation before invoking downstream skills |
| P0 change skipped ecw:spec-challenge | Plan blind spots unexposed | Roll back, run ecw:spec-challenge |
| Phase 2 upgrade did not backfill workflow | High-risk change went through low-risk workflow | Upgrade is mandatory; must backfill |
| Downgrade applied without user confirmation | Workflow simplified without human approval | Downgrade is suggested; requires human confirmation |
| Only checked keywords, skipped §3 | Missed shared resource impact | Phase 1 must check §3 |
| Cross-domain requirement routed to ecw:requirements-elicitation | Missing per-domain independent analysis and cross-validation | 2+ domain matches must route to ecw:domain-collab |
| Forgot ecw:biz-impact-analysis after impl-verify | Business impact of code changes not assessed | P0/P1 changes must invoke `/biz-impact-analysis` after impl-verify |
| P0-P2 change skipped TDD:RED | No failing test to prove test effectiveness | Test-first is a structural requirement, not optional |
| Bug fix without reproduction test | Fix correctness cannot be automatically verified | Write reproduction test first (RED), then fix to make it pass (GREEN) |
| Skipped Phase 3 after biz-impact-analysis | Prediction deviation not discovered; rules cannot improve | Must execute Phase 3 calibration after biz-impact-analysis report |
| Phase 3 suggestion applied without user confirmation | Single change may be coincidental; auto-modification may introduce bias | Phase 3 only outputs suggestions; user decides whether to adopt |
