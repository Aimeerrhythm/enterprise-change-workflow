# Phase 2 Subagent Return Schema

Subagent executes Steps 1-4 internally and returns structured YAML:

```yaml
risk_level: P{X}
phase1_level: P{Y}
level_change: upgraded | downgraded | unchanged
affected_domains: [domain1, domain2]
classification_factors:
  impact_scope: {level: P{X}, details: "..."}
  change_type: {level: P{X}, details: "..."}
  business_sensitivity: {level: P{X}, details: "..."}
dependency_graph:
  cross_domain_calls: [{from: X, to: Y, method: Z}]
  mq_impacts: [{topic: T, publishers: [...], consumers: [...]}]
  shared_resources: [{resource: R, consumers: [...]}]
  external_impacts: [{system: S, direction: inbound|outbound, interface: I}]
  e2e_paths: [{path_name: P, affected_step: S}]
upgrade_reason: "..."  # if upgraded
```

**Return value validation**: Coordinator verifies required fields (`risk_level`, `phase1_level`, `level_change`, `affected_domains`, `classification_factors`) exist in the YAML. If validation fails:
1. Log to Ledger: `[FAILED: phase2-subagent, reason: invalid return format]`
2. Retry once with the same model
3. If retry also fails: use Phase 1 level as final level, mark Phase 2 as `[degraded: format error]`, continue to writing-plans
