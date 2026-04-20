---
name: domain-collab
description: |
  Use when user describes a business requirement spanning 2+ domains.
  TRIGGER when: requirement involves 2+ domain keywords defined in project CLAUDE.md routing table,
  user asks "analyze impact", "which domains affected", or risk-classifier routes here for cross-domain needs.
  DO NOT TRIGGER when: single-domain need (use ecw:requirements-elicitation), already have code diff
  (use ecw:biz-impact-analysis), pure technical refactoring with no business logic change.
---

# Domain Collab — Multi-Domain Collaboration Analysis

Accepts natural language requirements spanning 2+ domains, dispatches domain-specific Agents in parallel for analysis, and outputs a structured report after Coordinator cross-validation.

> **Single-domain requirements** are handled by `ecw:requirements-elicitation`. This skill focuses on multi-domain scenarios.

**Announce at start:** "Using ecw:domain-collab to coordinate multi-domain requirement analysis."

**Mode switch**: Update session-state.md MODE marker to `analysis`.

## Trigger

- **Manual**: `/domain-collab <requirement or change description>`
- **Auto-detect**: Triggered when user describes a business requirement

## Prerequisites

1. Read the file specified by ecw.yml `paths.domain_registry` (default `.claude/ecw/domain-registry.md`) to get domain definitions
2. Confirm `cross-domain-rules.md` exists under ecw.yml `paths.knowledge_common`

> **Knowledge file robustness**: If `domain-registry.md` does not exist, halt and notify user: "Domain registry not found. Run `/ecw-init` to initialize." If `cross-domain-rules.md` does not exist, log `[Warning: cross-domain-rules.md not found, Round 3 cross-validation will be degraded]` and continue — Round 3 §3c will skip rule validation for missing files.

## Workflow Overview

For a visual overview of the process, see `./workflow-diagram.md`.

Phases: Domain Identification → Round 1 (Independent Analysis, parallel) → Round 2 (Inter-Domain Negotiation, parallel) → Round 3 (Coordinator Cross-Validation) → Output Report.

## Phase 1: Domain Identification

1. Read keywords from project CLAUDE.md domain routing section (keyword→domain mapping table), match against user input, identify involved domains
2. Read matched domain metadata from domain-registry (knowledge directory, code directory, etc.)
3. Determine applicability:
   - 0 domains matched → Prompt user: "Cannot identify involved business domains. Please add more description or specify domain names"
   - 1 domain matched → Prompt: "Single-domain requirement — suggest using `/requirements-elicitation`. This skill focuses on multi-domain collaboration analysis"
   - 2+ domains matched → Proceed with collaboration analysis
4. If called by risk-classifier with domain list already provided, **skip confirmation** and execute directly.
5. If manually triggered (`/domain-collab`), confirm with user: "Identified domains: {domain list}. Will proceed with multi-domain collaboration analysis."

---

## Multi-Domain Collaboration Analysis (3 Rounds)

### Round 1: Independent Analysis (parallel)

Dispatch one Agent per matched domain (using Agent tool, `subagent_type: general-purpose`).

**Model selection**: `model: opus` (default from `models.defaults.analysis`; configurable via ecw.yml). Reason: domain analysis requires deep understanding of business rules, state machines, and cross-domain dependencies — errors here cascade to all downstream workflow. Exception: if Phase 1 or prior context strongly predicts a domain's `impact_level: none`, use `model: haiku` (`models.defaults.mechanical`) for that domain to reduce cost.

**Prerequisites (Coordinator executes before dispatching Agents):** Read `.claude/ecw/ecw.yml` to get project.name and component_types; read the file at ecw.yml `paths.domain_registry` to get domain definitions.

**All domain Agents use the prompt template defined in `agents/domain-analyst.md`.** Coordinator reads the template, fills variables (`{project_name}`, `{domain_id}`, `{domain_name}`, `{description}`, `{knowledge_root}`, `{code_root}`, `{user_requirement}`) with domain-registry data, and passes the filled prompt to each Agent.

