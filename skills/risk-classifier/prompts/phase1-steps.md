# Phase 1 Reasoning Steps

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
