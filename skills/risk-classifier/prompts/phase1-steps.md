# Phase 1 Reasoning Steps

## Step 1: Keyword Extraction & Domain Identification

Extract from user's requirement description:
- **Business keywords** → Map to domains via project CLAUDE.md domain routing table (keyword→domain mapping); count matched domains for single/cross-domain routing (see `workflow-routes.yml`)
- **Operation keywords** → Determine operation type (CRUD, state changes, message format, etc.)
- **Sensitive words** → Read ecw.yml `paths.risk_factors` (default `.claude/ecw/change-risk-classification.md`) §Quick Reference keyword→level mapping; any match → at least P1

## Step 2: Quick Shared Resource Check

Read `shared-resources.md` (§3) under ecw.yml `paths.knowledge_common`. If file missing, log `[Warning: {file} not found]` and skip. Read risk factors §Factor 1 for domain dependency thresholds.

Phase 1 checks §3 (shared resources) + §2 (MQ topology, only if user mentions MQ). Does not check §1/§4/§5 (deferred to Phase 2). **P2 single-domain**: if shared resources or MQ write-ops found, **upgrade to P1 immediately**.

## Step 3: Composite Assessment

```
Total Risk = max(Keyword Estimated Level, Shared Resource Level)
Cross-Domain = Step 1 matched domain count >= 2 ? "cross-domain" : "single-domain"
```

Full three-dimensional factors in ecw.yml `paths.risk_factors` §Three-Dimensional Risk Factors. Phase 1 uses first two dimensions only.

**Calibration history**: Check `.claude/ecw/state/calibration-history.md` — scan last 10 entries for keyword overlap, adjust ±1 level max if systematic deviation found. Log adjustment: `[Phase 1 adjusted P{x} → P{y} based on calibration history]`. If file missing or empty, skip silently.

If information insufficient, **default to P2**. Look up routing in `workflow-routes.yml`.
