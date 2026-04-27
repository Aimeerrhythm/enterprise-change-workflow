# Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "The plan is well-structured, probably no fatal flaws" | Well-structured plans with logical gaps are more dangerous than rough plans with sound logic. Structure is not correctness. |
| "The reviewer is being too harsh, these are edge cases" | Edge cases in P0/P1 changes become production incidents. The reviewer's job is to find them. |
| "User disagreed with the finding, so it's not important" | User drives decisions, but disagreement must come with technical rationale. Record the disagreement; do not silently drop the finding. |
| "Plan revision is a quick fix, I'll use Edit" | Large plan files (50-80KB) break Edit's exact-match replacement. Use Write for full overwrite. |
| "I'll skip the session split recommendation, user knows what to do" | Context management checkpoints are handled by PreCompact hook. Do not re-introduce session split AskUserQuestion — auto-continue to implementation. |
