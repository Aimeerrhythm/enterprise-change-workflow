# Phase 1 Output Template

First output a brief assessment (no more than 5 lines):

```markdown
## Change Risk Pre-Assessment (Phase 1)

**P{X}** | {single-domain/cross-domain} ({domain list}) | {multi-domain collab/B/none} | {one-line rationale}

Downstream routing: {full routing chain, e.g., ecw:domain-collab(multi-domain) → Phase 2 → ecw:writing-plans → TDD:RED → Implementation(GREEN) → ecw:biz-impact-analysis → Phase 3}
```

Then check ecw.yml `auto_flow.auto_confirm`:

**If `auto_confirm: true`** — Skip AskUserQuestion. Output:
```
[Auto-Flow] Risk: P{X} | {single-domain/cross-domain} ({domain list}) | Route: {routing chain}. Auto-proceeding...
```
Then **immediately invoke** the next downstream skill (same as "Proceed" path below). The user can interrupt at any time if they disagree with the classification.

**If `auto_confirm: false` (default)** or `auto_flow` section missing — use `AskUserQuestion` tool for user confirmation:

```
Question: "Risk level P{X}, proceed with the above workflow?"
Options:
  1. "Proceed (Recommended)" — Execute with current level and routing
  2. "Adjust level" — Upgrade or downgrade risk level (will ask target level after selection)
  3. "Analysis only" — Complete impact analysis without entering implementation
  4. "Emergency fix" — Use fast track, skip full workflow
```

> **CRITICAL — Auto-Continue Rule**: When user selects "Proceed", you MUST **immediately invoke** the next downstream skill (e.g., `ecw:domain-collab` or `ecw:requirements-elicitation`). Do NOT output any text like "下一步…是否继续？", "Ready to proceed?", or any form of confirmation prompt. The user's selection of "Proceed" IS the confirmation — no second confirmation is needed. This applies to ALL subsequent skill transitions in the routing chain: after domain-collab completes, after Phase 2 completes, etc. — always immediately invoke the next skill without asking.
