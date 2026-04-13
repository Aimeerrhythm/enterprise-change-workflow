# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2025-04-13

Initial release of ECW (Enterprise Change Workflow) plugin for Claude Code.

### Added

- **Risk Classifier** (`ecw:risk-classifier`) — Three-phase (P0-P3) risk classification with feedback calibration
  - Phase 1: Quick keyword-based risk prediction
  - Phase 2: Precise grading with full dependency graph (§1-§5)
  - Phase 3: Post-implementation calibration against actual business impact
- **Domain Collaboration** (`ecw:domain-collab`) — Multi-domain collaborative analysis with three rounds: independent analysis, cross-domain negotiation, and coordinator verification
- **Requirements Elicitation** (`ecw:requirements-elicitation`) — 9-dimension systematic questioning for single-domain P0/P1 requirements
- **Spec Challenge** (`ecw:spec-challenge`) — Adversarial spec review via independent agent, challenge-response cycles for P0 and P1 cross-domain plans
- **Cross-Review** (`ecw:cross-review`) — Structured multi-round cross-consistency verification, converges only when zero findings in a round
- **Business Impact Analysis** (`ecw:biz-impact`) — Git diff-driven business impact analysis dispatched to specialized agent
- **Agents**: `biz-impact-analyzer` (5-step impact analysis) and `spec-challenger` (4-dimension adversarial review)
- **Commands**: `/ecw-init` (project initialization wizard with Attach/Manual/Scaffold modes), `/ecw-validate-config` (7-step configuration validation)
- **Completion Verification Hook** — PreToolUse hook with 3 hard blocks (broken references, stale references, Java compilation) and 1 soft reminder (knowledge doc sync)
- **Java/Spring Scanners** — Shell scripts for extracting cross-domain calls, shared resources, and MQ topology
- **Template System** — Configuration templates (ecw.yml, domain-registry, risk-classification, path-mappings, calibration-log) and knowledge file templates (common §1-§5, per-domain index/rules/model)
- **CLAUDE.md Integration** — Plugin-level guidance with workflow diagram, skill trigger conditions, and completion verification rules

[0.1.0]: https://github.com/Aimeerrhythm/enterprise-change-workflow/releases/tag/v0.1.0
