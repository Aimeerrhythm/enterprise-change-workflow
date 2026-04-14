# Enterprise Change Workflow (ECW)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)

[中文文档](README.zh-CN.md)

> Give AI the ability to "change one line of code, trace the full-chain impact" in large projects.

## What Problem Does It Solve

AI coding assistants excel at independent changes, but in large multi-module projects, modifying one component can cascade across multiple business domains. Typical pain points:

- Changed a Facade method signature, unaware that 5 other domains call it
- Fixed an MQ message format, missed 3 external system consumers
- Took on a "simple requirement" that actually involves state machine changes, shared resources, and end-to-end paths

ECW provides a structured change management workflow that makes AI assess risk, analyze impact, and cross-verify before writing code — ensuring nothing is missed.

## Core Concepts

### Three-Phase Risk Classification

ECW's core is a **P0-P3 four-level risk classification** that drives workflow depth:

| Level | Risk | Workflow Depth | Typical Scenarios |
|-------|------|---------------|------------------|
| **P0** | Critical | Full workflow: requirements elicitation → precise grading → full plan → adversarial review → implementation → impl-verify → impact analysis → calibration | Multi-domain state machine changes, core path refactoring |
| **P1** | High | Full workflow minus adversarial review (except cross-domain) | Shared resource modifications, MQ format changes |
| **P2** | Medium | Simplified: plan → implementation → impl-verify → impact analysis | Single-domain field additions, local logic adjustments |
| **P3** | Low | Direct implementation | Log adjustments, copy changes, config updates |

**Core principle: Changing a log line and changing inventory deduction should not require the same process.**

### Three Phases

| Phase | When | Data Source | Purpose |
|-------|------|-------------|---------|
| **Phase 1** | After user describes requirement | Keyword matching + shared resource table | Quick risk prediction, determine workflow path |
| **Phase 2** | After requirement analysis | Full dependency graph (§1-§5) | Precise grading, upgrade/downgrade if needed |
| **Phase 3** | After implementation + impact analysis | biz-impact-analysis report | Calibrate prediction accuracy, improve classification rules |

### Knowledge-Driven Impact Analysis

ECW relies on project-level knowledge files for precise analysis. Five types of cross-domain knowledge form the dependency graph:

| # | Knowledge File | Content | Used By |
|---|---------------|---------|---------|
| §1 | `cross-domain-calls.md` | Domain-to-domain call matrix | Phase 2, domain-collab, biz-impact-analysis |
| §2 | `mq-topology.md` | MQ topic publish/subscribe relationships | Phase 1 (lightweight), Phase 2, biz-impact-analysis |
| §3 | `shared-resources.md` | Services/components shared by 2+ domains | Phase 1, Phase 2, biz-impact-analysis |
| §4 | `external-systems.md` | External system integrations | Phase 2, biz-impact-analysis |
| §5 | `e2e-paths.md` | End-to-end critical business paths | Phase 2, biz-impact-analysis |

## Workflow Overview

```
User proposes requirement / change / bug
        |
        v
  Risk Classifier — Phase 1 (Quick P0-P3 prediction)
        |
   +----+----+----------------+--------+
   |         |                |        |
 Single    Cross-domain     P2/P3    Bug
 domain    (2+ domains)      |        |
   |         |                |        |
 Requirements  Domain Collab  |   Systematic
 Elicitation   (parallel      |   Debugging
 (P0/P1)       agent          |   (locate+fix)
   |           analysis)      |        |
   +----+----+                |        |
        |                     |        |
  Phase 2 (Precise grading)   |        |
        |                     |        |
  Implementation Plan  <------+        |
        |                              |
  [P0; P1 cross-domain: Spec Challenge] |
        |                              |
  Implementation  <--------------------+
        |
  Impl-Verify (code correctness + quality verification)
        |
  Business Impact Analysis
        |
  [P0/P1: Phase 3 feedback calibration]
        |
  Mark complete → Completion Verification Hook (automatic checks)
```

## Components

### Skills (7)

