# Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "Only one domain is really affected, the others are minor" | If other domains have any cross_domain_risks pointing at them, they need independent analysis. "Minor" impact is still impact. |
| "Round 2 negotiation is overkill for this requirement" | Round 2 catches companion changes that Round 1 independent analysis misses. Skip it and integration issues surface during implementation. |
| "Domain X returned none, so I can skip it in Round 2" | Check inbound risks first. If another domain flagged X in cross_domain_risks, X must participate in Round 2 even if its own analysis was none. |
| "I already know the cross-domain dependencies" | Knowledge docs may be stale. Code verification (Round 3 §3d) catches what assumptions miss. |
| "The requirement is clear enough to skip domain analysis" | Cross-domain coupling is invisible from requirements text. Only domain experts reading their own business rules can identify companion changes. |
| "I'll merge the domain reports manually instead of running Round 3" | Round 3 cross-validation catches conflicts and omissions that simple merging misses. The coordinator's systematic checks are the point. |
