# Code Quality Review Template (P0 Only)

For P0 risk level, after ALL spec reviews pass, dispatch code quality reviews in parallel:

```
Agent(description: "Code quality review for Task N"):
  Review the implementation for Task N.

  Files changed: [list from implementer report]

  Check:
  - Each file has one clear responsibility
  - Units decomposed for independent testing
  - Following file structure from plan
  - Clean, maintainable code
  - Names clear and accurate
  - No overbuilding (YAGNI)
  - Tests verify behavior (not mock behavior)

  Report: Strengths, Issues (Critical/Important/Minor), Assessment (Approved/Needs Fix)
```

If issues found → fix sequentially on current branch → re-review (max 2 rounds per task).