| Component | Trigger | Description |
|-----------|---------|-------------|
| `ecw:risk-classifier` | Any change/requirement/bug | P0-P3 risk classification + workflow routing, three phases (predict → precise → calibrate) |
| `ecw:domain-collab` | Cross-domain requirements (2+ domains) | Parallel domain agents analyze independently → mutual evaluation → coordinator cross-verification |
| `ecw:requirements-elicitation` | Single-domain P0/P1 requirements | 9-dimension systematic questioning to fully understand requirements |
| `ecw:spec-challenge` | After plan output (P0; P1 cross-domain only) | Dispatches independent agent for adversarial plan review, challenge-response cycles |
| `ecw:impl-verify` | After implementation (P0-P2) | Multi-round convergence: code ↔ requirements/rules/plan/standards, severity-based exit. Replaces code-reviewer |
| `ecw:biz-impact-analysis` | After impl-verify | Git diff → dispatches agent to analyze business impact, outputs structured report |
| `ecw:cross-review` | Manual only (`/ecw:cross-review`) | Cross-file structural consistency verification for document-heavy changes (optional tool) |

### Agents (2)

| Component | Dispatcher | Description |
|-----------|-----------|-------------|
| `biz-impact-analysis` | `ecw:biz-impact-analysis` | 5-step analysis: diff parsing → dependency graph queries → code scanning → external system evaluation → report generation |
| `spec-challenge` | `ecw:spec-challenge` | 4-dimension review: accuracy / information quality / boundaries & blind spots / robustness → fatal flaws + improvement suggestions |

### Commands (3)

| Component | Description |
|-----------|-------------|
| `/ecw-init` | Project initialization wizard (3 modes: Attach/Manual/Scaffold) |
| `/ecw-validate-config` | Validate ECW configuration completeness (7-step check, outputs pass/warn/fail report) |
| `/ecw-upgrade` | Upgrade project ECW configuration to latest plugin version (idempotent migrations, partial failure protection) |

### Hook (1)

| Component | Trigger | Description |
|-----------|---------|-------------|
| `verify-completion` | PreToolUse auto-intercepts TaskUpdate(completed) | 4 hard blocks + 1 soft reminder |

**Hard blocks (failure → prevents completion):**
1. Broken reference check — modified files reference non-existent `.claude/` paths
2. Stale reference check — deleted files still referenced elsewhere
3. Java compilation check — auto-runs `mvn compile` when `.java` files are modified
4. Java test check — auto-runs `mvn test` when `.java` files are modified (controlled by `ecw.yml` `verification.run_tests`)

**Soft reminder (non-blocking, injects systemMessage):**
5. Knowledge doc sync reminder — business code changed but corresponding domain knowledge docs not updated

## Installation

### Prerequisites

- **Claude Code CLI** — ECW is a Claude Code plugin, requires CLI environment
- **superpowers plugin** — Provides `writing-plans`, `executing-plans`, `systematic-debugging` and other foundational skills

### Step 1: Register Marketplace

Add to `extraKnownMarketplaces` in `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "enterprise-change-workflow": {
      "source": {
        "source": "github",
        "repo": "Aimeerrhythm/enterprise-change-workflow"
      }
    }
  }
}
```

### Step 2: Install Plugin

```bash
claude plugin install ecw@enterprise-change-workflow
```

Verify installation:

```bash
claude plugin list
# Should show ecw@enterprise-change-workflow
```

### Step 3: Enable Plugin

Confirm `enabledPlugins` in `~/.claude/settings.json` includes:

```json
{
  "enabledPlugins": {
    "ecw@enterprise-change-workflow": true
  }
}
```

> `claude plugin install` usually adds this entry automatically. If not, add it manually.

### Step 4: Restart Claude Code

Plugins load on next session start. Exit current session and restart Claude Code.

### Step 5: Initialize Project Configuration

Launch Claude Code in your target project directory and run:

```
/ecw-init
```

The initialization wizard supports 3 modes:

| Mode | Use Case | Creates |
|------|----------|---------|
| **Attach** | Project already has documentation | ECW config files only (5 files), preserves existing docs |
| **Manual** | Docs in non-standard locations | Config files + user-specified paths |
| **Scaffold** | New project | Config files + complete knowledge file templates |

