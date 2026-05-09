# Phase 1 Output Template

First output a brief assessment (no more than 5 lines):

```markdown
## Change Risk Pre-Assessment (Phase 1)

**P{X}** | {single-domain/cross-domain} ({domain list}) | {multi-domain collab/B/none} | {one-line rationale}

Downstream routing: {full routing chain, e.g., ecw:domain-collab(multi-domain) → Phase 2 → ecw:writing-plans → TDD:RED → Implementation(GREEN) → ecw:biz-impact-analysis → Phase 3}
```

Then output:
```
[Auto-Flow] Risk: P{X} | {single-domain/cross-domain} ({domain list}) | Route: {routing chain}. Auto-proceeding...
```
Then invoke the next downstream skill. The user can interrupt at any time if they disagree with the classification.