**Coordinator operation steps:**
1. Read each matched domain's metadata from domain-registry
2. Fill the template above with variables to generate a prompt for each domain
3. Use Agent tool to dispatch all domain Agents in parallel (multiple Agent tool calls in a single message)
4. Collect all Agent YAML results
5. **Return value validation**: For each domain agent, verify the YAML contains required fields (`domain`, `impact_level`, `summary`). If a domain agent returns invalid format:
   - Log to Ledger: `[FAILED: domain-collab R1 {domain}, reason: invalid return format]`
   - Retry once with the same model
   - If retry also fails: mark that domain as `[incomplete: {domain}, format error]` and continue with remaining domains
6. **Ledger update**: Append records to `.claude/ecw/session-data/{workflow-id}/session-state.md` Subagent Ledger table (one row per domain Agent): `| domain-collab R1 | {domain name} | general | opus | medium | {HH:mm} | {duration} |`. Scale reference: small (<20K tokens), medium (20-80K), large (>80K); domain analysis R1 is typically medium. Note time before dispatch and compute duration after return.

**Timeout per Agent**: 180s. If a domain Agent has not returned within this time, terminate it and mark that domain as `[timeout, analysis unavailable]`.

**Round 1 Checkpoint**: After collecting all Round 1 YAML results, write them to `.claude/ecw/session-data/{workflow-id}/domain-collab-r1.md` (one YAML block per domain). This ensures Round 1 results survive context compaction before Round 2 begins.

### Round 2: Inter-Domain Negotiation (parallel)

After Round 1 independent analysis completes, Coordinator distributes each domain's change plan to others, letting each domain assess whether **other domains' changes** affect them.

**Coordinator operation steps:**

1. Collect Round 1 YAML output from all domain agents
2. For each domain, generate an "other domains' changes summary" — aggregate all other domains' `affected_components`, `state_changes`, `cross_domain_risks`
3. Specifically flag: other domains' `cross_domain_risks` where `target` points to this domain ("another domain specifically noted you may be affected")
4. Dispatch new round of domain agents in parallel

**Model selection**: `model: opus` (default from `models.defaults.analysis`; configurable via ecw.yml). Reason: negotiation requires reasoning about cross-domain conflicts, companion changes, and impact propagation — misjudgment leads to missed integration issues. Domains that were `impact_level: none` in Round 1 and had no inbound risks are skipped entirely (see skip rule below).

