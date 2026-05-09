# Risk Assessment Steps

## Step 1: Keyword Extraction & Domain Identification

Extract from user's requirement description:
- **Domain identification** → Map to domains via project CLAUDE.md domain routing table; count matched domains for single/cross-domain routing (see `workflow-routes.yml`)
- **Operation type** → Determine operation type (CRUD, state changes, message format, external system calls, etc.)
- **Change scope** → What components change: public method signatures, state machine logic, MQ message format, shared service, private internals

## Step 2: Domain Knowledge Cross-Reference

For each matched domain, read its `business-rules.md` under `.claude/knowledge/{domain}/`. If missing, log `[Warning: {domain} business-rules.md not found]` and continue.

Assess impact based on:
- **Shared resources**: Read `shared-resources.md` under ecw.yml `paths.knowledge_shared`. Count how many domains depend on the changed component → more dependents = higher risk
- **Change type risk**:
  - State machine logic / public method deletion or rename / MQ message format (breaking) → P0
  - Method signature change with cross-domain callers / data write ops / new external MQ topic / core entity field change → P1
  - New public method / query condition change / config-driven branches → P2
  - Log/comment/constant/private method → P3
- **Business sensitivity**: From domain's business-rules.md — operations involving irreversible side effects (financial, order lifecycle, external system contracts) → elevate to P0/P1

## Step 3: Composite Assessment

```
Total Risk = max(Change Type Risk, Shared Resource Risk, Business Sensitivity)
Cross-Domain = matched domain count >= 2 ? "cross-domain" : "single-domain"
```

If information insufficient (no domain docs, ambiguous scope), **default to P1**. Look up routing in `workflow-routes.yml`.


## Assessment Output Fields

The assessment produces exactly 4 fields:

| Field | Values | Description |
|-------|--------|-------------|
| `risk_level` | P0 / P1 / P2 / P3 | Result of composite assessment |
| `domain_scope` | single-domain / cross-domain | Based on matched domain count |
| `entry_skill` | ecw:requirements-elicitation / ecw:domain-collab / ecw:writing-plans / (none for P3) | First downstream skill |
| `rationale` | one-line string | Key reason for level assignment |

These 4 fields drive `routing[0]` (= `entry_skill`) and populate the confirmation output below.

## Assessment Output and Confirmation Flow

First output a brief assessment (no more than 5 lines):

```markdown
## Change Risk Pre-Assessment

**P{X}** | {single-domain/cross-domain} ({domain list}) | {multi-domain collab/B/none} | {one-line rationale}

Downstream routing: {full routing chain, e.g., ecw:domain-collab(multi-domain) → Phase 2 → ecw:writing-plans → TDD:RED → Implementation(GREEN) → ecw:biz-impact-analysis → Phase 3}
```

Then output:
```
[Auto-Flow] Risk: P{X} | {single-domain/cross-domain} ({domain list}) | Route: {routing chain}. Auto-proceeding...
```

Then write session-state to `.claude/ecw/session-data/{workflow-id}/session-state.json`:
- `{workflow-id}`: date from `currentDate` system-reminder (YYYYMMDD) + `-` + 4 random hex chars (e.g. `20260509-a3f1`). Check for conflict first; regenerate suffix up to 3 times if file exists.
- Read `./session-state-format.md` for the exact JSON schema.
- Write `routing[0]` only — the auto-continue hook reconstructs the full chain.

Then invoke the next downstream skill. The user can interrupt at any time if they disagree with the classification.
