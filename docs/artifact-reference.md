# ECW Artifact Reference

Lookup table for all ECW project files. Use when you need to know where a file lives, when it's written, or what produces/consumes it.

## Required Files

Run `/ecw-init` after installation for project initialization, or manually create:

| File | Purpose |
|------|---------|
| `.claude/ecw/ecw.yml` | Project config (name, language, component types, scan patterns, paths) |
| `.claude/ecw/domain-registry.md` | Domain registry (domain definitions, knowledge directories, code directories) |
| `.claude/ecw/change-risk-classification.md` | Risk factor calibration (keyword→level mapping, sensitivity definitions) |
| `.claude/ecw/ecw-path-mappings.md` | Code path→domain mapping (used by biz-impact-analysis) |

## ECW Artifact Files (auto-generated)

| File | Write Timing | Purpose |
|------|-------------|---------|
| `.claude/ecw/session-data/{workflow-id}/session-state.md` | After risk-classifier Phase 1 output | ECW workflow state record + Subagent Ledger, for new session recovery |
| `.claude/ecw/session-data/{workflow-id}/domain-collab-report.md` | After domain-collab Round 3 completes | Full multi-domain collaboration analysis report |
| `.claude/ecw/session-data/{workflow-id}/knowledge-summary.md` | After domain-collab Round 3 completes | Knowledge file summary, reused across skills |
| `.claude/ecw/session-data/{workflow-id}/spec-challenge-report.md` | After spec-challenge agent returns | Adversarial review report |
| `.claude/ecw/session-data/{workflow-id}/requirements-summary.md` | After requirements-elicitation completes | Requirement summary checkpoint for downstream cold-start |
| `.claude/ecw/session-data/{workflow-id}/phase2-assessment.md` | After risk-classifier Phase 2 completes | Phase 2 structured conclusion for downstream cold-start |
| `.claude/ecw/session-data/{workflow-id}/impl-verify-findings.md` | After each impl-verify pass | Merged findings from all rounds (final summary) |
| `.claude/ecw/session-data/{workflow-id}/impl-verify-round{N}.md` | Immediately when each Round subagent returns | Per-round independent findings; survives partial failure |
| `.claude/ecw/session-data/{workflow-id}/biz-impact-report.md` | After biz-impact-analysis agent returns | Full business impact analysis report; required for Phase 3 calibration |
| `{worktree-root}/.claude/ecw/task-result.json` | Immediately before worktree implementer reports back | Implementer-written result file; coordinator reads from worktree path BEFORE git merge as authoritative Ledger source |
| `.claude/ecw/session-data/{workflow-id}/task-{N}-aggregation-warning.md` | When task-result.json is absent after worktree merge | Explicit gap marker written by coordinator; records that Ledger entry was inferred from git log |
| `.claude/ecw/calibration-log.md` | After Phase 3 calibration | Full-dimension comparison log (detailed tables for human review and pattern analysis) |
| `.claude/ecw/state/calibration-history.md` | After Phase 3 calibration | Concise structured index for Phase 1 automated quick-lookup |
| `.claude/ecw/state/instincts.md` | After Phase 3 calibration | Learned heuristic rules, injected by SessionStart when confidence > 0.7 |
| `.claude/ecw/knowledge-ops/doc-tracker.md` | After each knowledge-track run | Doc utilization tracking records (hit/miss/redundant/misleading) |
| `.claude/ecw/knowledge-ops/pending-entries.md` | After knowledge-track detects qualifying code-derived events | Candidate knowledge entries awaiting user review; Status: pending→accepted/rejected/written |
| `.claude/ecw/knowledge-ops/repo-map.md` | After knowledge-repomap / ecw-init | Auto-generated code structure index |
| `.claude/ecw/state/stale-refs.md` | After knowledge-audit run | Stale reference findings, consumed by verify-completion hook |
| `.claude/ecw/workspace.yml` | After workspace create | Workspace config: services, branches, build settings (workspace root only) |
| `.claude/ecw/session-data/{workflow-id}/cross-service-plan.md` | After workspace run Phase 1 + updated Phase 3 | Cross-service business decomposition → finalized with contracts + execution order |
| `{service}/.claude/ecw/workspace-analysis-task.md` | After workspace run Phase 1 | Per-service analysis task: original requirement (verbatim) + coordinator's hypothesis |
| `{service}/.claude/ecw/analysis-report.md` | After workspace run Phase 2 (child session) | Per-service technical plan: entry points, interaction pattern, concerns |
| `{service}/.claude/ecw/confirmed-contract.md` | After workspace run Phase 3 | Final aligned contracts for this service; triggers Phase 4 implementation |
| `{service}/status.json` | After workspace run Phase 4 (child session) | Child session completion marker, read by coordinator |

## Knowledge Files (populate as needed)

| File | Purpose |
|------|---------|
| `.claude/knowledge/common/cross-domain-rules.md` | Cross-domain call rules and global constraints |
| `.claude/knowledge/common/cross-domain-calls.md` | Cross-domain direct call matrix |
| `.claude/knowledge/common/mq-topology.md` | MQ Topic publish/consume relationships |
| `.claude/knowledge/common/shared-resources.md` | Cross-domain shared resource table |
| `.claude/knowledge/common/external-systems.md` | External system integrations |
| `.claude/knowledge/common/e2e-paths.md` | End-to-end critical paths |
