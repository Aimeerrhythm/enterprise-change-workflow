# Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "Changes are in one domain, no cross-domain impact" | Single-domain changes can affect shared resources consumed by other domains. Always check shared resources and end-to-end paths. |
| "The knowledge files are probably up to date" | Knowledge docs drift from code. Reverse validation catches stale entries. Skip it and the report includes phantom dependencies. |
| "No MQ or external references, so skip those sections" | Correct to skip if scan confirms no hits. But note it explicitly in Analysis Coverage — silent skips are the most dangerous blind spots. |
| "This is a low-risk query change, impact is minimal" | Query logic changes can affect downstream filtering. Medium risk, not minimal. Check end-to-end paths. |
| "Report is getting long but I need to include everything" | Conciseness is a hard constraint. Prioritize action items (max 3). Move verbose details to structured tables. |