Generated configuration files:

```
.claude/ecw/
├── ecw.yml                      # Project config: name, language, component types, scan patterns, verification settings
├── domain-registry.md           # Domain registry: definitions, knowledge dirs, code dirs
├── change-risk-classification.md # Risk classification calibration: factor weights, keyword mappings
├── ecw-path-mappings.md         # Code path → domain mappings (used by biz-impact-analysis)
└── calibration-log.md           # Phase 3 calibration history (auto-appended)
```

### Step 6: Configure Project CLAUDE.md

Add ECW integration configuration to your project's `CLAUDE.md`. Refer to `templates/CLAUDE.md.snippet` for the template. Core content:

1. **Domain knowledge routing table** — keyword → domain mappings for risk-classifier and domain-collab
2. **Completion verification rules** — structured self-check requirements before marking complete
3. **Impact analysis tool distinction** — `ecw:domain-collab` (requirements phase) vs `ecw:biz-impact-analysis` (code phase)

### Step 7: Populate Knowledge Files

Knowledge file quality directly determines impact analysis accuracy. Java/Spring projects can use built-in scanning scripts:

```bash
# Run in target project root directory
bash <plugin-path>/scripts/java/scan-cross-domain-calls.sh <project_root> <path_mappings_file>
bash <plugin-path>/scripts/java/scan-shared-resources.sh <project_root> <path_mappings_file>
bash <plugin-path>/scripts/java/scan-mq-topology.sh <project_root>
```

Scan results output Markdown tables to stdout, ready to paste into the corresponding knowledge files. Scans use grep heuristics (high recall, possible false positives) — manual review before committing is recommended.

### Verify Installation

```
/ecw-validate-config
```

This command runs 7-step checks and outputs pass/warn/fail status for each configuration file, helping you confirm configuration completeness.

## Knowledge File System

ECW relies on knowledge files in your project to make accurate domain judgments and impact analysis. Knowledge files live under `.claude/knowledge/`.

### Cross-Domain Common Knowledge (`common/`)

| File | Description | Phase 1 | Phase 2 | biz-impact-analysis |
|------|-------------|---------|---------|------------|
| `cross-domain-rules.md` | Index file, knowledge usage guide | — | Reference | Reference |
| `cross-domain-calls.md` (§1) | Domain-to-domain call matrix | — | Query | Query |
| `mq-topology.md` (§2) | MQ topic pub/sub relationships | Keywords | Query | Query |
| `shared-resources.md` (§3) | Cross-domain shared resource table | Query | Query | Query |
| `external-systems.md` (§4) | External system integration list | — | Query | Query |
| `e2e-paths.md` (§5) | End-to-end critical business paths | — | Query | Query |

### Domain-Level Knowledge (one directory per domain)

| File | Description |
|------|-------------|
| `00-index.md` | Domain entry: path lookup, node locations, Facade maps, external system interactions |
| `business-rules.md` | Business rules: concurrency control, idempotency, state machines, validation rules, cross-domain constraints |
| `data-model.md` | Data model: core table structures, enum definitions, ER relationships, indexes |

## Supported Project Types

`ecw.yml` adapts to different tech stacks via `component_types` and `scan_patterns`:

| Tech Stack | Typical Component Types | Scan Patterns |
|-----------|------------------------|---------------|
| **Java/Spring** | BizService, Manager, DO, Controller, Mapper | @Resource, @DubboReference, RocketMQ |
| **Go** | Handler, Repository, Service | import, interface |
| **Node/TypeScript** | Service, Controller, Middleware | import/require, EventEmitter |
| **Python** | Service, Repository, Handler | import, Celery |

## Project Structure