**Round 2 domain Agents use the prompt template defined in `agents/domain-negotiator.md`.** Coordinator fills template variables: `{project_name}`, `{domain_name}`, `{user_requirement}`, `{round1_yaml_output}`, and the "Other Domains' Change Plans" section (aggregate other domains' `affected_components`, `state_changes`, `cross_domain_risks`, flagging risks pointing to this domain).

**Coordinator operation steps:**
1. Fill the template above with variables to generate Round 2 prompt for each domain
2. Use Agent tool to dispatch all domain Agents in parallel (multiple Agent tool calls in a single message)
3. Collect all Agent YAML results
4. **Return value validation**: For each domain agent, verify the YAML contains required fields (`domain`, `negotiation_result.revised_impact_level`). If a domain agent returns invalid format:
   - Log to Ledger: `[FAILED: domain-collab R2 {domain}, reason: invalid return format]`
   - Retry once with the same model
   - If retry also fails: use Round 1 result unchanged for that domain, mark as `[incomplete: {domain} R2, format error]`
5. **Ledger update**: Append records to `.claude/ecw/session-data/{workflow-id}/session-state.md` Subagent Ledger table (one row per domain Agent): `| domain-collab R2 | {domain name} | general | opus | small | {HH:mm} | {duration} |`. Domain negotiation R2 is typically small. Note time before dispatch and compute duration after return.

**Timeout per Agent**: 120s (Round 2 is lighter than Round 1). If a domain Agent times out, use its Round 1 result unchanged.

**Round 2 Checkpoint**: After collecting all Round 2 YAML results, write them to `.claude/ecw/session-data/{workflow-id}/domain-collab-r2.md`. This ensures negotiation results survive context compaction before Round 3 cross-validation.

**Round 2 skip rule**: If a domain returned `impact_level: none` in Round 1 AND no other domain's `cross_domain_risks` points to it, **skip Round 2 Agent dispatch for that domain**. That domain is unaffected and no other domain flagged it as potentially affected — Round 2 negotiation would not produce new findings. Note in Round 3 cross-validation: "Domain X had no impact in Round 1 and no inbound risks; Round 2 skipped."

---

### Round 3: Coordinator Cross-Validation & Summary

**Coordinator completes the following steps itself (no Agent dispatch):**

**3a. Merge Round 1 + Round 2 Results**

For each domain:
- If Round 2's `revised_impact_level` is higher than Round 1's `impact_level` → Use Round 2 value
- Append Round 2's `revised_components` to Round 1's `affected_components`
- Add Round 2's `impact_from_others` to cross-domain dependency relationships
- Aggregate Round 2's `conflicts` into conflict list

**3b. Cross-Domain Conflict Detection**

Traverse all domains' merged `cross_domain_risks` + Round 2 `conflicts`, check:
- Do two domains propose incompatible changes to the same resource → Flag as "inter-domain conflict"
- Does domain A's `cross_domain_risks` point to domain B, but domain B reported `none` in both Round 1 and Round 2 → Flag as "suspected omission"

**3c. Cross-Domain Rule Validation (Omission Detection)**

Read the following files for final validation (read as needed, not all at once):
- `cross-domain-calls.md` → Verify whether direct call relationships mentioned by each domain are registered
- `mq-topology.md` → Verify whether MQ relationships mentioned by each domain are registered
- `shared-resources.md` → Check for overlooked shared resource impacts

> **Knowledge file robustness**: For each file, verify existence before reading. If a file is missing, skip that dimension's validation and note `[Warning: {file} not found, {dimension} validation skipped]` in the report. Do not halt Round 3 for missing knowledge files.

**3d. Code Verification**

For each `affected_component`, execute Grep verification. Read component types and their corresponding verification patterns from ecw.yml `component_types`:
- Service-layer components → `Grep pattern="class {name}" path=project root`
- Message queue components → `Grep pattern="{name}" path=project root`
- Domain model components → `Grep pattern="class {name}" path=domain model directory`

Tag verification results:
- Found → verified
- Not found → stale (knowledge docs say it exists but not found in code)
- Exists in code but not mentioned in knowledge docs → unregistered (suggest adding to knowledge docs)

For each `cross_domain_risk`:
- `Grep pattern="{resource}" path=project root` to confirm call relationship actually exists

**3e. Output Report**

1. **Write full report to file** `.claude/ecw/session-data/{workflow-id}/domain-collab-report.md`. **Before writing**, Read `./report-template.md` for the complete report structure.
2. **Output only summary version in conversation** (no more than 30 lines), including:
   - Domain overview table (domain name + level + changed component count + one-line summary)
   - Inter-domain conflicts (if any)
   - Suggested implementation order
   - Risk point summary

Detailed per-domain analysis, code verification results, negotiation findings, etc. are in the file. Subsequent Phase 2 and ecw:writing-plans read the file directly for full data.

**3f. Write Knowledge Summary File**

Write key information from knowledge files read during this analysis to `.claude/ecw/session-data/{workflow-id}/knowledge-summary.md` for reuse by downstream skills (risk-classifier Phase 2, impl-verify Round 2), reducing redundant reads of original knowledge files. **Before writing**, Read `./knowledge-summary-template.md` for the file structure.

---

---

## Fallback Logic

If all domain Agents return `impact_level: none`:

1. Check if user input involves shared-layer keywords:
   - `CoreBizService`, `Manager`, `common`, `infra`, `util`, `share`
2. If yes:
   - Read `shared-resources.md`, find all consumer domains for the related shared resource
   - Output warning: "This change does not belong to a specific business domain, but involves shared resource {resource} used by {domain list}. Suggest confirming impact on each."
3. If no:
   - Output: "Analysis complete. No business domain impact detected. This change may be a pure technical refactoring."

---

## Downstream Handoff: risk-classifier Phase 2

**P0/P1**: After collaboration analysis report is output, immediately execute risk-classifier Phase 2 (precise classification). Phase 2 will re-assess risk level based on this skill's collaboration analysis report (per-domain `affected_components`, `cross_domain_risks`, Coordinator cross-validation findings). Proceed to `ecw:writing-plans` after Phase 2 completes.

**P2**: Skip Phase 2 (Phase 1 lightweight check already covered), proceed directly to `ecw:writing-plans`.

**Do not skip Phase 2 for P0/P1 and go directly to writing-plans** — collaboration analysis may discover cross-domain dependencies not foreseen in Phase 1, requiring level upgrade.

Handoff flow:
```
P0/P1: ecw:domain-collab report → risk-classifier Phase 2 → ecw:writing-plans → [P0/P1 cross-domain: ecw:spec-challenge] → Implementation
P2:    ecw:domain-collab report → ecw:writing-plans → Implementation → ecw:impl-verify → ecw:biz-impact-analysis (suggested)
```

**Context management**: All analysis data has been persisted to files (domain-collab-report.md, knowledge-summary.md, session-data checkpoints). After Round 3 completes, check `.claude/ecw/state/context-health.txt` — if the file exists and starts with `HIGH`, suggest compaction as a non-blocking recommendation: output "上下文较大，建议输入 /compact 后自动继续" but do NOT wait for user response — proceed to the next skill immediately. If user does compact, the pre-compact hook ensures auto-resume.

> **CRITICAL — Auto-Continue Rule**: After Round 3 completes and report is output, update session-state.md `Next` field, then **immediately invoke** the next skill:
> - **P0/P1**: Immediately invoke risk-classifier Phase 2. Do NOT output confirmation text or wait for user input.
> - **P2**: Immediately invoke `ecw:writing-plans`. Do NOT ask for confirmation.
> - The user already confirmed the full workflow during Phase 1. If `Auto-Continue` field is missing or `no` in session-state.md, fall back to waiting for user confirmation (backward compatibility).

---

## Error Handling

| Scenario | Handling |
|----------|---------|
| Round 1/2 domain Agent returns empty or malformed YAML | Record `FAILED` in Subagent Ledger → retry once with explicit "return YAML only" instruction → still fails: mark domain as `[analysis unavailable]` and continue with remaining domains |
| All domain Agents fail in a Round | Notify user: "Domain analysis agents failed. Provide manual domain impact assessment or retry." Do not proceed to next Round |
| Knowledge file missing (`domain-registry.md`, `cross-domain-rules.md`, per-domain knowledge) | Log `[Warning: {file} not found, analysis degraded]` → continue with available data. If `domain-registry.md` missing: halt and ask user to run `/ecw-init` |
| Report file write failure (`domain-collab-report.md`, `knowledge-summary.md`) | Retry once → still fails: output full report content in conversation so downstream skills can reference it |

## Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "Only one domain is really affected, the others are minor" | If other domains have any cross_domain_risks pointing at them, they need independent analysis. "Minor" impact is still impact. |
| "Round 2 negotiation is overkill for this requirement" | Round 2 catches companion changes that Round 1 independent analysis misses. Skip it and integration issues surface during implementation. |
| "Domain X returned none, so I can skip it in Round 2" | Check inbound risks first. If another domain flagged X in cross_domain_risks, X must participate in Round 2 even if its own analysis was none. |
| "I already know the cross-domain dependencies" | Knowledge docs may be stale. Code verification (Round 3 §3d) catches what assumptions miss. |
| "The requirement is clear enough to skip domain analysis" | Cross-domain coupling is invisible from requirements text. Only domain experts reading their own business rules can identify companion changes. |
| "I'll merge the domain reports manually instead of running Round 3" | Round 3 cross-validation catches conflicts and omissions that simple merging misses. The coordinator's systematic checks are the point. |

## Notes

- Each round of Agent dispatch uses Agent tool's parallel calls (multiple Agent tool calls in a single message)
- Agent prompt variables are filled with domain-registry data
- Code verification uses Grep tool, not bash grep
- Cross-domain rule files are read as needed — do not load all at once
- Every cross-domain risk in analysis results must be tagged with source (knowledge docs / cross-domain rules / code scan)

## Supplementary Files

- `workflow-diagram.md` — DOT visual overview of the 3-Round process
- `report-template.md` — Full report template for domain-collab-report.md output
- `knowledge-summary-template.md` — Knowledge summary file structure for downstream reuse
