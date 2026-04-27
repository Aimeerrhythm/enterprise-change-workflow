# Enterprise Change Workflow (ECW)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

![Version](https://img.shields.io/badge/version-1.2.4-blue.svg)

[中文文档](README.zh-CN.md)

> Give AI the ability to "change one line of code, trace the full-chain impact" in large projects.

## Design Principles

See [docs/design-principles.md](docs/design-principles.md) — core idea: every scaffolding layer must pass the "model-upgrade test." Amplifiers get stronger with better models; crutches become dead weight.

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

### Multi-Repo Workspace (Cross-Service Development)

When changes span **2+ independent repositories** (e.g., provider + consumer services), use `ecw:workspace` instead of the standard single-repo flow. The workspace coordinator manages business decomposition, contract alignment, and parallel multi-session implementation.

**When to use**: Cross-repo changes with interface dependencies (Dubbo, MQ). **When NOT to use**: single-repo multi-module changes (use standard flow), monorepo services (use `ecw:domain-collab`).

```
/ecw:workspace create service-a ../service-b
        |
  Pre-flight — ECW readiness check per service
        |
  Phase 1 — Business Decomposition (Coordinator, NO code reading)
        |     Per-service roles (Provider/Consumer), interaction patterns
        |     Output: cross-service-plan.md + workspace-analysis-task.md per service
        |     [User confirms responsibilities]
        |
  Phase 2 — Per-Service Code Analysis (Child sessions, parallel)
        |     Each service opens a terminal split, runs its own analysis
        |     Output: analysis-report.md per service
        |
  Phase 3 — Contract Alignment + Conflict Resolution
        |     Cross-validate: MQ topics/DTOs, Dubbo signatures, ownership
        |     Conflicts → user decides
        |     Output: confirmed-contract.md per service
        |
  Phase 4 — Per-Service Implementation (Child sessions)
        |     Layer 1: Provider services (complete + publish API Jar)
        |     Layer 2: Consumer services (parallel)
        |     Each runs: ecw:writing-plans → implement → ecw:impl-verify
        |     Output: status.json per service
        |
  Phase 5 — Cross-Service Verification
        |     Dubbo signature match, MQ DTO compatibility, Maven version alignment
        |
  Phase 6 — Summary & Push
              Aggregate changes, confirm deploy order, batch push
```

**Sub-commands:**

| Command | Description |
|---------|-------------|
| `create <services...>` | Create workspace with git worktree isolation, auto-start run |
| `run "<requirement>"` | Execute 6-Phase coordinator flow |
| `status` | Show all services' git + session status |
| `push` | Batch push with per-service confirmation |
| `destroy` | Clean up worktrees + workspace directory |

**Key design principles:**
- **Code-free Phase 1** — business decomposition happens before any code analysis, preventing premature optimization
- **Verbatim requirement passing** — original requirement preserved without paraphrasing to prevent intent loss
- **Child session autonomy** — each service decomposes its own tasks; coordinator only aligns contracts
- **User gates at every architectural decision** — contract conflicts, interaction patterns, and push confirmation all surface to user

## Components

### Skills (15)

| Component | Trigger | Description |
|-----------|---------|-------------|
| `ecw:risk-classifier` | Any change/requirement/bug | P0-P3 risk classification + workflow routing, three phases (predict → precise → calibrate) |
| `ecw:domain-collab` | Cross-domain requirements (2+ domains) | Parallel domain agents analyze independently → mutual evaluation → coordinator cross-verification |
| `ecw:requirements-elicitation` | Single-domain P0/P1 requirements | 9-dimension systematic questioning to fully understand requirements |
| `ecw:writing-plans` | After requirements analysis (P0-P2) | Risk-aware implementation planning with domain context injection and downstream handoff |
| `ecw:spec-challenge` | After plan output (P0; P1 cross-domain only) | Dispatches independent agent for adversarial plan review, challenge-response cycles |
| `ecw:tdd` | Before implementation code (P0-P2) | Risk-differentiated test-driven development with ecw.yml integration |
| `ecw:impl-orchestration` | Plan execution with 4+ tasks (P0/P1) | Dependency-graph parallel layers + worktree isolation + risk-aware review gates |
| `ecw:systematic-debugging` | Bug/test failure/unexpected behavior | Domain-knowledge-driven root cause analysis with cross-domain tracing (§1-§5) |
| `ecw:impl-verify` | After implementation (P0-P2) | Multi-round convergence: code ↔ requirements/rules/plan/standards, severity-based exit |
| `ecw:biz-impact-analysis` | After impl-verify | Git diff → dispatches agent to analyze business impact, outputs structured report |
| `ecw:cross-review` | Manual only (`/ecw:cross-review`) | Cross-file structural consistency verification for document-heavy changes (optional tool) |
| `ecw:knowledge-audit` | Manual, periodic | Knowledge base health check: stale references, three-criteria compliance, content composition |
| `ecw:knowledge-track` | Manual, post-task | Doc utilization tracking (hit/miss/redundant/misleading), quantifies knowledge base ROI |
| `ecw:knowledge-repomap` | Manual, after refactors | Auto-generate code structure index from ecw.yml component_types |
| `ecw:workspace` | Manual only (`/ecw:workspace`) | **Multi-repo workspace**: git worktree isolation + 6-Phase coordinator (Phase 1 business-only decomposition, NO code reading → per-service code analysis with knowledge-first strategy → contract alignment with MQ/Dubbo dispatch sequencing → parallel implementation → cross-service field/signature verification → push). Child sessions use `bypassPermissions`, own task decomposition, and update session-state at milestones. MQ changes run parallel after contract alignment; Dubbo runs Layer 1 → Layer 2 serially. |

### Agents (7)

| Component | Dispatcher | Description |
|-----------|-----------|-------------|
| `biz-impact-analysis` | `ecw:biz-impact-analysis` | 5-step analysis: diff parsing → dependency graph queries → code scanning → external system evaluation → report generation |
| `spec-challenge` | `ecw:spec-challenge` | 4-dimension review: accuracy / information quality / boundaries & blind spots / robustness → fatal flaws + improvement suggestions |
| `domain-analyst` | `ecw:domain-collab` | R1 independent domain analysis — each domain agent analyzes impact in isolation |
| `domain-negotiator` | `ecw:domain-collab` | R2 cross-domain negotiation — domains evaluate each other's proposals |
| `implementer` | `ecw:impl-orchestration` | Per-task implementation with Fact-Forcing Gate traceability |
| `spec-reviewer` | `ecw:impl-orchestration` | Per-task spec compliance review |
| `impl-verifier` | `ecw:impl-verify` | Parallel 4-round verification (requirements/domain rules/plan/engineering standards) |

### Commands (3)

| Component | Description |
|-----------|-------------|
| `/ecw-init` | Project initialization wizard (3 modes: Attach/Manual/Scaffold) |
| `/ecw-validate-config` | Validate ECW configuration completeness (7-step check, outputs pass/warn/fail report) |
| `/ecw-upgrade` | Upgrade project ECW configuration to latest plugin version (idempotent migrations, partial failure protection) |

### Hooks (6 event points, dispatcher architecture)

ECW uses a unified dispatcher pattern for hooks. `hooks.json` registers 6 event points:

| Event | File | Description |
|-------|------|-------------|
| `SessionStart` | `session-start.py` | Auto-inject session-state / checkpoint / ecw.yml context + instincts |
| `Stop` | `stop-persist.py` | Marker-based state persistence on session stop |
| `PreToolUse` | `dispatcher.py` | Unified dispatcher with 5 sub-modules (see below) |
| `PostToolUse` | `post-edit-check.py` | Anti-pattern detection on Edit/Write |
| `PreCompact` | `pre-compact.py` | Recovery guidance injection before context compaction |
| `SessionEnd` | `session-end.py` | Session cleanup |

**Dispatcher sub-modules** (risk-level Profile gating: P0→strict, P1/P2→standard, P3→minimal):

| Sub-module | Profiles | Description |
|------------|----------|-------------|
| `verify-completion` | minimal, standard, strict | 4 hard blocks + 1 soft reminder before task completion |
| `config-protect` | minimal, standard, strict | Block AI from modifying critical ECW config files (auto-bypassed during ecw-upgrade/ecw-init via marker file) |
| `compact-suggest` | minimal, standard, strict | Proactive context compaction suggestion based on tool-call count |
| `secret-scan` | standard, strict | Detect sensitive data (AWS keys, JWT, GitHub tokens, private keys) |
| `bash-preflight` | standard, strict | Dangerous command pre-check (--no-verify, push --force, rm -rf) |

**verify-completion hard blocks (failure → prevents completion):**
1. Broken reference check — modified files reference non-existent `.claude/` paths
2. Stale reference check — deleted files still referenced elsewhere
3. Java compilation check — auto-runs `mvn compile` when `.java` files are modified
4. Java test check — auto-runs `mvn test` when `.java` files are modified (controlled by `ecw.yml` `verification.run_tests`)

## Installation

### Prerequisites

- **Claude Code CLI** — ECW is a Claude Code plugin, requires CLI environment

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

ECW currently supports **Java/Spring** projects. The `component_types` and `scan_patterns` in `ecw.yml` are configured for Java conventions:

| Tech Stack | Typical Component Types | Scan Patterns |
|-----------|------------------------|---------------|
| **Java/Spring** | BizService, Manager, DO, Controller, Mapper | @Resource, @DubboReference, RocketMQ |

## Project Structure

```
enterprise-change-workflow/
├── .claude-plugin/
│   ├── plugin.json              # Plugin metadata
│   └── marketplace.json         # Marketplace descriptor
├── skills/                      # 15 core skills
│   ├── risk-classifier/         # Risk classification (P0-P3, three phases)
│   ├── domain-collab/           # Cross-domain collaborative analysis (three rounds)
│   ├── requirements-elicitation/# Requirements elicitation (9-dimension questioning)
│   ├── writing-plans/           # Risk-aware implementation planning
│   ├── tdd/                     # Test-driven development (risk-differentiated)
│   ├── impl-orchestration/      # Subagent-driven plan execution (risk-aware review)
│   ├── systematic-debugging/    # Domain-knowledge-driven debugging
│   ├── spec-challenge/          # Adversarial review (challenge-response cycles)
│   ├── impl-verify/             # Implementation correctness verification (multi-round convergence)
│   ├── cross-review/            # Cross-file consistency verification (manual optional tool)
│   ├── biz-impact-analysis/     # Business impact analysis (5-step structured)
│   ├── knowledge-audit/         # Knowledge base health audit
│   ├── knowledge-track/         # Doc utilization tracking
│   ├── knowledge-repomap/       # Code structure index auto-generation
│   └── workspace/               # Multi-repo workspace (6-Phase coordinator)
├── agents/                      # 7 agent definitions
│   ├── biz-impact-analysis.md   # Impact analysis agent
│   ├── spec-challenge.md        # Adversarial review agent
│   ├── domain-analyst.md        # Domain-collab R1 independent analysis agent
│   ├── domain-negotiator.md     # Domain-collab R2 cross-domain negotiation agent
│   ├── implementer.md           # Impl-orchestration per-task implementation agent
│   ├── spec-reviewer.md         # Impl-orchestration spec review agent
│   └── impl-verifier.md         # Impl-verify parallel verification agent
├── commands/
│   ├── ecw-init.md              # Project initialization wizard
│   ├── ecw-validate-config.md   # Configuration validation command
│   └── ecw-upgrade.md           # Configuration upgrade command (versioned migrations)
├── hooks/                       # 6 event-point hook architecture
│   ├── hooks.json               # Hook registration (6 events: SessionStart/Stop/PreToolUse/PostToolUse/PreCompact/SessionEnd)
│   ├── dispatcher.py            # PreToolUse unified dispatcher (5 sub-modules, profile-gated)
│   ├── verify-completion.py     # Sub-module: completion verification (4 hard blocks + 1 soft reminder)
│   ├── config-protect.py        # Sub-module: config file protection
│   ├── compact-suggest.py       # Sub-module: proactive compaction suggestion
│   ├── secret-scan.py           # Sub-module: sensitive data detection
│   ├── bash-preflight.py        # Sub-module: dangerous command pre-check
│   ├── post-edit-check.py       # PostToolUse anti-pattern detection
│   ├── session-start.py         # SessionStart context injection + instinct loading
│   ├── stop-persist.py          # Stop marker-based state persistence
│   ├── pre-compact.py           # PreCompact recovery guidance
│   ├── session-end.py           # SessionEnd cleanup
│   ├── cost-tracker.py          # Token-based cost tracking and budget alerts
│   ├── gateguard-fact-force.py  # Fact-Forcing Gate compliance check
│   ├── marker_utils.py          # Shared idempotent marker update utilities
│   └── ecw_config.py            # Shared ECW config reader utilities
├── templates/                   # Config and knowledge file templates
│   ├── ecw.yml                  # Project config template
│   ├── domain-registry.md       # Domain registry template
│   ├── change-risk-classification.md # Risk classification calibration template
│   ├── calibration-log.md       # Calibration history template
│   ├── ecw-path-mappings.md     # Path mapping template
│   ├── CLAUDE.md.snippet        # CLAUDE.md integration snippet
│   ├── workspace.yml            # Workspace config template
│   ├── workspace-claude.md      # Workspace CLAUDE.md template
│   ├── cross-service-plan.md    # Cross-service change plan template
│   ├── service-task.md          # Per-service task template
│   ├── knowledge/               # Knowledge file templates
│   │   ├── common/              # Cross-domain common knowledge (6 files)
│   │   └── domain/              # Domain-level knowledge (3 files)
│   └── rules/                   # Engineering rule templates
│       ├── common/              # Universal rules
│       └── java/                # Java-specific rules
├── scripts/
│   ├── java/                    # Java/Spring project scanners (3 scripts)
│   ├── check-freshness.sh       # Detect stale knowledge file references
│   ├── generate-repo-map.sh     # Auto-extract component signatures for repo map
│   └── README.md                # Scanner output format specification
├── docs/                        # Design reference and advisory docs
│   └── design-reference.md      # Token budgets, model selection, context management guidelines
├── tests/                       # Three-layer test suite
│   ├── Makefile                 # lint / test-hook / eval-* targets
│   ├── static/                  # Layer 1: Python static lint (21 checks) + pytest unit tests (700 cases)
│   └── eval/                    # Layer 2: promptfoo behavioral eval (4 suites: risk-classifier/domain-collab/tdd/impl-verify)
├── CLAUDE.md                    # Plugin-level guidance
├── CHANGELOG.md                 # Version history
├── CONTRIBUTING.md              # Development conventions and review checklist
├── TROUBLESHOOTING.md           # Troubleshooting guide
├── package.json                 # Version info
├── ruff.toml                    # Python linting config
├── .markdownlint.json           # Markdown linting config
├── LICENSE                      # MIT License
├── README.md
└── README.zh-CN.md              # Chinese documentation
```

## Upgrading the Plugin

### Update to Latest Version

```bash
claude plugin update ecw@enterprise-change-workflow
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

A: Make sure you ran `claude plugin update ecw@enterprise-change-workflow` and restarted the Claude Code session.

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

For more troubleshooting scenarios, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development conventions, testing requirements, and the review checklist.

## Dependencies

- **Claude Code CLI** — ECW is a Claude Code plugin, requires CLI environment
- **No external plugin dependencies** — ECW is self-contained with all skills built-in (writing-plans, tdd, systematic-debugging, impl-orchestration, etc.)

## License

[MIT](LICENSE)