```
enterprise-change-workflow/
├── .claude-plugin/
│   ├── plugin.json              # Plugin metadata
│   └── marketplace.json         # Marketplace descriptor
├── skills/                      # 7 core skills
│   ├── risk-classifier/         # Risk classification (P0-P3, three phases)
│   ├── domain-collab/           # Cross-domain collaborative analysis (three rounds)
│   ├── requirements-elicitation/# Requirements elicitation (9-dimension questioning)
│   ├── spec-challenge/          # Adversarial review (challenge-response cycles)
│   ├── impl-verify/             # Implementation correctness verification (multi-round convergence, up to 5 rounds)
│   ├── cross-review/            # Cross-file consistency verification (manual optional tool)
│   └── biz-impact-analysis/     # Business impact analysis (5-step structured)
├── agents/
│   ├── biz-impact-analysis.md   # Impact analysis agent
│   └── spec-challenge.md       # Adversarial review agent
├── commands/
│   ├── ecw-init.md              # Project initialization wizard
│   ├── ecw-validate-config.md   # Configuration validation command
│   └── ecw-upgrade.md           # Configuration upgrade command (versioned migrations)
├── hooks/
│   ├── hooks.json               # Hook registration (PreToolUse → TaskUpdate)
│   └── verify-completion.py     # Completion verification hook (5 checks: 4 hard blocks + 1 soft reminder)
├── templates/                   # Config and knowledge file templates
│   ├── ecw.yml                  # Project config template
│   ├── domain-registry.md       # Domain registry template
│   ├── change-risk-classification.md # Risk classification calibration template
│   ├── calibration-log.md       # Calibration history template
│   ├── ecw-path-mappings.md     # Path mapping template
│   ├── CLAUDE.md.snippet        # CLAUDE.md integration snippet
│   └── knowledge/               # Knowledge file templates
│       ├── common/              # Cross-domain common knowledge (6 files)
│       └── domain/              # Domain-level knowledge (3 files)
├── scripts/
│   ├── java/                    # Java/Spring project scanners (3 scripts)
│   └── README.md                # Scanner output format specification
├── CLAUDE.md                    # Plugin-level guidance
├── CHANGELOG.md                 # Version history
├── package.json                 # Version info
├── LICENSE                      # MIT License
├── README.md
└── README.zh-CN.md              # Chinese documentation
```

## Upgrading the Plugin

### Update to Latest Version

```bash
claude plugin update ecw
```

Or run `/plugin update ecw` inside a Claude Code session, then restart the session to use new skills and commands.

### Upgrade Project Configuration

After updating the plugin, if the new version includes configuration migrations (e.g., new ecw.yml fields, new knowledge file templates), run in your target project:

```
/ecw-upgrade
```

This command detects the version gap between your project's ECW config and the plugin, lists pending migrations, and applies changes step by step.

## Troubleshooting

### Common Issues

**Q: New commands/skills don't appear after updating the plugin?**

A: Make sure you ran `claude plugin update ecw` and restarted the Claude Code session.

**Q: `/ecw-init` ran but `/ecw-validate-config` shows many warnings?**

A: Expected behavior. `ecw-init` generates template files that need to be filled with your project's actual content. Complete items based on the priority indicated in the validate report.

**Q: verify-completion hook reports "broken reference"?**

A: A file you modified references a `.claude/` path that doesn't exist. Check for typos or if the referenced file has been moved/deleted.

**Q: Java compilation check blocks task completion?**

A: Compilation must pass before completion is allowed. Fix compilation errors and re-mark as complete. If mvn is not in PATH, the compilation check is automatically skipped.

**Q: Phase 1 risk level is obviously inaccurate?**

A: Two common causes: (1) Keyword mappings in `change-risk-classification.md` aren't comprehensive enough — add missing keywords; (2) `shared-resources.md` is missing shared resource entries — re-run scanning scripts or add manually. Phase 3 calibration suggestions can help you systematically improve.

**Q: Knowledge files are empty, impact analysis is poor?**

A: Knowledge file quality directly determines analysis quality. For Java/Spring projects, use the scanning scripts under `scripts/java/` for automated extraction first, then review and supplement manually. Other tech stacks require manual population.

## Dependencies

- **Claude Code CLI** — ECW is a Claude Code plugin, requires CLI environment
- **superpowers plugin** — Provides `writing-plans`, `executing-plans`, `systematic-debugging` and other foundational skills; multiple ECW stages depend on these

## License

[MIT](LICENSE)
